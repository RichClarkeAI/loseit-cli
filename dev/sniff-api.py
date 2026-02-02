#!/usr/bin/env python3
"""Sniff Lose It! web app API calls to reverse-engineer food search + logging endpoints."""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_DIR = Path.home() / ".openclaw" / "playwright-loseit"
HOME_URL = "https://www.loseit.com/"

captured = []

def on_request(request):
    url = request.url
    # Filter for API calls (skip static assets)
    if any(x in url for x in ['.js', '.css', '.png', '.jpg', '.svg', '.woff', 'favicon', 'google', 'facebook', 'analytics', 'sentry']):
        return
    if 'loseit.com' in url or 'api' in url.lower():
        entry = {
            "method": request.method,
            "url": url,
            "headers": dict(request.headers),
        }
        try:
            if request.post_data:
                entry["post_data"] = request.post_data
        except:
            pass
        captured.append(entry)
        print(f"[REQ] {request.method} {url}")

def on_response(response):
    url = response.url
    if any(x in url for x in ['.js', '.css', '.png', '.jpg', '.svg', '.woff', 'favicon', 'google', 'facebook', 'analytics', 'sentry']):
        return
    if 'loseit.com' in url or 'api' in url.lower():
        status = response.status
        content_type = response.headers.get('content-type', '')
        print(f"[RES] {status} {url} ({content_type})")
        
        # Try to capture JSON response bodies for API endpoints
        if 'json' in content_type or 'api' in url:
            try:
                body = response.json()
                for c in captured:
                    if c['url'] == url and 'response' not in c:
                        c['response_status'] = status
                        c['response_body'] = body
                        break
            except:
                pass

def main():
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=True,
            viewport={"width": 1280, "height": 800},
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.on("request", on_request)
        page.on("response", on_response)
        page.set_default_timeout(30000)

        print(f"[sniff] Loading {HOME_URL}...")
        page.goto(HOME_URL, wait_until="networkidle")
        time.sleep(3)
        
        print(f"\n[sniff] Page loaded. Captured {len(captured)} requests so far.")
        print("[sniff] Now simulating a food search...")
        
        # Try to find any search input and type a query
        # First let's just see what API calls the page makes on load
        
        # Scroll to trigger lazy loading
        page.mouse.wheel(0, 500)
        time.sleep(2)
        
        # Look for search inputs
        inputs = page.locator("input[type='text'], input[type='search'], input[placeholder*='search' i], input[placeholder*='food' i]")
        count = inputs.count()
        print(f"[sniff] Found {count} search-like inputs")
        
        if count > 0:
            inp = inputs.first
            print(f"[sniff] Clicking first input and searching 'chicken breast'...")
            inp.click()
            time.sleep(0.5)
            inp.fill("chicken breast")
            time.sleep(3)  # Wait for API calls
            
            print(f"\n[sniff] After search, captured {len(captured)} total requests.")
        
        # Also check for auth tokens in cookies/localStorage
        print("\n[sniff] Checking auth tokens...")
        cookies = context.cookies("https://www.loseit.com")
        auth_cookies = [c for c in cookies if any(x in c['name'].lower() for x in ['auth', 'token', 'session', 'jwt'])]
        print(f"[sniff] Auth-looking cookies: {json.dumps([{'name': c['name'], 'value': c['value'][:30]+'...'} for c in auth_cookies], indent=2)}")
        
        # Check localStorage
        local_storage = page.evaluate("""() => {
            const items = {};
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key.toLowerCase().includes('auth') || key.toLowerCase().includes('token') || key.toLowerCase().includes('user') || key.toLowerCase().includes('session')) {
                    items[key] = localStorage.getItem(key).substring(0, 100);
                }
            }
            return items;
        }""")
        print(f"[sniff] Auth-looking localStorage: {json.dumps(local_storage, indent=2)}")
        
        context.close()
    
    # Save captured requests
    out_path = Path(__file__).parent / "data" / "api-sniff.json"
    with open(out_path, "w") as f:
        json.dump(captured, f, indent=2, default=str)
    print(f"\n[sniff] Saved {len(captured)} captured requests to {out_path}")


if __name__ == "__main__":
    main()
