import asyncio
import json
import re
import os

os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/root/.cache/ms-playwright'

# Try different import paths
try:
    from playwright.async_api import async_playwright
except ImportError:
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
        
        # Navigate to Google Maps
        await page.goto('https://www.google.com/maps', wait_until='networkidle', timeout=30000)
        print("Page loaded")
        await asyncio.sleep(3)
        
        # Take screenshot for debugging
        await page.screenshot(path='maps_initial.png')
        print("Screenshot taken")
        
        # Look for the search box
        search_box = await page.query_selector('input[aria-label="Search Google Maps"]')
        if not search_box:
            search_box = await page.query_selector('#searchboxinput')
        if not search_box:
            search_box = await page.query_selector('input[name="q"]')
        if not search_box:
            inputs = await page.query_selector_all('input')
            for inp in inputs:
                placeholder = await inp.get_attribute('placeholder')
                aria = await inp.get_attribute('aria-label')
                if placeholder or aria:
                    search_box = inp
                    print(f"Found input: placeholder={placeholder}, aria={aria}")
                    break
        
        if search_box:
            await search_box.click()
            await asyncio.sleep(1)
            await search_box.fill('windows installer')
            await asyncio.sleep(1)
            await page.keyboard.press('Enter')
            print("Search submitted")
            
            # Wait for results
            await asyncio.sleep(5)
            await page.wait_for_timeout(3000)
            
            # Take screenshot of results
            await page.screenshot(path='maps_results.png')
            print("Results screenshot taken")
            
            # Get page content
            page_text = await page.inner_text('body')
            
            # Save raw text
            with open('page_text.txt', 'w') as f:
                f.write(page_text)
            
            # Extract phone numbers with context
            # Phone number patterns
            phone_patterns = [
                r'[\+]?1[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}',
                r'\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}',
                r'\d{3}[\s.-]\d{3}[\s.-]\d{4}',
            ]
            
            # Try scrolling the results panel
            try:
                feed = await page.query_selector('[role="feed"]')
                if feed:
                    for _ in range(5):
                        await feed.evaluate('el => el.scrollTop = el.scrollHeight')
                        await asyncio.sleep(2)
            except:
                pass
            
            # Also scroll the page
            for _ in range(3):
                await page.evaluate('window.scrollBy(0, 800)')
                await asyncio.sleep(2)
            
            # Get updated content
            page_text = await page.inner_text('body')
            with open('page_text_full.txt', 'w') as f:
                f.write(page_text)
            
            # Extract business names and phone numbers
            lines = [l.strip() for l in page_text.split('\n') if l.strip()]
            
            phone_data = []
            current_business = ""
            
            for i, line in enumerate(lines):
                # Check if line has a phone number
                has_phone = False
                for pattern in phone_patterns:
                    if re.search(pattern, line):
                        has_phone = True
                        phone_match = re.search(pattern, line)
                        phone = phone_match.group()
                        # Look backwards for business name
                        biz_name = current_business
                        if i > 0 and not biz_name:
                            biz_name = lines[i-1]
                        phone_data.append({
                            'business': biz_name,
                            'phone': phone,
                            'line': line
                        })
                        print(f"Found: {biz_name} - {phone}")
                        break
                
                # Track potential business names
                if not has_phone and len(line) > 3 and len(line) < 80:
                    if not any(x in line.lower() for x in ['call', 'direction', 'website', 'save', 'share', 'review', 'route']):
                        if re.match(r'^[A-Za-z0-9\s\&\'\.\-]+$', line):
                            current_business = line
            
            print(f"\nTotal phone numbers found: {len(phone_data)}")
            
            # Save results
            with open('phone_numbers.json', 'w') as f:
                json.dump(phone_data, f, indent=2)
            
            # Also try clicking on each result to get more details
            # Find result items
            result_items = await page.query_selector_all('[role="article"], a[href*="/maps/place"]')
            print(f"Found {len(result_items)} result items")
            
        else:
            print("Could not find search box")
            await page.screenshot(path='maps_no_search.png')
        
        await browser.close()

asyncio.run(main())
