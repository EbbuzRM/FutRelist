# FIFA 26 WebApp Auto-Relist Tool

## Core Value
Automated relisting of expired players on FIFA 26 WebApp transfer market, running continuously in background.

## Current Milestone: v1.0 Auto-Relist MVP

**Goal:** Create a browser automation tool that monitors and automatically relists expired player listings on FIFA 26 WebApp.

**Target features:**
- Browser automation for FIFA 26 WebApp interaction
- Auto-detect expired listings
- Automatic relisting with configurable pricing
- Background/continuous operation
- Basic logging of actions

## Tech Stack
- **Language:** Python 3.13
- **Browser Automation:** Playwright (recommended over Selenium for speed/reliability)
- **UI:** CLI with status output, optional minimal GUI later
- **Storage:** JSON for configuration and logs

## Validated Requirements
*To be defined in REQUIREMENTS.md*

## Architecture
- Playwright-based browser controller
- Session management (handle login, cookies)
- Transfer market page interaction
- Listing detection and relisting logic
- Configuration system for pricing rules

## Constraints
- Must handle FIFA 26 WebApp authentication
- Rate limiting awareness (avoid bans)
- Session persistence across restarts
- Error recovery for network/UI issues

## Last Updated
2026-03-23T00:15:36+01:00
