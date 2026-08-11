import asyncio
import json
import re
import os

os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/root/.cache/ms-playwright'

import sys
sys.path.insert(0, '/usr/local/lib/hermes-agent/venv/lib/python3.11/site-packages')
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        page = await browser.new_page()
        
        # Navigate to Google Maps with search query in URL
        await page.goto('https://www.google.com/maps/search/windows+installer/', wait_until='networkidle', timeout=30000)
        print("Page loaded with search query")
        await asyncio.sleep(5)
        
        # Take screenshot
        await page.screenshot(path='maps_search.png')
        print("Screenshot saved")
        
        # Get the full HTML to understand structure
        html = await page.content()
        with open('page_html.html', 'w') as f:
            f.write(html)
        
        # Get text content
        page_text = await page.inner_text('body')
        with open('page_text.txt', 'w') as f:
            f.write(page_text)
        
        # Print first 3000 chars of text
        print("=== PAGE TEXT (first 3000 chars) ===")
        print(page_text[:3000])
        
        # Extract all text
        lines = [l.strip() for l in page_text.split('\n') if l.strip()]
        print("\n=== NON-EMPTY LINES ===")
        for line in lines[:50]:
            print(line)
        
        # Phone number patterns
        phone_pattern = re.compile(r'(\+1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}')
        phone_numbers = phone_pattern.findall(page_text)
        print(f"\n=== PHONE NUMBERS FOUND: {len(phone_numbers)} ===")
        for pn in phone_numbers:
            print(pn)
        
        # Also try scrolling
        for _ in range(5):
            await page.evaluate('window.scrollBy(0, 1000)')
            await asyncio.sleep(2)
        
        page_text2 = await page.inner_text('body')
        phone_numbers2 = phone_pattern.findall(page_text2)
        print(f"\n=== AFTER SCROLLING: PHONE NUMBERS FOUND: {len(phone_numbers2)} ===")
        for pn in phone_numbers2:
            print(pn)
        
        with open('page_text_scrolled.txt', 'w') as f:
            f.write(page_text2)
        
        await browser.close()

asyncio.run(main())
