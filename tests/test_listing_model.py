"""Unit tests for models/listing.py — data model for transfer market listings.

NOTE: These tests will fail until T01 creates models/listing.py.
That's expected for Wave 0 — tests define the contract before implementation.
"""
import pytest


def test_listing_state_values():
    """Assert ListingState has ACTIVE, EXPIRED, SOLD, UNKNOWN with correct string values."""
    from models.listing import ListingState

    assert ListingState.ACTIVE.value == "active"
    assert ListingState.EXPIRED.value == "expired"
    assert ListingState.SOLD.value == "sold"
    assert ListingState.UNKNOWN.value == "unknown"


def test_player_listing_creation():
    """Create a PlayerListing with all fields, assert fields accessible."""
    from models.listing import PlayerListing, ListingState

    listing = PlayerListing(
        index=0,
        player_name="Mbappé",
        rating=91,
        position="ST",
        state=ListingState.EXPIRED,
        current_price=50000,
        start_price=45000,
        time_remaining=None,
    )

    assert listing.index == 0
    assert listing.player_name == "Mbappé"
    assert listing.rating == 91
    assert listing.position == "ST"
    assert listing.state == ListingState.EXPIRED
    assert listing.current_price == 50000
    assert listing.start_price == 45000
    assert listing.time_remaining is None


def test_player_listing_needs_relist():
    """Assert needs_relist is True for EXPIRED, False for ACTIVE/SOLD/UNKNOWN."""
    from models.listing import PlayerListing, ListingState

    expired = PlayerListing(
        index=0, player_name="Test", rating=80, position="ST",
        state=ListingState.EXPIRED, current_price=1000, start_price=1000,
        time_remaining=None,
    )
    assert expired.needs_relist is True

    active = PlayerListing(
        index=1, player_name="Test", rating=80, position="ST",
        state=ListingState.ACTIVE, current_price=1000, start_price=1000,
        time_remaining="2h",
    )
    assert active.needs_relist is False

    sold = PlayerListing(
        index=2, player_name="Test", rating=80, position="ST",
        state=ListingState.SOLD, current_price=1000, start_price=1000,
        time_remaining=None,
    )
    assert sold.needs_relist is False

    unknown = PlayerListing(
        index=3, player_name="Test", rating=80, position="ST",
        state=ListingState.UNKNOWN, current_price=1000, start_price=1000,
        time_remaining=None,
    )
    assert unknown.needs_relist is False


def test_listing_scan_result_empty():
    """Call ListingScanResult.empty(), assert is_empty=True, all counts 0, listings=[]."""
    from models.listing import ListingScanResult

    result = ListingScanResult.empty()

    assert result.is_empty is True
    assert result.total_count == 0
    assert result.active_count == 0
    assert result.expired_count == 0
    assert result.sold_count == 0
    assert result.listings == []


def test_listing_scan_result_counts():
    """Create ListingScanResult with listings, verify counts."""
    from models.listing import ListingScanResult, PlayerListing, ListingState

    listings = [
        PlayerListing(
            index=0, player_name="Mbappé", rating=91, position="ST",
            state=ListingState.EXPIRED, current_price=50000, start_price=45000,
            time_remaining=None,
        ),
        PlayerListing(
            index=1, player_name="Messi", rating=90, position="RW",
            state=ListingState.ACTIVE, current_price=30000, start_price=28000,
            time_remaining="2h 30m",
        ),
        PlayerListing(
            index=2, player_name="Haaland", rating=89, position="ST",
            state=ListingState.SOLD, current_price=40000, start_price=38000,
            time_remaining=None,
        ),
    ]

    result = ListingScanResult(
        total_count=3,
        active_count=1,
        expired_count=1,
        sold_count=1,
        listings=listings,
    )

    assert result.is_empty is False
    assert result.total_count == 3
    assert result.active_count == 1
    assert result.expired_count == 1
    assert result.sold_count == 1
    assert len(result.listings) == 3
