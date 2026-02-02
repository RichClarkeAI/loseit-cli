#!/usr/bin/env python3
"""Launch FRESH browser (no persistent profile) with network capture for Lose It GWT-RPC calls.
User logs in manually, then logs food. Script captures all service requests."""

import json, sys, time, os
from datetime import datetime
from playwright.sync_api import sync_playwright

SERVICE_URL = "https://www.loseit.com/web/service"
OUTPUT_FILE = os.path.expanduser("~/clawd/integrations/loseit/data/captured-save.json")

captured = []

def on_request(request):
    if SERVICE_URL in request.url and request.method == "POST":
        body = request.post_data or ""
        parts = body.split('|')
        num_strings = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        strings = parts[3:3+num_strings]
        method = strings[3] if len(strings) > 3 else "unknown"
        print(f"\n{'='*60}", flush=True)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] GWT-RPC: {method}", flush=True)
        print(f"Body length: {len(body)}", flush=True)
        print(f"Preview: {body[:200]}...", flush=True)
        captured.append({
            "timestamp": datetime.now().isoformat(),
            "method": method,
            "body": body,
            "headers": dict(request.headers)
        })
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(captured, f, indent=2)
        print(f"Total captured: {len(captured)}", flush=True)

def on_response(response):
    if SERVICE_URL in response.url:
        try:
            body = response.text()
        except:
            body = ""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Response: {response.status} ({len(body)} chars)", flush=True)
        if captured:
            captured[-1]["response_status"] = response.status
            captured[-1]["response_body"] = body[:5000]
            with open(OUTPUT_FILE, 'w') as f:
                json.dump(captured, f, indent=2)

print("Launching FRESH browser (you'll need to log in)...", flush=True)
print(f"Capturing: {SERVICE_URL}", flush=True)
print(f"Output: {OUTPUT_FILE}", flush=True)

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
    
    page.goto("https://www.loseit.com/", timeout=30000)
    print(f"\nPage loaded: {page.url}", flush=True)
    print("\n>>> 1) Log in to Lose It", flush=True)
    print(">>> 2) Search & log a food item (Snacks is safest)", flush=True)
    print(">>> 3) Tell me when done — I'll read the captures <<<\n", flush=True)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print(f"\nCaptured {len(captured)} GWT-RPC calls.", flush=True)
        browser.close()
