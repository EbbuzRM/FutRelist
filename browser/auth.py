#!/usr/bin/env python3

import asyncio
import logging
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout
from pathlib import Path
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EAAuth:
    def __init__(self):
        self.email = os.getenv('EMAIL')
        self.password = os.getenv('PASSWORD')
        self.bot_2fa_code = os.getenv('BOT_2FA_CODE')
        self.is_headless = os.getenv('PLAYWRIGHT_HEADLESS', 'false').lower() == 'true'
        
        if not self.email:
            raise ValueError("EMAIL environment variable is required")
        if not self.password:
            raise ValueError("PASSWORD environment variable is required")
        if not self.is_headless and not self.bot_2fa_code:
            logger.warning("Running headed mode without BOT_2FA_CODE - will require manual 2FA entry")

    async def login(self, page: Page) -> bool:
        """
        Perform EA login with 2FA support
        Returns True if successful, False if failed
        """
        try:
            logger.info("Starting EA authentication flow")
            
            # Navigate to EA login page
            await page.goto("https://www.ea.com/login")
            await page.wait_for_load_state('networkidle')
            logger.info("Navigated to EA login page")
            
            # Fill email and click Next
            email_input = page.get_by_role('textbox', name='email')
            await email_input.fill(self.email)
            await email_input.press('Enter')
            logger.info(f"Email filled: {self.email}")
            
            # Wait for password page to load
            await page.wait_for_load_state('networkidle')
            
            # Fill password and click Sign In
            password_input = page.get_by_role('textbox', name='password')
            await password_input.fill(self.password)
            sign_in_button = page.get_by_role('button', name='Sign In')
            await sign_in_button.click()
            logger.info("Password filled and Sign In clicked")
            
            # Handle 2FA if present
            if await self._handle_2fa(page):
                logger.info("2FA completed successfully")
            else:
                logger.info("No 2FA required or already handled")
            
            # Wait for navigation to Transfer List or home page
            try:
                # Wait for either Transfer List page or home page
                await page.wait_for_url(['https://www.ea.com/fifa/transfer-list', 'https://www.ea.com/'], 
                                      timeout=30000)
                logger.info("Successfully navigated to authenticated page")
                return True
            except PlaywrightTimeout:
                # Check if we're on a page that indicates success
                current_url = page.url
                if 'fifa' in current_url or 'ea.com' in current_url:
                    logger.info(f"Successfully on page: {current_url}")
                    return True
                logger.error(f"Failed to navigate to expected page. Current URL: {current_url}")
                return False
                
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            return False

    async def _handle_2fa(self, page: Page) -> bool:
        """
        Handle 2FA authentication
        Returns True if 2FA was handled, False if 2FA not required or failed
        """
        logger.info("Checking for 2FA challenge...")
        
        # Look for 2FA indicators - common selectors for 2FA input
        selectors = [
            'input[autocomplete="one-time-code"]',
            'input[name="code"]',
            'input[placeholder*="code"]',
            'input[aria-label*="code"]',
            'input[type="text"]'
        ]
        
        2fa_input = None
        for selector in selectors:
            try:
                elements = page.query_selector_all(selector)
                for element in elements:
                    if element.is_visible():
                        2fa_input = element
                        break
                if 2fa_input:
                    break
            except:
                continue
        
        if not 2fa_input:
            logger.info("No 2FA input found - proceeding without 2FA")
            return False
        
        logger.info("2FA challenge detected")
        
        try:
            if self.is_headless:
                if not self.bot_2fa_code:
                    raise ValueError("BOT_2FA_CODE environment variable is required for headless mode")
                
                # Fill 2FA code automatically
                await 2fa_input.fill(self.bot_2fa_code)
                logger.info("2FA code filled from environment variable")
                
                # Click submit button
                submit_selectors = ['button[type="submit"]', 'button:has-text("Verify")', 'button:has-text("Submit")']
                submit_clicked = False
                
                for selector in submit_selectors:
                    submit_button = page.query_selector(selector)
                    if submit_button and submit_button.is_visible():
                        await submit_button.click()
                        submit_clicked = True
                        logger.info("2FA submit button clicked")
                        break
                
                if not submit_clicked:
                    # Press Enter on the input as fallback
                    await 2fa_input.press('Enter')
                    logger.info("Pressed Enter to submit 2FA code")
                
            else:
                # Headed mode - wait for manual entry
                logger.info("Headed mode detected - waiting for manual 2FA code entry...")
                await page.wait_for_selector('input[autocomplete="one-time-code"]', timeout=120000)
                logger.info("Manual 2FA entry completed")
            
            # Wait a bit for 2FA to process
            await asyncio.sleep(2)
            return True
            
        except Exception as e:
            logger.error(f"2FA handling failed: {str(e)}")
            return False