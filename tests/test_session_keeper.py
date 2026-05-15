"""Tests for SessionKeeper."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from bot_state import BotState, RebootRequestError
from browser.session_keeper import SessionKeeper


class TestSessionKeeper:
    """Test SessionKeeper methods."""

    @pytest.fixture
    def setup_session_keeper(self):
        mock_controller = MagicMock()
        mock_auth = MagicMock()
        mock_bot_state = MagicMock()
        mock_page = MagicMock()
        mock_get_credentials = MagicMock(return_value=("user", "pass"))
        mock_notifications_config = MagicMock()

        session_keeper = SessionKeeper(
            controller=mock_controller,
            auth=mock_auth,
            bot_state=mock_bot_state,
            page=mock_page,
            get_credentials_fn=mock_get_credentials,
            notifications_config=mock_notifications_config,
        )
        return {
            "session_keeper": session_keeper,
            "controller": mock_controller,
            "auth": mock_auth,
            "bot_state": mock_bot_state,
            "page": mock_page,
            "get_credentials": mock_get_credentials,
            "notifications_config": mock_notifications_config,
        }

    def test_execute_heartbeat_success(self, setup_session_keeper):
        """_execute_heartbeat completes without errors if session is active."""
        components = setup_session_keeper
        components["auth"].is_logged_in.return_value = True
        components["auth"].is_console_session_active.return_value = False
        components["page"].locator.return_value.count.return_value = 1

        components["session_keeper"]._execute_heartbeat()

        components["page"].locator.assert_called_once_with("button.ut-tab-bar-item.icon-transfer")
        components["page"].locator.return_value.first.click.assert_called_once_with(timeout=3000, force=True)

    def test_execute_heartbeat_session_expired_and_recovered(self, setup_session_keeper):
        """_execute_heartbeat recovers session if expired and ensure_session succeeds."""
        components = setup_session_keeper
        components["auth"].is_logged_in.side_effect = [False, True]
        components["auth"].is_console_session_active.return_value = False
        components["page"].locator.return_value.count.return_value = 1

        components["session_keeper"]._execute_heartbeat()

        assert components["auth"].is_logged_in.call_count == 2

    def test_execute_heartbeat_session_expired_and_recovery_fails(self, setup_session_keeper):
        """_execute_heartbeat raises RebootRequestError if ensure_session fails."""
        components = setup_session_keeper
        components["auth"].is_logged_in.return_value = False
        components["auth"].is_console_session_active.return_value = False

        with (
            patch("browser.session_keeper.send_telegram_error_with_screenshot") as mock_send,
            patch.object(components["session_keeper"], "ensure_session", side_effect=Exception("Recovery failed")),
        ):
            with pytest.raises(RebootRequestError) as excinfo:
                components["session_keeper"]._execute_heartbeat()
            assert "Impossibile recuperare la sessione" in str(excinfo.value)
            mock_send.assert_called_once()

    def test_execute_heartbeat_transfers_button_not_found(self, setup_session_keeper):
        """_execute_heartbeat skips click if 'Transfers' button is not found."""
        components = setup_session_keeper
        components["auth"].is_logged_in.return_value = True
        components["auth"].is_console_session_active.return_value = False
        components["page"].locator.return_value.count.return_value = 0
        components["page"].get_by_role.return_value.count.return_value = 0

        components["session_keeper"]._execute_heartbeat()

        components["page"].locator.return_value.first.click.assert_not_called()

    def test_execute_heartbeat_console_session_detected(self, setup_session_keeper):
        """_execute_heartbeat activates console mode if console session is detected."""
        components = setup_session_keeper
        components["auth"].is_logged_in.return_value = True
        components["auth"].is_console_session_active.return_value = True
        components["bot_state"].is_console_mode.return_value = False
        components["page"].locator.return_value.count.return_value = 0
        components["page"].get_by_role.return_value.count.return_value = 0

        components["session_keeper"]._execute_heartbeat()

        components["bot_state"].set_console_mode.assert_called_once_with(True, hours=0.5)

    def test_supervise_pause_caps_wait_to_auto_resume_deadline(self, setup_session_keeper):
        """La pausa temporizzata non deve dormire sempre 300s se scade prima."""
        components = setup_session_keeper
        real_state = BotState()
        real_state.set_paused(True, hours=1)
        real_state._pause_until = datetime.now() + timedelta(seconds=30)
        components["session_keeper"].bot_state = real_state

        with patch.object(real_state, "wait_interruptible", return_value=False) as wait_mock:
            handled = components["session_keeper"].supervise_state(MagicMock())

        assert handled is False
        assert wait_mock.call_args.args[0] <= 31

    def test_supervise_console_caps_wait_to_auto_resume_deadline(self, setup_session_keeper):
        """La console mode temporizzata deve svegliarsi alla deadline, non dopo 300s."""
        components = setup_session_keeper
        real_state = BotState()
        real_state.set_console_mode(True, hours=1)
        real_state._console_mode_until = datetime.now() + timedelta(seconds=30)
        components["session_keeper"].bot_state = real_state

        with patch.object(real_state, "wait_interruptible", return_value=False) as wait_mock:
            handled = components["session_keeper"].supervise_state(MagicMock())

        assert handled is False
        assert wait_mock.call_args.args[0] <= 31
