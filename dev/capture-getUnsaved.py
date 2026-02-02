#!/usr/bin/env python3
"""Capture getUnsavedFoodLogEntry by intercepting network traffic while interacting with Lose It."""
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
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        
        # Set auth cookies
        context.add_cookies([
            {"name": "liauth", "value": token, "domain": "www.loseit.com", "path": "/"},
            {"name": "fn_auth", "value": token, "domain": "www.loseit.com", "path": "/"},
        ])
        
        page = context.new_page()
        page.on("request", on_request)
        page.on("response", on_response)
        
        print("[capture] Loading loseit.com...", flush=True)
        page.goto("https://www.loseit.com/", wait_until="networkidle", timeout=60000)
        time.sleep(5)
        print(f"[capture] Title: {page.title()}", flush=True)
        
        # Screenshot initial state
        page.screenshot(path=f"{OUTPUT_DIR}/cap_00_loaded.png")
        
        # The Lose It GWT app uses complex widgets. Let's look for ALL inputs and clickable elements
        # First, let's see what's on the page
        all_inputs = page.query_selector_all('input')
        print(f"[capture] Found {len(all_inputs)} inputs:", flush=True)
        for i, inp in enumerate(all_inputs):
            try:
                ph = inp.get_attribute("placeholder") or ""
                typ = inp.get_attribute("type") or ""
                cls = inp.get_attribute("class") or ""
                vis = inp.is_visible()
                print(f"  input[{i}] type={typ} vis={vis} ph='{ph}' cls='{cls[:50]}'", flush=True)
            except:
                pass
        
        # Try clicking on the Breakfast area / "+" button to open food search
        # GWT apps render as div-based UI. Look for text like "Breakfast", "search", "add"
        breakfast_els = page.query_selector_all('text="Breakfast"')
        add_buttons = page.query_selector_all('[class*="add"], [class*="Add"], [class*="plus"]')
        print(f"[capture] 'Breakfast' elements: {len(breakfast_els)}", flush=True)
        print(f"[capture] Add buttons: {len(add_buttons)}", flush=True)
        
        # Let's just look at visible text on the page
        body_text = page.inner_text('body')
        # Print first 2000 chars
        print(f"[capture] Page text (first 2000):", flush=True)
        print(body_text[:2000], flush=True)
        
        # Try to find the search input by looking at all elements with role or aria labels
        search_els = page.query_selector_all('[role="search"], [role="searchbox"], [aria-label*="search" i], [placeholder*="search" i]')
        print(f"\n[capture] Search elements: {len(search_els)}", flush=True)
        
        # GWT often uses gwt-TextBox class
        gwt_inputs = page.query_selector_all('.gwt-TextBox, .gwt-SuggestBox')
        print(f"[capture] GWT text boxes: {len(gwt_inputs)}", flush=True)
        for i, inp in enumerate(gwt_inputs):
            try:
                vis = inp.is_visible()
                bb = inp.bounding_box()
                print(f"  gwt[{i}] vis={vis} box={bb}", flush=True)
            except:
                pass
        
        # Try clicking near the top of the food log area
        # Based on Lose It layout: search bar is typically near the top of each meal section
        # Let's try pressing / or Ctrl+F which might open search
        page.keyboard.press("Slash")
        time.sleep(2)
        page.screenshot(path=f"{OUTPUT_DIR}/cap_01_slash.png")
        
        # Check for new inputs
        gwt_inputs2 = page.query_selector_all('.gwt-TextBox, .gwt-SuggestBox, input:visible')
        print(f"[capture] After slash - visible inputs: {len(gwt_inputs2)}", flush=True)
        
        # Try clicking on specific coordinates where the search bar typically is
        # (in the Lose It web app, the search bar is usually at top of the diary)
        page.click("body", position={"x": 640, "y": 200})
        time.sleep(1)
        page.screenshot(path=f"{OUTPUT_DIR}/cap_02_click.png")
        
        # Look for the gwt-TextBox again
        gwt_inputs3 = page.query_selector_all('.gwt-TextBox')
        print(f"[capture] After click - gwt text boxes: {len(gwt_inputs3)}", flush=True)
        for i, inp in enumerate(gwt_inputs3):
            try:
                vis = inp.is_visible()
                bb = inp.bounding_box()
                ph = inp.get_attribute("placeholder") or ""
                print(f"  gwt[{i}] vis={vis} box={bb} ph='{ph}'", flush=True)
                if vis and bb:
                    inp.click()
                    time.sleep(0.5)
                    inp.type("banana", delay=80)
                    time.sleep(3)
                    page.screenshot(path=f"{OUTPUT_DIR}/cap_03_typed.png")
                    print(f"[capture] Typed 'banana' in gwt[{i}]", flush=True)
                    print(f"[capture] Captured so far: {len(captured)}", flush=True)
                    
                    # Press Enter to confirm search
                    inp.press("Enter")
                    time.sleep(4)
                    page.screenshot(path=f"{OUTPUT_DIR}/cap_04_enter.png")
                    print(f"[capture] After Enter: {len(captured)} captured", flush=True)
                    
                    # Now look for search results and click one
                    # Check for new visible elements
                    banana_els = page.query_selector_all('text=/[Bb]anana/')
                    print(f"[capture] Banana elements: {len(banana_els)}", flush=True)
                    
                    for j, el in enumerate(banana_els[:5]):
                        try:
                            text = el.inner_text()[:80]
                            vis = el.is_visible()
                            tag = el.evaluate("el => el.tagName")
                            print(f"  banana[{j}] <{tag}> vis={vis} '{text}'", flush=True)
                        except:
                            pass
                    
                    # Click the first visible banana result that's not the input itself
                    for el in banana_els:
                        try:
                            if el.is_visible():
                                tag = el.evaluate("el => el.tagName")
                                text = el.inner_text()[:80]
                                if tag != "INPUT" and "Medium" in text:
                                    print(f"[capture] Clicking: '{text}'", flush=True)
                                    el.click()
                                    time.sleep(3)
                                    page.screenshot(path=f"{OUTPUT_DIR}/cap_05_clicked_result.png")
                                    print(f"[capture] After click result: {len(captured)} captured", flush=True)

                                    # Click the green "Add Food" button in the modal
                                    try:
                                        add_btn = page.query_selector('text="Add Food"')
                                        if add_btn and add_btn.is_visible():
                                            print("[capture] Clicking Add Food...", flush=True)
                                            add_btn.click(force=True)
                                            time.sleep(5)
                                            page.screenshot(path=f"{OUTPUT_DIR}/cap_06_added.png")
                                            print(f"[capture] After Add Food: {len(captured)} captured", flush=True)
                                    except Exception as e:
                                        print(f"[capture] Add Food click error: {e}", flush=True)

                                    break
                        except Exception as e:
                            print(f"  click err: {e}", flush=True)
                    
                    break
            except Exception as e:
                print(f"  gwt input error: {e}", flush=True)
        
        time.sleep(3)
        
        print(f"\n[capture] === SUMMARY ===", flush=True)
        print(f"Total captured: {len(captured)} GWT requests", flush=True)
        for c in captured:
            has_resp = "✅" if "response" in c else "❌"
            print(f"  {c['idx']:03d} {has_resp} {c['label']} ({len(c['body'])} chars)", flush=True)
        
        # Save all
        with open(f"{OUTPUT_DIR}/all_captured.json", "w") as f:
            json.dump(captured, f, indent=2, default=str)
        
        context.close()
        browser.close()
    print("[capture] Done!", flush=True)

if __name__ == "__main__":
    main()
