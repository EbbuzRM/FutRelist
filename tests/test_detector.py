"""Unit tests for browser/detector.py — DOM parsing functions for transfer market.

NOTE: These tests will fail until T03 creates browser/detector.py.
That's expected for Wave 0 — tests define the contract before implementation.
"""
import pytest


class TestParsePrice:
    """Tests for parse_price() function."""

    def test_parse_price_formatted(self):
        """parse_price('10,000 coins') == 10000"""
        from browser.detector import parse_price
        assert parse_price("10,000 coins") == 10000

    def test_parse_price_plain(self):
        """parse_price('500') == 500"""
        from browser.detector import parse_price
        assert parse_price("500") == 500

    def test_parse_price_none(self):
        """parse_price(None) is None"""
        from browser.detector import parse_price
        assert parse_price(None) is None

    def test_parse_price_empty(self):
        """parse_price('') is None"""
        from browser.detector import parse_price
        assert parse_price("") is None

    def test_parse_price_no_digits(self):
        """parse_price('no numbers') is None"""
        from browser.detector import parse_price
        assert parse_price("no numbers") is None


class TestParseRating:
    """Tests for parse_rating() function."""

    def test_parse_rating_normal(self):
        """parse_rating('87') == 87"""
        from browser.detector import parse_rating
        assert parse_rating("87") == 87

    def test_parse_rating_with_prefix(self):
        """parse_rating('OVR 91') == 91"""
        from browser.detector import parse_rating
        assert parse_rating("OVR 91") == 91

    def test_parse_rating_none(self):
        """parse_rating(None) is None"""
        from browser.detector import parse_rating
        assert parse_rating(None) is None

    def test_parse_rating_empty(self):
        """parse_rating('') is None"""
        from browser.detector import parse_rating
        assert parse_rating("") is None


class TestDetermineState:
    """Tests for determine_state() function."""

    def test_determine_state_expired_english(self):
        """determine_state('Expired') == ListingState.EXPIRED"""
        from browser.detector import determine_state
        from models.listing import ListingState
        assert determine_state("Expired") == ListingState.EXPIRED

    def test_determine_state_expired_italian(self):
        """determine_state('scaduto') == ListingState.EXPIRED"""
        from browser.detector import determine_state
        from models.listing import ListingState
        assert determine_state("scaduto") == ListingState.EXPIRED

    def test_determine_state_active_english(self):
        """determine_state('Active') == ListingState.ACTIVE"""
        from browser.detector import determine_state
        from models.listing import ListingState
        assert determine_state("Active") == ListingState.ACTIVE

    def test_determine_state_active_italian(self):
        """determine_state('attivo') == ListingState.ACTIVE"""
        from browser.detector import determine_state
        from models.listing import ListingState
        assert determine_state("attivo") == ListingState.ACTIVE

    def test_determine_state_sold_english(self):
        """determine_state('Sold') == ListingState.SOLD"""
        from browser.detector import determine_state
        from models.listing import ListingState
        assert determine_state("Sold") == ListingState.SOLD

    def test_determine_state_sold_italian(self):
        """determine_state('venduto') == ListingState.SOLD"""
        from browser.detector import determine_state
        from models.listing import ListingState
        assert determine_state("venduto") == ListingState.SOLD

    def test_determine_state_unknown(self):
        """determine_state('???') == ListingState.UNKNOWN"""
        from browser.detector import determine_state
        from models.listing import ListingState
        assert determine_state("???") == ListingState.UNKNOWN
