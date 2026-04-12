"""Test per SoldHandler — navigazione, raccolta crediti, pulizia venduti."""
from unittest.mock import MagicMock, patch

import pytest

from browser.sold_handler import SoldHandler
from models.sold_result import SoldCreditsResult


@pytest.fixture
def mock_page():
    """Playwright page mock."""
    page = MagicMock()
    page.query_selector.return_value = None
    page.query_selector_all.return_value = []
    page.evaluate.return_value = []
    page.wait_for_selector.return_value = True
    page.get_by_role.return_value.count.return_value = 0
    return page


@pytest.fixture
def mock_config():
    """Config dict minimale."""
    return {
        "rate_limiting": {
            "min_delay_ms": 0,  # Zero delay per test veloci
            "max_delay_ms": 0,
        }
    }


@pytest.fixture
def handler(mock_page, mock_config):
    """SoldHandler con page e config mock."""
    return SoldHandler(page=mock_page, config=mock_config)


class TestSoldCreditsResult:
    """Test per il dataclass SoldCreditsResult."""

    def test_default_values(self):
        """Valori di default: successo con zero crediti."""
        result = SoldCreditsResult()
        assert result.total_credits == 0
        assert result.items_cleared == 0
        assert result.success is True
        assert result.error is None

    def test_error_result(self):
        """Risultato di errore."""
        result = SoldCreditsResult(success=False, error="Navigation failed")
        assert result.success is False
        assert result.error == "Navigation failed"
        assert result.total_credits == 0
        assert result.items_cleared == 0

    def test_success_with_credits(self):
        """Risultato di successo con crediti."""
        result = SoldCreditsResult(total_credits=50000, items_cleared=3)
        assert result.success is True
        assert result.total_credits == 50000
        assert result.items_cleared == 3
        assert result.error is None


class TestNavigateToSoldItems:
    """Test per la navigazione alla pagina Sold Items."""

    def test_navigation_success(self, handler, mock_page):
        """Navigazione riuscita → True."""
        btn = MagicMock()
        btn.count.return_value = 1
        mock_page.get_by_role.side_effect = lambda role, name=None: btn

        result = handler._navigate_to_sold_items()
        assert result is True

    def test_navigation_no_transfers_button(self, handler, mock_page):
        """Pulsante Transfers non trovato → False."""
        btn = MagicMock()
        btn.count.return_value = 0
        mock_page.get_by_role.side_effect = lambda role, name=None: btn

        result = handler._navigate_to_sold_items()
        assert result is False

    def test_navigation_no_sold_items_tab(self, handler, mock_page):
        """Tab Sold Items non trovato → False."""
        call_count = [0]

        def mock_get_by_role(role, name=None):
            call_count[0] += 1
            btn = MagicMock()
            if call_count[0] == 1:
                # Transfers button exists
                btn.count.return_value = 1
            else:
                # Sold Items tab not found
                btn.count.return_value = 0
            return btn

        mock_page.get_by_role.side_effect = mock_get_by_role

        result = handler._navigate_to_sold_items()
        assert result is False


class TestCollectSoldCredits:
    """Test per la raccolta dei crediti dagli oggetti venduti."""

    def test_collect_credits_from_dom(self, handler, mock_page):
        """Raccoglie i prezzi degli oggetti venduti dal DOM."""
        # Simula 3 oggetti venduti con prezzi
        mock_page.eval_on_selector_all.return_value = [
            {"price": "10,000 coins"},
            {"price": "25,000 coins"},
            {"price": "5,500 coins"},
        ]

        total, count = handler._collect_sold_credits()
        assert total == 40500  # 10000 + 25000 + 5500
        assert count == 3

    def test_collect_no_items(self, handler, mock_page):
        """Nessun oggetto venduto → (0, 0)."""
        mock_page.eval_on_selector_all.return_value = []

        total, count = handler._collect_sold_credits()
        assert total == 0
        assert count == 0

    def test_collect_handles_parse_errors(self, handler, mock_page):
        """Prezzi non parsabili vengono ignorati."""
        mock_page.eval_on_selector_all.return_value = [
            {"price": "10,000 coins"},
            {"price": "invalid"},
            {"price": "5,000 coins"},
        ]

        total, count = handler._collect_sold_credits()
        assert total == 15000  # Solo i due validi
        assert count == 2


class TestClearSoldItems:
    """Test per la cancellazione degli oggetti venduti."""

    def test_clear_success(self, handler, mock_page):
        """Click sul pulsante Clear → successo."""
        clear_btn = MagicMock()
        clear_btn.count.return_value = 1
        # Dialog confirmation: no confirm button visible
        confirm_btn = MagicMock()
        confirm_btn.count.return_value = 0

        def mock_get_by_role(role, name=None):
            if name in ("Clear Sold Items", "Cancella oggetti venduti"):
                return clear_btn
            return confirm_btn

        mock_page.get_by_role.side_effect = mock_get_by_role

        result = handler._clear_sold_items()
        assert result is True
        clear_btn.first.click.assert_called_once()

    def test_clear_no_button(self, handler, mock_page):
        """Pulsante Clear non trovato → False."""
        clear_btn = MagicMock()
        clear_btn.count.return_value = 0

        def mock_get_by_role(role, name=None):
            return clear_btn

        mock_page.get_by_role.side_effect = mock_get_by_role

        locator_mock = MagicMock()
        locator_mock.count.return_value = 0
        mock_page.locator.return_value = locator_mock

        result = handler._clear_sold_items()
        assert result is False


class TestProcessSoldItems:
    """Test per il flusso completo process_sold_items()."""

    def test_full_flow_success(self, handler, mock_page):
        """Navigazione + raccolta + cancellazione → SoldCreditsResult."""
        # Mock navigazione
        def mock_get_by_role(role, name=None):
            btn = MagicMock()
            btn.count.return_value = 1
            return btn

        mock_page.get_by_role.side_effect = mock_get_by_role

        # Mock raccolta crediti
        mock_page.eval_on_selector_all.return_value = [
            {"price": "10,000 coins"},
            {"price": "5,000 coins"},
        ]

        result = handler.process_sold_items()

        assert result.success is True
        assert result.total_credits == 15000
        assert result.items_cleared == 2
        assert result.error is None

    def test_navigation_failure(self, handler, mock_page):
        """Navigazione fallita → SoldCreditsResult(success=False)."""
        mock_page.get_by_role.return_value.count.return_value = 0

        result = handler.process_sold_items()

        assert result.success is False
        assert result.error is not None
        assert result.total_credits == 0
        assert result.items_cleared == 0

    def test_no_sold_items(self, handler, mock_page):
        """Nessun oggetto venduto → risultato con zero crediti."""
        def mock_get_by_role(role, name=None):
            btn = MagicMock()
            btn.count.return_value = 1
            return btn

        mock_page.get_by_role.side_effect = mock_get_by_role
        mock_page.eval_on_selector_all.return_value = []

        result = handler.process_sold_items()

        assert result.success is True
        assert result.total_credits == 0
        assert result.items_cleared == 0

    def test_exception_handling(self, handler, mock_page):
        """Eccezione durante il processo → SoldCreditsResult(success=False)."""
        mock_page.get_by_role.side_effect = Exception("Unexpected error")

        result = handler.process_sold_items()

        assert result.success is False
        assert result.error is not None
