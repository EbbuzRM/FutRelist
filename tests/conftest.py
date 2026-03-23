import pytest


@pytest.fixture
def sample_listing_html():
    """Returns mock HTML matching WebApp DOM structure with 3 player listings."""
    return """
    <div class="listFUTItem player">
        <div class="player-name">Mbappé</div>
        <div class="rating">91</div>
        <div class="position">ST</div>
        <div class="auction-state">Expired</div>
        <div class="auctionValue">50,000 coins</div>
        <div class="auctionStartPrice">45,000</div>
        <div class="time-remaining"></div>
    </div>
    <div class="listFUTItem player">
        <div class="player-name">Messi</div>
        <div class="rating">90</div>
        <div class="position">RW</div>
        <div class="auction-state">Active</div>
        <div class="auctionValue">30,000 coins</div>
        <div class="auctionStartPrice">28,000</div>
        <div class="time-remaining">2h 30m</div>
    </div>
    <div class="listFUTItem player">
        <div class="player-name">Haaland</div>
        <div class="rating">89</div>
        <div class="position">ST</div>
        <div class="auction-state">Sold</div>
        <div class="auctionValue">40,000 coins</div>
        <div class="auctionStartPrice">38,000</div>
        <div class="time-remaining"></div>
    </div>
    """


@pytest.fixture
def empty_listings_html():
    """Returns HTML with no listing items (empty state)."""
    return '<div class="no-items"></div>'
