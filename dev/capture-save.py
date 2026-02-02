#!/usr/bin/env python3
"""Launch browser with network capture for Lose It GWT-RPC calls.
User interacts manually; script logs all service requests."""

import json, sys, time, os
from datetime import datetime
from playwright.sync_api import sync_playwright

PROFILE_DIR = os.path.expanduser("~/.openclaw/playwright-loseit")
SERVICE_URL = "https://www.loseit.com/web/service"
OUTPUT_FILE = os.path.expanduser("~/clawd/integrations/loseit/data/captured-save.json")

captured = []

def on_request(request):
    if SERVICE_URL in request.url and request.method == "POST":
        body = request.post_data or ""
        print(f"\n{'='*60}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] GWT-RPC REQUEST captured!")
        # Extract method name (field index 4 in pipe-delimited format)
        parts = body.split('|')
        if len(parts) > 10:
            # String table starts at index 3, method name is typically string #4
            num_strings = int(parts[2]) if parts[2].isdigit() else 0
            strings = parts[3:3+num_strings]
            method = strings[3] if len(strings) > 3 else "unknown"
            print(f"Method: {method}")
        print(f"Body length: {len(body)}")
        print(f"Body preview: {body[:300]}...")
        captured.append({
            "timestamp": datetime.now().isoformat(),
            "url": request.url,
            "method": request.method,
            "body": body,
            "headers": dict(request.headers)
        })
        # Save after each capture
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(captured, f, indent=2)
        print(f"Saved to {OUTPUT_FILE} ({len(captured)} calls total)")

def on_response(response):
    if SERVICE_URL in response.url:
        try:
            body = response.text()
        except:
            body = "<could not read>"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] RESPONSE: {response.status} ({len(body)} chars)")
        if captured:
            captured[-1]["response_status"] = response.status
            captured[-1]["response_body"] = body[:5000]
            with open(OUTPUT_FILE, 'w') as f:
                json.dump(captured, f, indent=2)

print("Launching browser with Lose It session...")
print(f"Profile: {PROFILE_DIR}")
print(f"Capturing GWT-RPC calls to: {SERVICE_URL}")
print(f"Output: {OUTPUT_FILE}")
print("\n>>> Log a food item manually. I'll capture everything. <<<")
print(">>> Press Ctrl+C when done. <<<\n")

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        PROFILE_DIR,
        headless=False,
        viewport={"width": 1280, "height": 900},
        args=["--disable-blink-features=AutomationControlled"]
    )
    
    page = context.pages[0] if context.pages else context.new_page()
    page.on("request", on_request)
    page.on("response", on_response)
    
    page.goto("https://www.loseit.com/#Food:date=%today%", wait_until="networkidle", timeout=30000)
    print(f"\nPage loaded: {page.url}")
    print("Waiting for your interactions... (Ctrl+C to stop)\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n\nDone! Captured {len(captured)} GWT-RPC calls.")
        print(f"Saved to: {OUTPUT_FILE}")
    finally:
        context.close()
