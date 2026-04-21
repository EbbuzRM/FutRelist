---
phase: 5
slug: logging-error-handling
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-23
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=7.0.0 |
| **Config file** | none (existing) |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-00-01 | 00 | 1 | LOG-01 | unit | `pytest tests/test_action_log.py::test_json_formatter -x` | ❌ W0 | ⬜ pending |
| 05-00-02 | 00 | 1 | LOG-02 | unit | `pytest tests/test_action_log.py::test_error_log_entry -x` | ❌ W0 | ⬜ pending |
| 05-00-03 | 00 | 1 | LOG-04 | unit | `pytest tests/test_action_log.py::test_history_parsing -x` | ❌ W0 | ⬜ pending |
| 05-00-04 | 00 | 1 | ERROR-01 | unit | `pytest tests/test_error_handler.py::test_retry_backoff -x` | ❌ W0 | ⬜ pending |
| 05-00-05 | 00 | 1 | ERROR-02 | unit | `pytest tests/test_error_handler.py::test_session_expiry_detection -x` | ❌ W0 | ⬜ pending |
| 05-00-06 | 00 | 1 | ERROR-03 | unit | `pytest tests/test_error_handler.py::test_element_not_found_fallback -x` | ❌ W0 | ⬜ pending |
| 05-00-07 | 00 | 1 | ERROR-04 | unit | `pytest tests/test_rate_limiter.py -x` | ❌ W0 | ⬜ pending |
| 05-01-01 | 01 | 2 | LOG-01,LOG-02 | integration | `pytest tests/test_action_log.py -x` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 2 | ERROR-01,ERROR-02,ERROR-03 | integration | `pytest tests/test_error_handler.py -x` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 2 | ERROR-04 | integration | `pytest tests/test_rate_limiter.py -x` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 3 | LOG-03,LOG-04 | integration | `pytest tests/ -v` | N/A | ⬜ pending |
| 05-02-02 | 02 | 3 | ALL | e2e | Manual verification (live WebApp test) | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_action_log.py` — stubs for LOG-01, LOG-02, LOG-04 (JsonFormatter, ActionLogEntry, history parsing)
- [ ] `tests/test_error_handler.py` — stubs for ERROR-01, ERROR-02, ERROR-03 (retry, session, element fallback)
- [ ] `tests/test_rate_limiter.py` — stubs for ERROR-04 (RateLimiter wait, wait_if_needed)
- [ ] `pip install tenacity rich` — framework install for retry + console status

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real-time console status display | LOG-03 | Visual verification of rich Live display during scan cycle | Run main.py, observe status table updates during relist cycle |
| Live re-login after session expiry | ERROR-02 | Requires real FIFA WebApp session to expire | Run tool, wait for session timeout, verify auto re-login |
| Action history readability | LOG-04 | Human judgment on output format | Run `fifa-relist history`, verify readable output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending