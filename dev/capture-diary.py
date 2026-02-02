#!/usr/bin/env python3
"""Capture the diary query GWT-RPC call from Lose It!"""
import sys, json, time, os

VENV = os.path.expanduser("~/clawd/email-triage/venv")
sys.path.insert(0, f"{VENV}/lib/python3.12/site-packages")

from playwright.sync_api import sync_playwright

TOKEN_FILE = os.path.expanduser("~/.config/loseit/token")
OUTPUT_DIR = os.path.expanduser("~/clawd/integrations/loseit/data/captured-requests")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_token():
    with open(TOKEN_FILE) as f:
        return f.read().strip()

captured = []
counter = [0]

def on_request(request):
    if "service" in request.url and request.method == "POST":
        body = request.post_data or ""
        if "gwt-rpc" in (request.headers.get("content-type", "") or ""):
            counter[0] += 1
            idx = counter[0]
            parts = body.split("|")
            label = "unknown"
            for i, p in enumerate(parts):
                if "LoseItRemoteService" in p and i+1 < len(parts):
                    label = parts[i+1]
                    break
            entry = {"body": body, "label": label, "idx": idx}
            captured.append(entry)
            fname = f"{OUTPUT_DIR}/{idx:03d}_{label}.txt"
            with open(fname, "w") as f:
                f.write(body)
            print(f"  📥 [{idx}] {label} ({len(body)} chars)", flush=True)

def on_response(response):
    if "service" in response.url and response.request.method == "POST":
        body = response.request.post_data or ""
        if "gwt-rpc" in (response.request.headers.get("content-type", "") or ""):
            try:
                resp_text = response.text()
                for entry in reversed(captured):
                    if entry["body"] == body and "response" not in entry:
                        entry["response"] = resp_text
                        fname = f"{OUTPUT_DIR}/{entry['idx']:03d}_{entry['label']}_resp.txt"
                        with open(fname, "w") as f:
                            f.write(resp_text)
                        print(f"  📤 [{entry['idx']}] {entry['label']} resp ({len(resp_text)} chars)", flush=True)
                        break
            except Exception as e:
                print(f"  ⚠️ {e}", flush=True)

def main():
    token = load_token()
    print(f"[capture] Token: {len(token)} chars", flush=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # visible for debugging
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        
        context.add_cookies([
            {"name": "liauth", "value": token, "domain": "www.loseit.com", "path": "/"},
            {"name": "fn_auth", "value": token, "domain": "www.loseit.com", "path": "/"},
        ])
        
        page = context.new_page()
        page.on("request", on_request)
        page.on("response", on_response)
        
        print("[capture] Loading loseit.com...", flush=True)
        page.goto("https://www.loseit.com/", wait_until="networkidle", timeout=60000)
        time.sleep(3)
        print(f"[capture] Title: {page.title()}", flush=True)
        
        # The initial page load should trigger diary query calls
        print(f"[capture] Captured {len(captured)} calls so far", flush=True)
        
        # Click through days to capture different date queries
        # Look for next/prev day buttons
        try:
            next_btn = page.query_selector('text=">>"')
            if not next_btn:
                next_btn = page.query_selector('[title="Next Day"]')
            if next_btn:
                print("[capture] Clicking next day...", flush=True)
                next_btn.click()
                time.sleep(3)
                print(f"[capture] After next: {len(captured)} captured", flush=True)
        except Exception as e:
            print(f"[capture] Next day error: {e}", flush=True)
        
        # Wait a bit for any delayed requests
        time.sleep(5)
        
        print(f"\n[capture] === SUMMARY ===", flush=True)
        print(f"Total captured: {len(captured)} GWT requests", flush=True)
        for c in captured:
            has_resp = "✅" if "response" in c else "❌"
            print(f"  {c['idx']:03d} {has_resp} {c['label']} ({len(c['body'])} chars)", flush=True)
        
        with open(f"{OUTPUT_DIR}/diary_capture.json", "w") as f:
            json.dump(captured, f, indent=2, default=str)
        
        context.close()
        browser.close()
    print("[capture] Done!", flush=True)

if __name__ == "__main__":
    main()
