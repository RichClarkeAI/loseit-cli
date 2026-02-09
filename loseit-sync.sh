#!/usr/bin/env bash
# loseit-sync.sh — Download Lose It! export using Brave cookies via Playwright
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$SCRIPT_DIR/data"
EXPORT_DIR="$DATA_DIR/export"
ZIP_FILE="$DATA_DIR/loseit-export.zip"
SYNC_LOG="$DATA_DIR/last-sync.json"
VENV="$HOME/clawd/email-triage/venv"
PLAYWRIGHT_PROFILE="$HOME/.openclaw/playwright-loseit"

mkdir -p "$DATA_DIR" "$EXPORT_DIR"

log_result() {
    local status="$1" msg="$2"
    cat > "$SYNC_LOG" <<EOF
{
  "status": "$status",
  "message": "$msg",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "timestamp_local": "$(date +%Y-%m-%dT%H:%M:%S%z)"
}
EOF
}

echo "[loseit-sync] Starting export download..."

"$VENV/bin/python3" - "$ZIP_FILE" "$PLAYWRIGHT_PROFILE" <<'PYEOF'
import sys, json, time, os

zip_path = sys.argv[1]
playwright_profile = sys.argv[2]

from playwright.sync_api import sync_playwright
import requests

EXPORT_URL = "https://www.loseit.com/export/data"

print("[loseit-sync] Launching Playwright (dedicated profile) to grab cookies...")

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        playwright_profile,
        headless=True,
        args=["--no-sandbox", "--disable-gpu", "--no-first-run"],
        timeout=30000,
    )
    # Navigate to loseit to ensure cookies are fresh
    page = context.pages[0] if context.pages else context.new_page()
    page.goto("https://www.loseit.com", wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)

    # Extract cookies
    cookies = context.cookies("https://www.loseit.com")
    context.close()

if not cookies:
    print("[loseit-sync] ERROR: No cookies found for loseit.com", file=sys.stderr)
    sys.exit(1)

print(f"[loseit-sync] Got {len(cookies)} cookies, downloading export...")

# Build cookie dict for requests
cookie_dict = {c["name"]: c["value"] for c in cookies}

resp = requests.get(EXPORT_URL, cookies=cookie_dict, timeout=60, allow_redirects=True)

if resp.status_code != 200:
    print(f"[loseit-sync] ERROR: HTTP {resp.status_code} from export endpoint", file=sys.stderr)
    sys.exit(2)

content_type = resp.headers.get("content-type", "")
if "zip" not in content_type and len(resp.content) < 1000:
    print(f"[loseit-sync] ERROR: Response doesn't look like a zip (content-type: {content_type}, size: {len(resp.content)})", file=sys.stderr)
    sys.exit(3)

with open(zip_path, "wb") as f:
    f.write(resp.content)

print(f"[loseit-sync] Saved {len(resp.content)} bytes to {zip_path}")
PYEOF

PYTHON_EXIT=$?
if [ $PYTHON_EXIT -ne 0 ]; then
    log_result "error" "Python script failed with exit code $PYTHON_EXIT"
    echo "[loseit-sync] FAILED (exit $PYTHON_EXIT)"
    exit 1
fi

echo "[loseit-sync] Unzipping export..."
unzip -o "$ZIP_FILE" -d "$EXPORT_DIR"

log_result "success" "Export downloaded and extracted ($(du -sh "$ZIP_FILE" | cut -f1))"
echo "[loseit-sync] Done! Data in $EXPORT_DIR"
