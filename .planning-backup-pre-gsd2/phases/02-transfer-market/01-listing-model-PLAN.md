# Task 01: Listing Data Model

**Wave:** 1
**Requirements:** DETECT-01, DETECT-02, DETECT-03, DETECT-04
**Depends on:** nothing
**Files created:** `models/__init__.py`, `models/listing.py`
**Files modified:** none

---

## Objective

Create the data structures that represent player listings and scan results. These types are the shared contract consumed by the detector (T03) and integration (T04). No browser interaction — pure data model.

---

## What to Build

### File 1: `models/__init__.py`
Empty package marker. Just a comment indicating this is the models package.

### File 2: `models/listing.py`

**ListingState enum:**
- `ACTIVE = "active"` — currently on transfer market
- `EXPIRED = "expired"` — didn't sell, needs relist
- `SOLD = "sold"` — successfully sold
- `UNKNOWN = "unknown"` — could not determine state

**PlayerListing dataclass:**
| Field | Type | Purpose |
|-------|------|---------|
| `index` | `int` | Position in list (0-based) |
| `player_name` | `str` | Player name (e.g., "Mbappé") |
| `rating` | `Optional[int]` | Overall rating (e.g., 91) |
| `position` | `Optional[str]` | Position (e.g., "ST") |
| `state` | `ListingState` | Active/Expired/Sold/Unknown |
| `current_price` | `Optional[int]` | Buy Now price in coins |
| `start_price` | `Optional[int]` | Starting bid in coins |
| `time_remaining` | `Optional[str]` | Time remaining (active only) |

**Property:** `needs_relist -> bool` — returns `True` if `self.state == ListingState.EXPIRED`

**ListingScanResult dataclass:**
| Field | Type | Purpose |
|-------|------|---------|
| `total_items` | `int` | Total listing count |
| `active_count` | `int` | Active listings |
| `expired_count` | `int` | Expired listings |
| `sold_count` | `int` | Sold listings |
| `listings` | `list[PlayerListing]` | All listings |
| `is_empty` | `bool` | True if no listings at all |

**Class method:** `ListingScanResult.empty()` — returns a zeroed-out empty result.

---

## Implementation Notes

- Use `from __future__ import annotations` for forward references (Python 3.10+ style)
- Follow existing codebase conventions: Italian comments OK, logging via `logging.getLogger(__name__)`
- No external dependencies — stdlib only (`dataclasses`, `enum`, `typing`)
- Keep `models/listing.py` focused — no parsing logic here (that goes in detector.py)

---

## Verification

```bash
# Import test — should produce no errors
python -c "from models.listing import ListingState, PlayerListing, ListingScanResult; print('OK')"

# Quick smoke test
python -c "
from models.listing import ListingState, PlayerListing, ListingScanResult
p = PlayerListing(index=0, player_name='Mbappé', rating=91, position='ST', state=ListingState.EXPIRED, current_price=50000, start_price=45000, time_remaining=None)
assert p.needs_relist == True
r = ListingScanResult.empty()
assert r.is_empty == True
print('All assertions passed')
"
```

---

## Done Criteria

- [ ] `models/__init__.py` exists
- [ ] `models/listing.py` exists with `ListingState`, `PlayerListing`, `ListingScanResult`
- [ ] Import test passes without error
- [ ] `needs_relist` property returns `True` for EXPIRED, `False` for ACTIVE/SOLD/UNKNOWN
- [ ] `ListingScanResult.empty()` returns valid empty result with `is_empty=True`
