"""Tests for active session probing."""

from unittest.mock import MagicMock, patch

from browser.auth import AuthManager


def _locator(count=1, visible=True):
    loc = MagicMock()
    loc.count.return_value = count
    loc.first.is_visible.return_value = visible
    return loc


class TestAuthProbe:
    def test_menu_probe_clicks_alternate_menu_before_transfers(self):
        auth = AuthManager({})
        page = MagicMock()
        page.url = "https://www.ea.com/fifa/ultimate-team/web-app/"
        home = _locator()
        transfers = _locator()

        def by_role(role, name):
            if name == "Home":
                return home
            if name == "Transfers":
                return transfers
            return _locator(count=0)

        page.get_by_role.side_effect = by_role

        with (
            patch.object(auth, "check_and_handle_disconnect_modal", return_value=False),
            patch.object(auth, "is_console_session_active", return_value=False),
            patch.object(auth, "is_logged_in", return_value=True),
        ):
            assert auth.probe_session_alive(page) is True

        home.first.click.assert_called_once()
        transfers.first.click.assert_called_once()

    def test_menu_probe_returns_false_when_disconnect_modal_appears_after_menu_change(self):
        auth = AuthManager({})
        page = MagicMock()
        page.url = "https://www.ea.com/fifa/ultimate-team/web-app/"
        page.get_by_role.side_effect = lambda role, name: _locator() if name in {"Home", "Transfers"} else _locator(0)

        with (
            patch.object(auth, "check_and_handle_disconnect_modal", side_effect=[False, True]),
            patch.object(auth, "is_console_session_active", return_value=False),
            patch.object(auth, "is_logged_in", return_value=True),
        ):
            assert auth.probe_session_alive(page) is False

    def test_refresh_fallback_runs_after_consecutive_menu_probe_failures(self):
        auth = AuthManager({"session_probe_refresh_after_failures": 2})
        page = MagicMock()
        page.url = "https://www.ea.com/fifa/ultimate-team/web-app/"
        page.get_by_role.return_value = _locator(count=0)

        with (
            patch.object(auth, "check_and_handle_disconnect_modal", return_value=False),
            patch.object(auth, "is_console_session_active", return_value=False),
            patch.object(auth, "is_logged_in", return_value=True),
        ):
            assert auth.probe_session_alive(page) is False
            assert auth.probe_session_alive(page) is True

        page.reload.assert_called_once()
