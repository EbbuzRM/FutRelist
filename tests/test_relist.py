"""Unit tests for browser/relist.py — price adjustment and result model.

NOTE: These tests will fail until Tasks 3-4 create the implementation files.
That's expected for TDD — tests define the contract before implementation.
"""
import pytest


class TestCalculateAdjustedPrice:
    """Tests for calculate_adjusted_price() function."""

    def test_percentage_decrease(self):
        """price 10000, type 'percentage', value -10 → 9000"""
        from browser.relist import calculate_adjusted_price
        result = calculate_adjusted_price(10000, "percentage", -10)
        assert result == 9000

    def test_percentage_increase(self):
        """price 10000, type 'percentage', value 5 → 10500"""
        from browser.relist import calculate_adjusted_price
        result = calculate_adjusted_price(10000, "percentage", 5)
        assert result == 10500

    def test_fixed_decrease(self):
        """price 10000, type 'fixed', value -500 → 9500"""
        from browser.relist import calculate_adjusted_price
        result = calculate_adjusted_price(10000, "fixed", -500)
        assert result == 9500

    def test_fixed_increase(self):
        """price 10000, type 'fixed', value 1000 → 11000"""
        from browser.relist import calculate_adjusted_price
        result = calculate_adjusted_price(10000, "fixed", 1000)
        assert result == 11000

    def test_bounds_clamp_below_min(self):
        """price 300, type 'percentage', value -50 → 200 (not 150)"""
        from browser.relist import calculate_adjusted_price
        result = calculate_adjusted_price(300, "percentage", -50)
        assert result == 200

    def test_bounds_clamp_above_max(self):
        """price 14000000, type 'fixed', value 2000000 → 15000000"""
        from browser.relist import calculate_adjusted_price
        result = calculate_adjusted_price(14000000, "fixed", 2000000)
        assert result == 15000000

    def test_zero_adjustment(self):
        """price 50000, type 'percentage', value 0 → 50000"""
        from browser.relist import calculate_adjusted_price
        result = calculate_adjusted_price(50000, "percentage", 0)
        assert result == 50000

    def test_unknown_type_returns_unchanged(self):
        """unknown type returns current_price unchanged"""
        from browser.relist import calculate_adjusted_price
        result = calculate_adjusted_price(10000, "unknown", -10)
        assert result == 10000


class TestRelistResult:
    """Tests for RelistResult dataclass."""

    def test_successful_result(self):
        """Creating a successful result (success=True, error=None)"""
        from models.relist_result import RelistResult
        result = RelistResult(
            listing_index=0,
            player_name="Mbappé",
            old_price=50000,
            new_price=45000,
            success=True,
        )
        assert result.success is True
        assert result.error is None
        assert result.player_name == "Mbappé"

    def test_failed_result(self):
        """Creating a failed result (success=False, error='timeout')"""
        from models.relist_result import RelistResult
        result = RelistResult(
            listing_index=1,
            player_name="Messi",
            old_price=30000,
            new_price=None,
            success=False,
            error="timeout",
        )
        assert result.success is False
        assert result.error == "timeout"

    def test_field_access(self):
        """Field access returns correct values"""
        from models.relist_result import RelistResult
        result = RelistResult(
            listing_index=2,
            player_name="Haaland",
            old_price=40000,
            new_price=36000,
            success=True,
        )
        assert result.listing_index == 2
        assert result.player_name == "Haaland"
        assert result.old_price == 40000
        assert result.new_price == 36000


class TestRelistBatchResult:
    """Tests for RelistBatchResult dataclass."""

    def test_from_results_aggregation(self):
        """from_results() correctly counts total=3, succeeded=2, failed=1"""
        from models.relist_result import RelistResult, RelistBatchResult
        results = [
            RelistResult(0, "A", 1000, 900, True),
            RelistResult(1, "B", 2000, 1800, True),
            RelistResult(2, "C", 3000, None, False, error="timeout"),
        ]
        batch = RelistBatchResult.from_results(results)
        assert batch.total == 3
        assert batch.succeeded == 2
        assert batch.failed == 1

    def test_success_rate(self):
        """success_rate returns correct percentage (2/3 ≈ 66.7%)"""
        from models.relist_result import RelistResult, RelistBatchResult
        results = [
            RelistResult(0, "A", 1000, 900, True),
            RelistResult(1, "B", 2000, 1800, True),
            RelistResult(2, "C", 3000, None, False, error="timeout"),
        ]
        batch = RelistBatchResult.from_results(results)
        assert abs(batch.success_rate - 66.66666666666667) < 0.01

    def test_empty_results(self):
        """Empty results list returns zeroed batch"""
        from models.relist_result import RelistBatchResult
        batch = RelistBatchResult.from_results([])
        assert batch.total == 0
        assert batch.succeeded == 0
        assert batch.failed == 0
        assert batch.success_rate == 0.0
