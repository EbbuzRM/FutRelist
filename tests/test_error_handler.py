"""Tests for ErrorHandler (retry + session helpers)."""
from unittest.mock import MagicMock, patch

import pytest

from browser.error_handler import (
    retry_on_timeout,
    is_session_expired,
    handle_element_not_found,
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
