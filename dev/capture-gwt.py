#!/usr/bin/env python3
"""Capture the real getUnsavedFoodLogEntry GWT-RPC request from Lose It! web app.
Strategy: type into the Breakfast search bar, wait for searchFoods GWT call,
then click a result to trigger getUnsavedFoodLogEntry."""
import sys, json, time, os

VENV = os.path.expanduser("~/clawd/email-triage/venv")
sys.path.insert(0, f"{VENV}/lib/python3.12/site-packages")

from playwright.sync_api import sync_playwright

PROFILE_DIR = os.path.expanduser("~/.openclaw/playwright-loseit")
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
            print(f"  📥 [{idx}] {label} ({len(body)} chars)")

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
                        print(f"  📤 [{entry['idx']}] {entry['label']} resp ({len(resp_text)} chars)")
                        break
            except Exception as e:
                print(f"  ⚠️ {e}")

def main():
    token = load_token()
    print(f"[capture] Token: {len(token)} chars")
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            PROFILE_DIR, headless=True, viewport={"width": 1280, "height": 900},
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        browser.add_cookies([
            {"name": "liauth", "value": token, "domain": "www.loseit.com", "path": "/"},
            {"name": "fn_auth", "value": token, "domain": "www.loseit.com", "path": "/"},
        ])
        page.on("request", on_request)
        page.on("response", on_response)
        
        print("[capture] Loading loseit.com...")
        page.goto("https://www.loseit.com/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(8)
        print(f"[capture] Title: {page.title()}")
        
        # Find all search inputs with placeholder "search & add food"
        search_inputs = page.query_selector_all('input')
        food_searches = []
        for inp in search_inputs:
            try:
                ph = inp.get_attribute("placeholder") or ""
                if "search" in ph.lower() and "food" in ph.lower():
                    food_searches.append(inp)
                    print(f"  Found food search: placeholder='{ph}'")
            except:
                pass
        
        print(f"[capture] Found {len(food_searches)} food search inputs")
        
        if food_searches:
            # Use the first one (Breakfast)
            search = food_searches[0]
            print("[capture] Clicking Breakfast search bar...")
            search.click(force=True)
            time.sleep(0.5)
            
            # Type character by character to trigger search
            print("[capture] Typing 'banana'...")
            search.type("banana", delay=100)
            time.sleep(2)
            
            page.screenshot(path=f"{OUTPUT_DIR}/step1_typing.png")
            
            # Press Enter to search
            search.press("Enter")
            time.sleep(4)
            
            page.screenshot(path=f"{OUTPUT_DIR}/step2_enter.png")
            print(f"[capture] After Enter - captured {len(captured)} requests so far")
            
            # Check if search triggered any GWT calls
            search_calls = [c for c in captured if "search" in c["label"].lower()]
            print(f"[capture] Search-related calls: {len(search_calls)}")
            
            # If no search GWT call, maybe it uses a different mechanism
            # Try Tab key or clicking a suggestion
            if not search_calls:
                print("[capture] No search GWT call yet, trying Tab...")
                search.press("Tab")
                time.sleep(3)
                page.screenshot(path=f"{OUTPUT_DIR}/step3_tab.png")
            
            # Look for any dropdown/popup results
            time.sleep(2)
            
            # Try to find result elements - Lose It uses GWT widgets
            # Look for elements that appeared after search
            all_text = page.inner_text('body')
            
            # Check for banana mentions
            if 'anana' in all_text:
                print("[capture] 'banana' found in page text - results may be showing")
                
                # Try to find and click a result
                # GWT apps often use table rows or divs
                banana_rows = page.query_selector_all('tr:has-text("anana"), div:has-text("Banana")')
                print(f"[capture] Found {len(banana_rows)} banana elements")
                
                for i, row in enumerate(banana_rows[:10]):
                    try:
                        text = row.inner_text().strip()[:80]
                        vis = row.is_visible()
                        tag = row.evaluate("el => el.tagName")
                        cls = row.get_attribute("class") or ""
                        print(f"  [{i}] <{tag}> vis={vis} cls={cls[:30]} text='{text}'")
                    except:
                        pass
                
                # Click visible banana results
                for row in banana_rows:
                    try:
                        if row.is_visible():
                            text = row.inner_text().strip()[:60]
                            if "anana" in text and len(text) < 200:
                                print(f"[capture] Clicking: '{text[:50]}'")
                                row.click(force=True)
                                time.sleep(4)
                                page.screenshot(path=f"{OUTPUT_DIR}/step4_clicked.png")
                                print(f"[capture] After click - captured {len(captured)} requests")
                                break
                    except Exception as e:
                        print(f"  click err: {e}")
            else:
                print("[capture] No banana text found on page")
                # Save page HTML for debugging
                html = page.content()
                with open(f"{OUTPUT_DIR}/page_debug.html", "w") as f:
                    f.write(html)
                print(f"[capture] Page HTML saved ({len(html)} chars)")
        
        # Final wait
        time.sleep(3)
        
        print(f"\n[capture] === SUMMARY ===")
        print(f"Total captured: {len(captured)} GWT requests")
        for c in captured:
            has_resp = "✅" if "response" in c else "❌"
            print(f"  {c['idx']:03d} {has_resp} {c['label']} ({len(c['body'])} chars)")
        
        with open(f"{OUTPUT_DIR}/all_captured.json", "w") as f:
            json.dump([{k:v for k,v in c.items() if k != "response" or True} for c in captured], 
                     f, indent=2, default=str)
        
        browser.close()
    print("[capture] Done!")

if __name__ == "__main__":
    main()
