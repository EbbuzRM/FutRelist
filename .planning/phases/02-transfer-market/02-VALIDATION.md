---
phase: 2
slug: transfer-market
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-23
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `pytest tests/test_detector.py tests/test_listing_model.py -x` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_detector.py tests/test_listing_model.py -x`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01-listing-model | 1 | DETECT-01 | unit | `pytest tests/test_listing_model.py -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01-listing-model | 1 | DETECT-02 | unit | `pytest tests/test_listing_model.py -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01-listing-model | 1 | DETECT-03 | unit | `pytest tests/test_listing_model.py -x` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01-listing-model | 1 | DETECT-04 | unit | `pytest tests/test_listing_model.py -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02-navigator | 1 | BROWSER-04 | integration | `pytest tests/test_navigator.py -x` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03-detector | 2 | DETECT-01 | unit | `pytest tests/test_detector.py::test_determine_state_expired -x` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03-detector | 2 | DETECT-02 | unit | `pytest tests/test_detector.py::test_parse_listing_data -x` | ❌ W0 | ⬜ pending |
| 02-03-03 | 03-detector | 2 | DETECT-03 | unit | `pytest tests/test_detector.py::test_determine_state -x` | ❌ W0 | ⬜ pending |
| 02-03-04 | 03-detector | 2 | DETECT-04 | unit | `pytest tests/test_detector.py::test_empty_state -x` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04-integration | 3 | BROWSER-04 | integration | manual | — | ⬜ pending |
| 02-04-02 | 04-integration | 3 | DETECT-01-04 | integration | manual | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_detector.py` — unit tests for parse_price, parse_rating, determine_state, scan_listings mock
- [ ] `tests/test_listing_model.py` — unit tests for ListingState, PlayerListing, ListingScanResult
- [ ] `tests/test_navigator.py` — integration test stub for go_to_transfer_list (requires mock or live WebApp)
- [ ] `tests/conftest.py` — shared fixtures (mock Page, sample DOM HTML)
- [ ] `pytest` install — `pip install pytest` (not in requirements.txt)
- [ ] Mock HTML fixtures for unit testing without live WebApp

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Navigate to Transfer List on live WebApp | BROWSER-04 | Requires live FC 26 WebApp session | Run `python main.py`, verify navigation succeeds, listing summary prints |
| Read real player data from Transfer List | DETECT-02 | DOM structure varies by WebApp state | Verify player names, ratings, prices match WebApp display |
| Distinguish active/expired on live data | DETECT-03 | State depends on actual listing timing | Verify expired listings flagged correctly when listings expire |
| Handle empty Transfer List | DETECT-04 | Requires WebApp account with no listings | Clear all listings, verify "Nessun listing trovato" message |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved — Wave 0 test infrastructure creates all files referenced in VALIDATION.md
