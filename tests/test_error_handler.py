"""Tests for ErrorHandler (retry + session helpers)."""

from unittest.mock import MagicMock

import pytest

from browser.auth import AuthError
from browser.error_handler import (
    ensure_session,
    handle_element_not_found,
    is_session_expired,
    retry_on_timeout,
)


class TestRetryOnTimeout:
    """Test retry_on_timeout decorator."""

    def test_retries_on_playwright_error_and_raises_after_max(self):
        """retry_on_timeout retries on timeout errors and raises after max attempts."""
        from playwright.sync_api import Error as PlaywrightError

        call_count = 0

        @retry_on_timeout
        def failing_func():
            nonlocal call_count
            call_count += 1
            raise PlaywrightError("Timeout exceeded: waiting for selector")

        with pytest.raises(PlaywrightError):
            failing_func()

        assert call_count == 3  # max 3 attempts

    def test_succeeds_on_second_attempt(self):
        """retry_on_timeout succeeds on second attempt after one timeout failure."""
        from playwright.sync_api import Error as PlaywrightError

        call_count = 0

        @retry_on_timeout
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise PlaywrightError("Timeout exceeded: transient network error")
            return "success"

        result = flaky_func()
        assert result == "success"
        assert call_count == 2


class TestIsSessionExpired:
    """Test is_session_expired detection."""

    def test_returns_true_when_url_contains_login(self):
        """is_session_expired returns True when page URL contains 'login'."""
        mock_page = MagicMock()
        mock_page.url = "https://www.ea.com/fifa/login?returnTo=app"

        assert is_session_expired(mock_page) is True

    def test_returns_false_when_ut_app_present(self):
        """is_session_expired returns False when .ut-app element is present."""
        mock_page = MagicMock()
        mock_page.url = "https://www.ea.com/fifa/web-app"
        mock_page.query_selector.return_value = MagicMock()  # element found

        assert is_session_expired(mock_page) is False


class TestHandleElementNotFound:
    """Test handle_element_not_found fallback."""

    def test_reloads_page_when_element_not_found(self):
        """handle_element_not_found reloads page when element missing and fallback_reload=True."""
        mock_page = MagicMock()
        # First call: element not found, second call (after reload): found
        mock_page.query_selector.side_effect = [None, MagicMock()]

        result = handle_element_not_found(mock_page, ".test-selector")

        assert result is True
        mock_page.reload.assert_called_once()
        mock_page.wait_for_timeout.assert_called_with(3000)

    def test_returns_false_when_element_still_missing_after_reload(self):
        """handle_element_not_found returns False if element still missing after reload."""
        mock_page = MagicMock()
        mock_page.query_selector.return_value = None  # always not found

        result = handle_element_not_found(mock_page, ".missing-selector")

        assert result is False
        mock_page.reload.assert_called_once()


class TestEnsureSession:
    """Test ensure_session function."""

    def test_session_already_active(self):
        """ensure_session does nothing if session is already active."""
        mock_page = MagicMock()
        mock_page.url = "https://www.ea.com/fifa/ultimate-team/web-app/"
        mock_auth = MagicMock()
        mock_auth.check_and_handle_disconnect_modal.return_value = False
        mock_auth.is_logged_in.return_value = True
        mock_controller = MagicMock()

        ensure_session(mock_page, mock_auth, mock_controller)
        mock_auth.is_logged_in.assert_called_once_with(mock_page, timeout_ms=5000)
        mock_auth.authenticate.assert_not_called()

    def test_session_expired_but_recovered_after_reload(self):
        """ensure_session recovers session after reload if initially not logged in."""
        mock_page = MagicMock()
        mock_page.url = "https://www.ea.com/fifa/ultimate-team/web-app/"
        mock_auth = MagicMock()
        mock_auth.check_and_handle_disconnect_modal.return_value = False
        mock_auth.is_logged_in.side_effect = [False, True]
        mock_controller = MagicMock()

        ensure_session(mock_page, mock_auth, mock_controller)
        assert mock_auth.is_logged_in.call_count == 2
        mock_page.reload.assert_called_once()
        mock_auth.authenticate.assert_not_called()

    def test_session_expired_and_authenticate_success(self):
        """ensure_session calls perform_full_login if session is expired and recovers successfully."""
        mock_page = MagicMock()
        mock_page.url = "https://signin.ea.com/p/signin/"
        mock_auth = MagicMock()
        mock_auth.is_logged_in.return_value = False
        mock_auth.check_and_handle_disconnect_modal.return_value = False
        mock_controller = MagicMock()

        ensure_session(mock_page, mock_auth, mock_controller)
        mock_auth.perform_full_login.assert_called_once_with(mock_page, mock_controller, get_credentials_fn=None)

    def test_session_expired_and_authenticate_fails(self):
        """ensure_session raises AuthError if perform_full_login fails."""
        mock_page = MagicMock()
        mock_page.url = "https://signin.ea.com/p/signin/"
        mock_auth = MagicMock()
        mock_auth.is_logged_in.return_value = False
        mock_auth.check_and_handle_disconnect_modal.return_value = False
        mock_auth.perform_full_login.side_effect = Exception("Login failed")
        mock_controller = MagicMock()

        with pytest.raises(AuthError) as excinfo:
            ensure_session(mock_page, mock_auth, mock_controller)
        assert "Recupero sessione fallito" in str(excinfo.value)

    def test_check_and_handle_disconnect_modal_triggers_recovery(self):
        """ensure_session forces re-authentication if disconnect modal is detected."""
        mock_page = MagicMock()
        mock_page.url = "https://www.ea.com/fifa/ultimate-team/web-app/"
        mock_auth = MagicMock()
        mock_auth.check_and_handle_disconnect_modal.return_value = True
        mock_auth.is_logged_in.return_value = False
        mock_controller = MagicMock()

        ensure_session(mock_page, mock_auth, mock_controller)
        mock_auth.perform_full_login.assert_called_once_with(mock_page, mock_controller, get_credentials_fn=None)

    def test_passes_interruptible_wait_to_full_login(self):
        """ensure_session passa la wait interrompibile al recovery login quando disponibile."""
        mock_page = MagicMock()
        mock_page.url = "https://signin.ea.com/p/signin/"
        mock_auth = MagicMock()
        mock_auth.is_logged_in.return_value = False
        mock_auth.check_and_handle_disconnect_modal.return_value = False
        mock_controller = MagicMock()
        wait_fn = MagicMock(return_value=False)

        ensure_session(mock_page, mock_auth, mock_controller, wait_fn=wait_fn)

        mock_auth.perform_full_login.assert_called_once_with(
            mock_page, mock_controller, wait_fn=wait_fn, get_credentials_fn=None
        )
