---
phase: 4
slug: configuration-system
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-23
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 7.0.0 |
| **Config file** | none (uses defaults) |
| **Quick run command** | `pytest tests/test_config.py -x --tb=short` |
| **Full suite command** | `pytest tests/ -x --tb=short` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_config.py -x --tb=short`
- **After every plan wave:** Run `pytest tests/ -x --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | CONFIG-01 | unit | `pytest tests/test_config.py::test_duration_validation -x` | ❌ Wave 0 | ⬜ pending |
| 4-01-02 | 01 | 1 | CONFIG-01 | unit | `pytest tests/test_config.py::test_invalid_duration -x` | ❌ Wave 0 | ⬜ pending |
| 4-02-01 | 02 | 1 | CONFIG-02 | unit | `pytest tests/test_config.py::test_price_rules -x` | ❌ Wave 0 | ⬜ pending |
| 4-02-02 | 02 | 1 | CONFIG-02 | unit | `pytest tests/test_config.py::test_invalid_price_range -x` | ❌ Wave 0 | ⬜ pending |
| 4-03-01 | 03 | 1 | CONFIG-03 | unit | `pytest tests/test_config.py::test_scan_interval -x` | ❌ Wave 0 | ⬜ pending |
| 4-04-01 | 04 | 1 | CONFIG-04 | unit | `pytest tests/test_config.py::test_round_trip -x` | ❌ Wave 0 | ⬜ pending |
| 4-04-02 | 04 | 1 | CONFIG-04 | unit | `pytest tests/test_config.py::test_create_defaults -x` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_config.py` — unit tests for validation, round-trip, CLI coercion
- [ ] `config/config.py` — AppConfig dataclass + ConfigManager class

---

## Manual-Only Verifications

*No manual-only verifications for this phase. All CONFIG-01 through CONFIG-04 are covered by automated tests in Per-Task Verification Map above.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
