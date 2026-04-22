#!/usr/bin/env python3
"""
Playwright browser controller with persistent session state.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from playwright.async_api import async_playwright, BrowserContext

from config.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class BrowserController:
    """Playwright browser controller with persistent session state."""

    def __init__(self, config: ConfigManager):
        self.config = config
        self._browser = None
        self._user_data_dir = self._get_user_data_dir()
        self._session_state_path = Path(".gsd/browser-state/session.json")
        self._session_state_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_user_data_dir(self) -> Path:
        """Get or create user data directory."""
        user_data_dir = self.config.get("browser", "user_data_dir", default="browser-profile")
        user_data_dir_path = Path(user_data_dir)
        user_data_dir_path.mkdir(parents=True, exist_ok=True)
        return user_data_dir_path

    async def _save_session_state(self, context: BrowserContext):
        """Save session cookies and storage."""
        try:
            cookies = await context.context.cookies()
            storage = {
                "cookies": cookies,
                "localStorage": {},
                "sessionStorage": {}
            }
            # Save cookies
            for cookie in cookies:
                if cookie["name"] == "sessionId":
                    storage["sessionId"] = cookie["value"]
            
            # Save local/session storage for main frame
            page = await context.new_page()
            await page.goto("https://www.easports.com/fifa/ultimate-team/web-app")
            
            local_storage = await page.evaluate("() => Object.fromEntries(Object.entries(localStorage))")
            session_storage = await page.evaluate("() => Object.fromEntries(Object.entries(sessionStorage))")
            
            storage["localStorage"] = local_storage
            storage["sessionStorage"] = session_storage
            
            with open(self._session_state_path, "w", encoding="utf-8") as f:
                json.dump(storage, f, indent=2)
            
            logger.info(f"Session state saved to {self._session_state_path}")
            
        except Exception as e:
            logger.error(f"Failed to save session state: {e}")

    async def _restore_session_state(self, context: BrowserContext):
        """Restore session cookies and storage."""
        try:
            if not self._session_state_path.exists():
                logger.info("No session state to restore")
                return
            
            with open(self._session_state_path, "r", encoding="utf-8") as f:
                storage = json.load(f)
            
            # Restore cookies
            if "cookies" in storage:
                await context.add_cookies(storage["cookies"])
            
            # Restore local/session storage
            page = await context.new_page()
            await page.goto("https://www.easports.com/fifa/ultimate-team/web-app")
            
            if "localStorage" in storage:
                await page.evaluate("""(storage) => {
                    Object.entries(storage).forEach(([key, value]) => {
                        localStorage.setItem(key, value);
                    });
                }""", storage["localStorage"])
            
            if "sessionStorage" in storage:
                await page.evaluate("""(storage) => {
                    Object.entries(storage).forEach(([key, value]) => {
                        sessionStorage.setItem(key, value);
                    });
                }""", storage["sessionStorage"])
            
            logger.info("Session state restored")
            
        except Exception as e:
            logger.error(f"Failed to restore session state: {e}")
            # If restore fails, continue without session

    async def launch_browser(self) -> Tuple[async_playwright, BrowserContext]:
        """Launch browser with persistent session."""
        playwright = await async_playwright.start()
        
        try:
            browser = await playwright.chromium.launch(
                headless=self.config.get("browser", "headless", default=True),
                user_data_dir=str(self._user_data_dir)
            )
            
            context = await browser.new_context()
            
            # Try to restore session
            await self._restore_session_state(context)
            
            return playwright, context
            
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            await playwright.stop()
            raise

    async def close_browser(self, playwright: async_playwright):
        """Close browser and save session."""
        try:
            # Save session before closing
            if self._browser:
                context = await self._browser.new_context()
                await self._save_session_state(context)
                await context.close()
            
        finally:
            await playwright.stop()

    async def new_context(self) -> BrowserContext:
        """Create new browser context with session restoration."""
        playwright, context = await self.launch_browser()
        self._browser = playwright.chromium
        return context

    async def save_session(self, context: BrowserContext):
        """Save current session state."""
        await self._save_session_state(context)

    async def restore_session(self, context: BrowserContext):
        """Restore session state."""
        await self._restore_session_state(context)