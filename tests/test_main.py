"""Unit tests for main.py — bot startup notification."""

from unittest.mock import MagicMock, patch

import pytest


class TestBotStartedNotification:
    """Verify that '🤖 Bot avviato' Telegram notification is sent after login."""

    @patch("main.NotificationBatch")
    @patch("main.RelistEngine")
    @patch("main.SessionKeeper")
    @patch("main.RelistExecutor")
    @patch("main.ListingDetector")
    @patch("main.TransferMarketNavigator")
    @patch("main.RateLimiter")
    @patch("main.AuthManager")
    @patch("main.BrowserController")
    @patch("main.ConfigManager")
    @patch("main.BotState")
    @patch("main.send_telegram_alert")
    @patch("main.authenticate")
    @patch("main.load_dotenv")
    @patch("main.setup_logging")
    def test_send_bot_started_notification_after_login(
        self,
        mock_setup_logging,
        mock_load_dotenv,
        mock_authenticate,
        mock_send_alert,
        mock_bot_state_cls,
        mock_config_mgr_cls,
        mock_browser_ctrl_cls,
        mock_auth_mgr_cls,
        mock_rate_limiter_cls,
        mock_navigator_cls,
        mock_detector_cls,
        mock_executor_cls,
        mock_keeper_cls,
        mock_engine_cls,
        mock_batch_cls,
    ):
        """After authenticate() succeeds, send_telegram_alert must be called with '🤖 Bot avviato'."""
        # -- Setup mocks --
        mock_config = MagicMock()
        mock_config.to_dict.return_value = {}
        mock_config.notifications.telegram_token = "fake-token"
        mock_config.notifications.telegram_chat_id = "fake-chat"
        mock_config.rate_limiting.min_delay_ms = 1000
        mock_config.rate_limiting.max_delay_ms = 2000
        mock_config_mgr_cls.return_value = MagicMock(load=lambda: mock_config)

        mock_bot_state = MagicMock()
        mock_bot_state.has_commands.return_value = False
        mock_bot_state.is_reboot_requested.return_value = True  # break outer loop after 1st iter
        mock_bot_state_cls.return_value = mock_bot_state

        mock_page = MagicMock()
        mock_controller = MagicMock()
        mock_controller.start.return_value = mock_page
        mock_browser_ctrl_cls.return_value = mock_controller

        mock_auth_mgr = MagicMock()
        mock_auth_mgr.load_session.return_value = None
        mock_auth_mgr_cls.return_value = mock_auth_mgr

        mock_keeper = MagicMock()
        mock_keeper.supervise_state.return_value = False
        mock_keeper.handle_reboot.side_effect = SystemExit
        mock_keeper_cls.return_value = mock_keeper

        mock_engine = MagicMock()
        mock_engine.process_cycle.return_value = (0, 0, 60, MagicMock(), None, 0)
        mock_engine_cls.return_value = mock_engine

        mock_batch = MagicMock()
        mock_batch.should_flush.return_value = False
        mock_batch_cls.return_value = mock_batch

        mock_telegram = MagicMock()
        mock_telegram_cls = MagicMock(return_value=mock_telegram)

        # -- Execute --
        with patch("main.TelegramHandler", mock_telegram_cls):
            from main import main
            with pytest.raises(SystemExit):
                main()

        # -- Assert --
        mock_authenticate.assert_called_once()
        mock_send_alert.assert_any_call(mock_config.notifications, "🤖 Bot avviato")

    @patch("main.NotificationBatch")
    @patch("main.RelistEngine")
    @patch("main.SessionKeeper")
    @patch("main.RelistExecutor")
    @patch("main.ListingDetector")
    @patch("main.TransferMarketNavigator")
    @patch("main.RateLimiter")
    @patch("main.AuthManager")
    @patch("main.BrowserController")
    @patch("main.ConfigManager")
    @patch("main.BotState")
    @patch("main.send_telegram_alert")
    @patch("main.authenticate")
    @patch("main.load_dotenv")
    @patch("main.setup_logging")
    def test_notification_sent_before_rate_limiter(
        self,
        mock_setup_logging,
        mock_load_dotenv,
        mock_authenticate,
        mock_send_alert,
        mock_bot_state_cls,
        mock_config_mgr_cls,
        mock_browser_ctrl_cls,
        mock_auth_mgr_cls,
        mock_rate_limiter_cls,
        mock_navigator_cls,
        mock_detector_cls,
        mock_executor_cls,
        mock_keeper_cls,
        mock_engine_cls,
        mock_batch_cls,
    ):
        """The 'Bot avviato' notification must be sent BEFORE RateLimiter is created."""
        # -- Setup mocks (same as above) --
        mock_config = MagicMock()
        mock_config.to_dict.return_value = {}
        mock_config.notifications.telegram_token = "fake-token"
        mock_config.notifications.telegram_chat_id = "fake-chat"
        mock_config.rate_limiting.min_delay_ms = 1000
        mock_config.rate_limiting.max_delay_ms = 2000
        mock_config_mgr_cls.return_value = MagicMock(load=lambda: mock_config)

        mock_bot_state = MagicMock()
        mock_bot_state.has_commands.return_value = False
        mock_bot_state.is_reboot_requested.return_value = True
        mock_bot_state_cls.return_value = mock_bot_state

        mock_page = MagicMock()
        mock_controller = MagicMock()
        mock_controller.start.return_value = mock_page
        mock_browser_ctrl_cls.return_value = mock_controller

        mock_auth_mgr = MagicMock()
        mock_auth_mgr.load_session.return_value = None
        mock_auth_mgr_cls.return_value = mock_auth_mgr

        mock_keeper = MagicMock()
        mock_keeper.supervise_state.return_value = False
        mock_keeper.handle_reboot.side_effect = SystemExit
        mock_keeper_cls.return_value = mock_keeper

        mock_engine = MagicMock()
        mock_engine.process_cycle.return_value = (0, 0, 60, MagicMock(), None, 0)
        mock_engine_cls.return_value = mock_engine

        mock_batch = MagicMock()
        mock_batch.should_flush.return_value = False
        mock_batch_cls.return_value = mock_batch

        # Track call order
        call_order = []
        mock_send_alert.side_effect = lambda *a, **kw: call_order.append("send_alert")
        mock_rate_limiter_cls.side_effect = lambda *a, **kw: call_order.append("rate_limiter")

        with patch("main.TelegramHandler"):
            from main import main
            with pytest.raises(SystemExit):
                main()

        # send_alert must appear before rate_limiter in call order
        assert "send_alert" in call_order, f"send_telegram_alert not called. Order: {call_order}"
        if "rate_limiter" in call_order:
            idx_alert = call_order.index("send_alert")
            idx_rl = call_order.index("rate_limiter")
            assert idx_alert < idx_rl, f"Notification sent AFTER RateLimiter. Order: {call_order}"


class TestGetCredentials:
    """Tests for get_credentials() function."""

    def test_returns_env_vars(self):
        """get_credentials returns FIFA_EMAIL and FIFA_PASSWORD from env."""
        with patch.dict("os.environ", {"FIFA_EMAIL": "test@example.com", "FIFA_PASSWORD": "secret123"}):
            from main import get_credentials
            email, password = get_credentials()
            assert email == "test@example.com"
            assert password == "secret123"

    def test_raises_when_missing_email(self):
        """get_credentials raises RuntimeError when FIFA_EMAIL is missing."""
        with patch.dict("os.environ", {"FIFA_PASSWORD": "secret123"}, clear=True):
            from main import get_credentials
            with pytest.raises(RuntimeError, match="FIFA_EMAIL"):
                get_credentials()

    def test_raises_when_missing_password(self):
        """get_credentials raises RuntimeError when FIFA_PASSWORD is missing."""
        with patch.dict("os.environ", {"FIFA_EMAIL": "test@example.com"}, clear=True):
            from main import get_credentials
            with pytest.raises(RuntimeError, match="FIFA_PASSWORD"):
                get_credentials()
