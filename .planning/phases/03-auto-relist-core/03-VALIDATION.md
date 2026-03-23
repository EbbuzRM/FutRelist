---
phase: 3
slug: auto-relist-core
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-23
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 7.0.0 |
| **Config file** | none (uses defaults) |
| **Quick run command** | `pytest tests/test_relist.py -x --tb=short` |
| **Full suite command** | `pytest tests/ -x --tb=short` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_relist.py -x --tb=short`
- **After every plan wave:** Run `pytest tests/ -x --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | RELIST-02 | unit | `pytest tests/test_relist.py::test_price_adjustment_percentage -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | RELIST-02 | unit | `pytest tests/test_relist.py::test_price_adjustment_fixed -x` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | RELIST-02 | unit | `pytest tests/test_relist.py::test_price_adjustment_bounds -x` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 1 | RELIST-03 | unit | `pytest tests/test_relist.py::test_relist_result -x` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 2 | RELIST-01 | browser | `python -c "from browser.relist import RelistExecutor; print('OK')"` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 2 | RELIST-04 | browser | manual test with live WebApp | N/A | ⬜ pending |
| 03-03-01 | 03 | 3 | RELIST-01,02,03,04 | integration | `python -c "import main; print('OK')"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_relist.py` — unit tests for `calculate_adjusted_price()` and `RelistResult`
- [ ] No new framework install needed (pytest already in requirements.txt)

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Click relist on individual expired listing | RELIST-01 | Requires live FIFA WebApp with expired listings | 1. Run main.py, 2. Login, 3. Navigate to Transfer List, 4. Verify relist click works on expired listing |
| Confirmation dialog auto-accept | RELIST-04 | Dialog behavior varies by WebApp version | 1. Trigger relist on expired listing, 2. Verify confirmation dialog appears and is auto-accepted, 3. Verify listing state changes to ACTIVE |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
