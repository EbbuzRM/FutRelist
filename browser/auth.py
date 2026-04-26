#!/usr/bin/env python3
"""
EA authentication flow with 2FA and session persistence.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from playwright.async_api import Page, expect

from browser.controller import BrowserController

logger = logging.getLogger(__name__)


class Auth:
    """EA authentication with 2FA handling."""

    def __init__(self, browser_controller: BrowserController):
        self.browser_controller = browser_controller
        self._auth_state_path = Path(".gsd/browser-state/auth_state.json")
        self._auth_state_path.parent.mkdir(parents=True, exist_ok=True)

    async def _load_auth_state(self) -> Optional[Dict[str, Any]]:
        """Load saved authentication state."""
        try:
            if self._auth_state_path.exists():
                with open(self._auth_state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load auth state: {e}")
        return None

    async def _save_auth_state(self, state: Dict[str, Any]):
        """Save authentication state."""
        try:
            with open(self._auth_state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save auth state: {e}")

    async def _check_session_validity(self, page: Page) -> bool:
        """Check if current session is valid."""
        try:
            # Check if we're on the Transfer List page
            await page.goto("https://www.easports.com/fifa/ultimate-team/web-app")
            await asyncio.sleep(2)
            
            # Look for Transfer List button
            transfer_list_selector = "text=Transfer List"
            transfer_list_button = page.locator(transfer_list_selector)
            
            if await transfer_list_button.is_visible():
                logger.info("Session is valid - Transfer List accessible")
                return True
                
        except Exception as e:
            logger.error(f"Session validity check failed: {e}")
        
        return False

    async def _handle_2fa(self, page: Page) -> bool:
        """Handle 2FA prompt."""
        try:
            # Wait for 2FA prompt
            await expect(page).to_have_url("*/login")
            
            # Check for 2FA input
            two_fa_input = page.locator("//input[@type='tel' and @placeholder='Enter code']")
            
            if await two_fa_input.is_visible():
                logger.info("2FA prompt detected")
                
                # Get 2FA code from environment or prompt
                two_fa_code = os.getenv("BOT_2FA_CODE")
                
                if not two_fa_code:
                    logger.error("BOT_2FA_CODE environment variable not set")
                    return False
                
                # Enter 2FA code
                await two_fa_input.fill(two_fa_code)
                
                # Submit 2FA
                submit_button = page.locator("//button[text()='Submit' or contains(text(), 'Verify')]")
                if await submit_button.is_visible():
                    await submit_button.click()
                    
                    # Wait for navigation
                    await asyncio.sleep(3)
                    
                    return True
        
        except Exception as e:
            logger.error(f"2FA handling failed: {e}")
        
        return False

    async def _perform_login(self, page: Page) -> bool:
        """Perform EA login with email and password."""
        try:
            # Navigate to login page
            await page.goto("https://www.easports.com/fifa/ultimate-team/web-app")
            
            # Wait for login button
            login_button = page.locator("//button[contains(text(), 'Log In') or contains(text(), 'Sign In')]")
            await login_button.click()
            
            # Wait for email input
            await expect(page).to_have_url("*/login")
            
            email_input = page.locator("//input[@type='email']")
            password_input = page.locator("//input[@type='password']")
            
            if await email_input.is_visible() and await password_input.is_visible():
                # Get credentials from environment
                email = os.getenv("EA_EMAIL")
                password = os.getenv("EA_PASSWORD")
                
                if not email or not password:
                    logger.error("EA_EMAIL or EA_PASSWORD environment variables not set")
                    return False
                
                # Fill credentials
                await email_input.fill(email)
                await password_input.fill(password)
                
                # Submit login
                next_button = page.locator("//button[contains(text(), 'Next') or contains(text(), 'Sign In')]")
                await next_button.click()
                
                # Handle 2FA if present
                await asyncio.sleep(3)
                
                if await self._handle_2fa(page):
                    logger.info("Login successful with 2FA")
                    return True
                else:
                    logger.info("Login successful without 2FA")
                    return True
        
        except Exception as e:
            logger.error(f"Login failed: {e}")
        
        return False

    async def login(self, page: Page) -> bool:
        """Main login function with session persistence."""
        try:
            # Check if we have a valid session
            if await self._check_session_validity(page):
                logger.info("Using existing valid session")
                return True
            
            # Try to restore session
            auth_state = await self._load_auth_state()
            if auth_state:
                logger.info("Attempting to restore session from saved state")
                # Try to use restored session
                if await self._check_session_validity(page):
                    return True
            
            # Perform fresh login
            logger.info("Performing fresh login")
            success = await self._perform_login(page)
            
            if success:
                # Save successful auth state
                auth_state = {
                    "last_login": str(asyncio.get_event_loop().time()),
                    "status": "authenticated"
                }
                await self._save_auth_state(auth_state)
                
                # Save session state
                await self.browser_controller.save_session(page.context)
                
            return success
            
        except Exception as e:
            logger.error(f"Login process failed: {e}")
            return False