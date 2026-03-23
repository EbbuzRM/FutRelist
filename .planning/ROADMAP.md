# FIFA 26 Auto-Relist Tool - Roadmap

## Current Milestone: v1.0 Auto-Relist MVP

## Phases

### Phase 1: Browser Setup & Authentication ✅ COMPLETED
**Goal:** Establish reliable browser automation and FIFA 26 WebApp login
**Requirements:** BROWSER-01, BROWSER-02, BROWSER-03
**Completed:** 2026-03-23

**Success Criteria:**
1. ✅ Playwright launches browser and navigates to FIFA 26 WebApp
2. ✅ User can authenticate with stored credentials
3. ✅ Session cookies persist across restarts
4. ✅ Browser handles login page detection

---

### Phase 2: Transfer Market Navigation  ⏳ IN PROGRESS (1/5 plans)
**Goal:** Navigate to My Listings and read listing state
**Requirements:** BROWSER-04, DETECT-01, DETECT-02, DETECT-03, DETECT-04

**Progress:**
| Plan | Name | Status | Commit |
|------|------|--------|--------|
| 00 | Test Infrastructure Setup | ✅ Complete | 4554109 |
| 01 | Listing Data Model | ⬜ Pending | - |
| 02 | 3/6 | In Progress|  |
| 03 | DOM Detector | ⬜ Pending | - |
| 04 | Integration | ⬜ Pending | - |

**Success Criteria:**
1. System navigates to Transfer Market > My Listings
2. System identifies expired vs active listings
3. System reads player name, rating, price from each listing
4. System handles empty transfer list state

---

### Phase 3: Auto-Relist Core
**Goal:** Execute relisting actions on expired players
**Requirements:** RELIST-01, RELIST-02, RELIST-03, RELIST-04

**Success Criteria:**
1. System clicks relist on expired players
2. System applies price adjustment rules
3. System confirms relisting completed
4. System handles confirmation dialogs

---

### Phase 4: Configuration System
**Goal:** User-configurable settings for pricing and timing
**Requirements:** CONFIG-01, CONFIG-02, CONFIG-03, CONFIG-04

**Success Criteria:**
1. User can set listing duration
2. User can configure price rules (min/max/undercut)
3. User can set scan interval
4. Settings persist in JSON config file

---

### Phase 5: Logging & Error Handling
**Goal:** Robust operation with logging and error recovery
**Requirements:** LOG-01, LOG-02, LOG-03, LOG-04, ERROR-01, ERROR-02, ERROR-03, ERROR-04

**Success Criteria:**
1. All relisting actions logged with timestamps
2. Real-time console status display
3. Network disconnection recovery
4. Session expiration handling (auto re-login)
5. Rate limiting between actions

---

## Completed Milestones
- Contact Management System v1.0 - Basic contact CRUD with GUI

## All milestone requirements mapped to phases.
