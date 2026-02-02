#!/usr/bin/env python3
"""Capture ALL POST requests from Lose It to find what endpoints food logging uses."""

import json, time, os
from datetime import datetime
from playwright.sync_api import sync_playwright

OUTPUT_FILE = os.path.expanduser("~/clawd/integrations/loseit/data/captured-all.json")
captured = []

def on_request(request):
    url = request.url
    # Capture any POST to loseit.com or their API domains
    if request.method == "POST" and ("loseit" in url or "cloudfront" in url):
        body = request.post_data or ""
        entry = {
            "timestamp": datetime.now().strftime('%H:%M:%S'),
            "url": url,
            "method": request.method,
            "body": body[:2000],
            "content_type": request.headers.get("content-type", ""),
        }
        captured.append(entry)
        print(f"[{entry['timestamp']}] POST {url[:80]}", flush=True)
        print(f"  Content-Type: {entry['content_type']}", flush=True)
        print(f"  Body: {body[:150]}...", flush=True)
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(captured, f, indent=2)

def on_response(response):
    url = response.url
    if ("loseit" in url or "cloudfront" in url):
        method = response.request.method
        if method in ("POST", "PUT", "PATCH"):
            try:
                body = response.text()
            except:
                body = ""
            print(f"[{datetime.now().strftime('%H:%M:%S')}] RESP {response.status} {url[:80]} ({len(body)} chars)", flush=True)
            # Also log any non-GET that returns data
            if captured:
                captured[-1]["response_status"] = response.status
                captured[-1]["response_body"] = body[:3000]
                with open(OUTPUT_FILE, 'w') as f:
                    json.dump(captured, f, indent=2)

# Also capture ALL requests (GET too) to see what URLs are hit
def on_any_request(request):
    url = request.url
    if "loseit" in url or "cloudfront" in url:
        if not url.endswith(('.js', '.css', '.png', '.jpg', '.gif', '.ico', '.woff', '.woff2', '.svg')):
            print(f"  [{request.method}] {url[:100]}", flush=True)

print("Launching fresh browser — capturing ALL loseit requests...", flush=True)

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=["--disable-blink-features=AutomationControlled"]
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    page.on("request", on_request)
    page.on("response", on_response)
    page.on("request", on_any_request)
    
    page.goto("https://www.loseit.com/", timeout=30000)
    print(f"\nPage loaded: {page.url}", flush=True)
    print("\n>>> Log in, then search & log a food to Snacks <<<", flush=True)
    print(">>> Tell me when done <<<\n", flush=True)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print(f"\nCaptured {len(captured)} POST requests.", flush=True)
        browser.close()
