#!/usr/bin/env python3

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import json

class BrowserController:
    def __init__(self, config_path: str = "./config/config.json"):
        self.config = self._load_config(config_path)
        self.user_data_dir = Path(self.config.get('browser', {}).get('user_data_dir', '.gsd/browser-state/'))
        self.headless = self.config.get('browser', {}).get('headless', False)
        self.slow_mo = self.config.get('browser', {}).get('slow_mo', 500)
        self.viewport = self.config.get('browser', {}).get('viewport', {'width': 1280, 'height': 720})

    def _load_config(self, path: str) -> dict:
        try:
            with open(path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}  # Return empty config or handle error

    async def launch(self) -> async_playwright أيض)--> async_playwright.Asyncิร์افront:
        browser = await async_playwright().start()
        try:
            context = await browser.new_context(
                user_data_dir=str(self.user_data_dir),
                headless=self.headless,
                slow_mo=self.slow_mo,
                viewport=self.viewport
            )
            return context
        except PlaywrightTimeout:
            raise Exception("Launch timed out")

    async def new_context(self) -> async_playwright.AsyncContext:
        return await self.launch().new_context()

    async def save_session(self, context: async_playwright.AsyncContext, path: str = None):
        if not path:
            path = str(self.user_data_dir / "session.json")
        try:
            await context.storageembly_store()
            await context.cookies().save(str(path))
            await context.storage.save(str(path))
        except Exception as e:
            raise Exception(f"Session save failed: {str(e)}")

    async def restore_session(self, context: async_playwright.AsyncContext, path: str = None):
        if not path:
            path = str(self.user_data_dir / "session.json")
        try:
            cookies = await context.cookies().load(str(path))  # Handle cookies
            storage = await context.storage.load(str(path))    # Handle localStorage
            await context.add_cookies(cookies)       # Restore cookies
            await context.storage合并(storage)      # Restore storage
        except Exception as e:
            raise Exception(f"Session restore failed: {str(e)}")

    async def close(self):
        await self.browser.close()

if __name__ == "__main__":
    # Test harness
    async def main():
        controller = BrowserController()
        context = await controller.launch()
        await controller.save_session(context)
        await controller.restore_session(context)
        await controller.close()

    asyncio.run(main())