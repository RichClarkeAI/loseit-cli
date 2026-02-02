#!/usr/bin/env python3
"""Lose It! Food Logger via GWT-RPC

Unofficial CLI for logging foods to Lose It via reverse-engineered GWT-RPC API.

Usage:
    python loseit-log.py "banana" --search            # Search for food
    python loseit-log.py "banana" -m snacks --pick 1  # Log to snacks, 1st result
    python loseit-log.py "eggs" -m breakfast --pick 1 --servings 2
    python loseit-log.py "salmon" -m dinner --pick 1 --date 2026-02-01
    python loseit-log.py --replay                     # Test auth with Chobani yogurt

Authentication:
    Requires JWT token saved to ~/.config/loseit/token
    Get it from browser cookies (liauth value) after logging into loseit.com

How it works:
    1. searchFoods(query) → returns list of foods from Lose It database
    2. getUnsavedFoodLogEntry(food_pk) → returns nutrient template for food
    3. updateFoodLogEntry(entry, meal, date, servings) → saves to diary

Notes:
    - GWT-RPC protocol is complex; this implementation is heuristic but works
    - Byte arrays must be reversed (GWT serialization quirk)
    - Server only accepts 9 core nutrient ordinals (0,2,3,8,9,10,11,12,13)
    - Day keys come from getUnsavedFoodLogEntry response, not getInitializationData

⚠️  Unofficial & unsupported - use at your own risk!
"""

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone, timedelta, date

try:
    import requests
except ImportError:
    venv_path = os.path.expanduser("~/clawd/email-triage/venv/lib/python3.12/site-packages")
    if os.path.exists(venv_path):
        sys.path.insert(0, venv_path)
    import requests

# ─── Constants ───────────────────────────────────────────────────────────────

SERVICE_URL = "https://www.loseit.com/web/service"
BASE_URL = "https://d3hsih69yn4d89.cloudfront.net/web/"
POLICY_HASH = "5ED2771F63B26294E45551B2D697E7B0"
STRONG_NAME = "24BBC590737D4E7508A96609A56E11F3"
USER_ID = "47596378"
USER_NAME = "Rich"
TOKEN_FILE = os.path.expanduser("~/.config/loseit/token")
HOURS_FROM_GMT = -5

MEAL_TYPES = {
    "breakfast": 0, "lunch": 1, "dinner": 2, "snacks": 3, "snack": 3,
}
MEAL_NAMES = {0: "Breakfast", 1: "Lunch", 2: "Dinner", 3: "Snacks"}

HEADERS = {
    "content-type": "text/x-gwt-rpc; charset=UTF-8",
    "x-gwt-module-base": BASE_URL,
    "x-gwt-permutation": STRONG_NAME,
    "x-loseit-gwtversion": "devmode",
    "x-loseit-hoursfromgmt": str(HOURS_FROM_GMT),
    "origin": "https://www.loseit.com",
    "referer": "https://www.loseit.com/",
}

# A known mapping from the sniffing session: 2026-02-02 -> 9164.
# Used to compute day numbers for arbitrary dates.
_DAYNUM_ANCHOR = (date(2026, 2, 2), 9164)

# ─── Auth ────────────────────────────────────────────────────────────────────

def load_token():
    token = os.environ.get("LOSEIT_TOKEN")
    if token:
        return token.strip()
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    print(f"❌ No token. Set LOSEIT_TOKEN or put token in {TOKEN_FILE}")
    sys.exit(1)


def make_session(token):
    s = requests.Session()
    s.headers.update(HEADERS)
    s.cookies.set("liauth", token, domain="www.loseit.com", path="/")
    s.cookies.set("fn_auth", token, domain="www.loseit.com", path="/")
    return s


# ─── GWT-RPC Core ───────────────────────────────────────────────────────────

def gwt_call(session, payload, debug=False):
    """Send GWT-RPC call, return raw response text or None on error."""
    if debug:
        print(f"  📤 Payload ({len(payload)} chars): {payload[:180]}...")
    resp = session.post(SERVICE_URL, data=payload)
    if debug:
        print(f"  📥 HTTP {resp.status_code}, {len(resp.text)} chars")
    if resp.status_code != 200:
        print(f"❌ HTTP {resp.status_code}: {resp.text[:300]}")
        return None
    text = resp.text
    if text.startswith("//EX"):
        err = re.search(r'"([^"]*)"', text)
        print(f"❌ GWT Error: {err.group(1) if err else text[:200]}")
        return None
    if not text.startswith("//OK"):
        print(f"❌ Unexpected: {text[:200]}")
        return None
    return text


def parse_gwt_response(text):
    """Parse //OK[...] → (data_tokens, string_table).

    String table is the [...] array at the end of the response.
    String refs in data are 1-indexed: ref N → string_table[N-1].
    """
    if not text or not text.startswith("//OK["):
        return [], []

    inner = text[5:-1]

    # Find string table array at the end
    bracket_start = inner.rfind(",[\"")
    if bracket_start == -1:
        # fallback: try last ',['
        bracket_start = inner.rfind(",[\"")
    bracket_start = inner.rfind(",[\"")
    # robust find for ',['
    bracket_start = inner.rfind(",[\"")
    bracket_start = inner.rfind(',[')
    if bracket_start == -1:
        return [], []

    data_str = inner[:bracket_start]
    table_str = inner[bracket_start + 1:]

    # Parse string table
    string_table = []
    for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', table_str):
        s = m.group(1)
        s = s.replace('\\u0026', '&').replace('\\"', '"').replace('\\\\', '\\')
        string_table.append(s)

    # Parse data tokens
    tokens = []
    for tok in data_str.split(','):
        tok = tok.strip()
        if not tok:
            continue
        if tok.startswith('"') and tok.endswith('"'):
            tokens.append(tok[1:-1].replace('\\u0026', '&'))
        else:
            try:
                tokens.append(float(tok) if '.' in tok else int(tok))
            except ValueError:
                tokens.append(tok)

    return tokens, string_table


def str_ref(string_table, ref):
    """Resolve a GWT string reference. ref is 1-indexed into string_table."""
    if isinstance(ref, int) and 1 <= ref <= len(string_table):
        return string_table[ref - 1]
    return None


# ─── Helpers ────────────────────────────────────────────────────────────────

def uuid_signed_bytes(u: uuid.UUID):
    b = u.bytes
    out = []
    for x in b:
        out.append(x - 256 if x >= 128 else x)
    return out


def day_number_for(d: date) -> int:
    anchor_date, anchor_num = _DAYNUM_ANCHOR
    return anchor_num + (d - anchor_date).days


def parse_date_arg(s: str | None) -> date:
    if not s:
        return datetime.now().date()
    return datetime.strptime(s, "%Y-%m-%d").date()


# ─── Replay ──────────────────────────────────────────────────────────────────

REPLAY_PAYLOAD = (
    "7|0|28|"
    "https://d3hsih69yn4d89.cloudfront.net/web/|"
    "5ED2771F63B26294E45551B2D697E7B0|"
    "com.loseit.core.client.service.LoseItRemoteService|"
    "updateFoodLogEntry|"
    "com.loseit.core.client.service.ServiceRequestToken/1076571655|"
    "com.loseit.core.client.model.FoodLogEntry/264522954|"
    "com.loseit.core.client.model.UserId/4281239478|"
    "Rich|"
    "com.loseit.core.client.model.FoodIdentifier/2763145970|"
    "Yogurt|en-US|"
    "Greek Yogurt, Strawberry, Non Fat|"
    "Chobani|"
    "com.loseit.core.client.model.interfaces.FoodProductType/2860616120|"
    "com.loseit.healthdata.model.shared.Verification/3485154600|"
    "com.loseit.core.client.model.SimplePrimaryKey/3621315060|"
    "[B/3308590456|"
    "com.loseit.core.client.model.FoodLogEntryContext/4082213671|"
    "com.loseit.core.shared.model.DayDate/1611136587|"
    "java.util.Date/3385151746|"
    "com.loseit.core.client.model.interfaces.FoodLogEntryType/1152459170|"
    "com.loseit.core.client.model.FoodServing/1858865662|"
    "com.loseit.core.client.model.FoodNutrients/1097231324|"
    "java.util.HashMap/1797211028|"
    "com.loseit.healthdata.model.shared.food.FoodMeasurement/2371921172|"
    "java.lang.Double/858496421|"
    "com.loseit.core.client.model.FoodServingSize/63998910|"
    "com.loseit.core.client.model.FoodMeasure/1457474932|"
    "1|2|3|4|2|5|6|"
    "5|0|7|47596378|8|-5|"
    "6|9|-1|10|11|12|13|14|0|-1|15|0|"
    "ZwdI0HK|16|17|16|17|-115|-32|94|82|-48|75|64|-95|55|52|-122|-82|-16|-48|120|"
    "18|0|19|20|ZwdImkw|9164|-5|0|-1|-1|0|0|0|"
    "21|1|0|"
    "22|23|1|2|24|9|"
    "25|9|26|55|"
    "25|2|26|150|"
    "25|13|26|11|"
    "25|3|26|0|"
    "25|0|26|110|"
    "25|11|26|0|"
    "25|8|26|5|"
    "25|12|26|14|"
    "25|10|26|15|"
    "27|2|1|28|45|1|1|2|0|"
    "P__________|ZwdI0HK|16|17|16|-23|122|50|48|-46|-41|77|124|-86|-128|-99|40|-26|-33|-33|66|"
)


def do_replay(session, debug=False):
    """Replay the captured Chobani Greek Yogurt → Snacks save."""
    print("🔄 Replaying: Chobani Greek Yogurt, Strawberry, Non Fat → Snacks")
    result = gwt_call(session, REPLAY_PAYLOAD, debug=debug)
    if result:
        print("✅ Logged successfully!")
        print("   📦 Chobani Greek Yogurt, Strawberry, Non Fat")
        print("   🍽️  Meal: Snacks")
        print("   🔥 Calories: 110 | Protein: 11g | Carbs: 15g | Fat: 0g")
        return True
    return False


# ─── Delete (Replay) ─────────────────────────────────────────────────────────

_DELETE_PAYLOAD_PATH = os.path.expanduser("~/clawd/integrations/loseit/data/delete-payload.txt")


def load_delete_payload():
    """Load captured deleteFoodLogEntry payload from disk."""
    try:
        with open(_DELETE_PAYLOAD_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def do_delete_replay(session, debug=False, yes=False):
    """Replay captured deleteFoodLogEntry call (will remove an existing diary entry)."""
    payload = load_delete_payload()
    if not payload:
        print(f"❌ Delete payload not found at {_DELETE_PAYLOAD_PATH}")
        return False

    print("🗑️  Replaying: deleteFoodLogEntry (captured payload)")
    if not yes:
        try:
            ans = input("This will DELETE a food log entry. Type 'delete' to continue: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return False
        if ans != "delete":
            print("Cancelled.")
            return False

    result = gwt_call(session, payload, debug=debug)
    if result:
        print("✅ Deleted successfully! (per server response)")
        print("   📦 Entry: Chobani Greek Yogurt (captured) — 2 servings")
        return True
    return False


# ─── Search ──────────────────────────────────────────────────────────────────

def build_search_payload(query):
    """Build searchFoods GWT-RPC payload (incremental search format)."""
    strings = [
        BASE_URL,
        POLICY_HASH,
        "com.loseit.core.client.service.LoseItRemoteService",
        "searchFoods",
        "com.loseit.core.client.service.ServiceRequestToken/1076571655",
        "java.lang.String/2004016611",
        "I",   # primitive int type
        "Z",   # primitive boolean type
        "com.loseit.core.client.model.UserId/4281239478",
        USER_NAME,
        query,
        "en-US",
    ]
    n = len(strings)
    header = f"7|0|{n}|" + "|".join(strings) + "|"
    data = f"1|2|3|4|6|5|6|6|7|8|8|5|0|9|{USER_ID}|10|{HOURS_FROM_GMT}|11|12|15|1|1|"
    return header + data


def extract_food_results(tokens, string_table):
    """Extract food results from GWT search response.

    Heuristic parser:
    - Each SearchResultFood block ends with: <16 pk bytes> 16 [B_ref] SimplePrimaryKey_ref SearchResultFood_ref
      In practice for our responses: ... <16 bytes>, 16, bytes_type_ref, pk_type_ref, food_type_ref
    - We split on that delimiter and then recover name/brand/category by mapping
      positive string refs in the chunk.

    Returns list of dicts: {name, brand, category, pk_bytes}
    """
    foods = []

    # Identify type refs
    food_type_ref = None
    pk_type_ref = None
    bytes_type_ref = None

    for i, s in enumerate(string_table):
        ref = i + 1
        if "SearchResultFood/" in s:
            food_type_ref = ref
        elif "SimplePrimaryKey/" in s:
            pk_type_ref = ref
        elif s == "[B/3308590456":
            bytes_type_ref = ref

    if not (food_type_ref and pk_type_ref and bytes_type_ref):
        return foods

    delimiter = [16, bytes_type_ref, pk_type_ref, food_type_ref]

    # Find all occurrences of delimiter
    ends = []
    for i in range(len(tokens) - 3):
        if tokens[i:i+4] == delimiter:
            ends.append(i+3)

    # Find plausible start of first entry: after first negative backref marker
    start = 0
    for i, t in enumerate(tokens[:80]):
        if isinstance(t, int) and t < 0:
            start = i + 1
            break

    prev = start
    for end in ends:
        chunk = tokens[prev:end+1]
        # PK bytes: 16 numbers immediately before the delimiter's leading 16
        # (the delimiter begins with 16, so pk bytes are chunk[-(4+16):-4])
        pk_bytes = []
        if len(chunk) >= 4 + 16:
            pk_bytes = chunk[-(4+16):-4]
            pk_bytes = [int(x) for x in pk_bytes]

        # candidate strings from chunk
        strings = []
        for t in chunk:
            if isinstance(t, int) and 1 <= t <= len(string_table):
                s = str_ref(string_table, t)
                if not s:
                    continue
                if s.startswith("com.") or s.startswith("java.") or s.startswith("["):
                    continue
                if s in {"All Foods", "BB", "BQ", "en-US", USER_NAME, "I", "Z"}:
                    continue
                strings.append(s)

        # locale appears as string "en-US" in table; category often a generic like "Pork"
        # name is usually the longest non-empty string in the entry, brand often shorter.
        strings = [s for s in strings if s is not None]
        name = ""
        brand = ""
        category = ""
        if strings:
            name = max(strings, key=lambda x: len(x))
            # category heuristic: common single-word entry or first string in table chunk
            for s in strings:
                if len(s) <= 16 and s[0].isupper() and " " not in s and s.lower() not in {"rich"}:
                    category = s
                    break
            # brand heuristic: remaining non-empty string that's not name/category
            for s in strings:
                if s and s != name and s != category and len(s) <= 30:
                    brand = s
                    break

        if name and pk_bytes and len(pk_bytes) == 16:
            foods.append({
                "name": name,
                "brand": brand,
                "category": category,
                "pk_bytes": pk_bytes,
            })

        prev = end + 1

    return foods


def search_foods(session, query, debug=False):
    """Search for foods, return list of {name, brand, category, pk_bytes}."""
    payload = build_search_payload(query)
    print(f"🔍 Searching: {query}")

    result = gwt_call(session, payload, debug=debug)
    if not result:
        return []

    tokens, string_table = parse_gwt_response(result)

    if debug:
        print(f"\n  String table ({len(string_table)} entries):")
        for i, s in enumerate(string_table):
            print(f"    [{i+1}] {s[:80]}")
        print(f"\n  Data tokens ({len(tokens)}):")
        print(f"    {tokens[:60]}...")

    if not string_table:
        return []

    foods = extract_food_results(tokens, string_table)

    return foods


def display_results(foods, limit=15):
    if not foods:
        print("  No results found.")
        return

    print(f"\n{'#':>3}  {'Food':50} {'Brand'}")
    print(f"{'─'*3}  {'─'*50} {'─'*20}")
    for i, f in enumerate(foods[:limit]):
        name = (f.get('name') or '')[:50]
        brand = (f.get('brand') or '')[:20]
        if brand:
            print(f"{i+1:>3}  {name:50} {brand}")
        else:
            print(f"{i+1:>3}  {name}")


# ─── getInitializationData (for DayDate key) ────────────────────────────────

def build_get_initialization_data_payload():
    strings = [
        BASE_URL,
        POLICY_HASH,
        "com.loseit.core.client.service.LoseItRemoteService",
        "getInitializationData",
        "com.loseit.core.client.service.ServiceRequestToken/1076571655",
        "com.loseit.core.client.model.UserId/4281239478",
        USER_NAME,
    ]
    n = len(strings)
    header = f"7|0|{n}|" + "|".join(strings) + "|"
    data = f"1|2|3|4|1|5|5|0|6|{USER_ID}|7|{HOURS_FROM_GMT}|"
    return header + data


def get_daydate_key(session, target_daynum: int, debug=False) -> str | None:
    """Best-effort lookup of the DayDate key string for a day number.

    Uses getInitializationData, which returns recent DayDate keys.
    If target is outside returned range, returns None.
    """
    payload = build_get_initialization_data_payload()
    resp = gwt_call(session, payload, debug=debug)
    if not resp:
        return None
    tokens, _st = parse_gwt_response(resp)

    # pattern in sniff: ...,-5,9164,"Zwc78Lo",...
    for i in range(len(tokens) - 2):
        if tokens[i] == target_daynum and isinstance(tokens[i+1], str):
            return tokens[i+1]
        if tokens[i] == HOURS_FROM_GMT and tokens[i+1] == target_daynum and isinstance(tokens[i+2], str):
            return tokens[i+2]
    return None


# ─── getUnsavedFoodLogEntry ─────────────────────────────────────────────────

def build_get_unsaved_food_log_entry_payload(food, locale="en-US"):
    """Build getUnsavedFoodLogEntry payload.

    Captured real method signature: 4 params
      (ServiceRequestToken, IPrimaryKey, String locale, String foodName)

    IPrimaryKey is serialized as: SimplePrimaryKey | [B | 16 | <16 signed bytes>
    """
    name = food.get("name") or ""
    pk_bytes = food.get("pk_bytes") or []
    if len(pk_bytes) != 16:
        raise ValueError("food.pk_bytes must be 16 bytes")

    strings = [
        BASE_URL,                   # 1
        POLICY_HASH,                # 2
        "com.loseit.core.client.service.LoseItRemoteService",  # 3
        "getUnsavedFoodLogEntry",   # 4
        "com.loseit.core.client.service.ServiceRequestToken/1076571655",  # 5
        "com.loseit.core.client.model.interfaces.IPrimaryKey",  # 6
        "java.lang.String/2004016611",  # 7
        "com.loseit.core.client.model.UserId/4281239478",  # 8
        USER_NAME,                  # 9
        "com.loseit.core.client.model.SimplePrimaryKey/3621315060",  # 10
        "[B/3308590456",            # 11
        locale,                     # 12
        name,                       # 13
    ]

    n = len(strings)
    header = f"7|0|{n}|" + "|".join(strings) + "|"

    # Data section: method(1,2,3,4) | 4 params | types(5,6,7,7) | values
    data = []
    data += ["1", "2", "3", "4"]
    data += ["4"]               # 4 params
    data += ["5", "6", "7", "7"]  # param types

    # Param 1: ServiceRequestToken
    data += ["5", "0", "8", USER_ID, "9", str(HOURS_FROM_GMT)]

    # Param 2: IPrimaryKey (serialized as SimplePrimaryKey)
    # NOTE: GWT serializes byte[] in REVERSE order
    data += ["10", "11", "16"]
    data += [str(int(b)) for b in reversed(pk_bytes)]

    # Param 3: locale string
    data += ["12"]

    # Param 4: food name string
    data += ["13"]

    return header + "|".join(data) + "|"


def parse_unsaved_food_log_entry(tokens, string_table):
    """Parse getUnsavedFoodLogEntry response.

    GWT responses serialize data in REVERSE order. Key patterns:
    - Nutrients: <value>, <Double_ref>, <ordinal>, <FoodMeasurement_ref>
    - PK bytes: <16 signed bytes>, <16 (length)>, <[B_ref>, <SimplePrimaryKey_ref>
    - Serving: values near FoodServingSize ref

    Returns dict with: name, brand, category, food_pk_bytes, day_key, nutrients,
    serving_qty, food_measure_ordinal
    """
    out = {
        "name": "",
        "brand": "",
        "category": "",
        "food_pk_bytes": None,
        "day_key": "",
        "nutrients": {},
        "serving_qty": None,
        "food_measure_ordinal": None,
    }

    # Locate type refs in string table
    fm_ref = None      # FoodMeasurement
    dbl_ref = None     # Double
    bytes_ref = None   # [B
    pk_ref = None      # SimplePrimaryKey
    serving_size_ref = None
    food_measure_ref = None

    for i, s in enumerate(string_table):
        ref = i + 1
        if "FoodMeasurement/" in s:
            fm_ref = ref
        elif s == "java.lang.Double/858496421":
            dbl_ref = ref
        elif s == "[B/3308590456":
            bytes_ref = ref
        elif "SimplePrimaryKey/" in s:
            pk_ref = ref
        elif "FoodServingSize/" in s:
            serving_size_ref = ref
        elif "FoodMeasure/" in s:
            food_measure_ref = ref

    # Extract name/brand/category from string table
    user_skip = {USER_NAME, "en-US", "I", "Z", "All Foods", "P__________"}
    candidates = [s for s in string_table if s and not s.startswith(("com.", "java.", "[")) and s not in user_skip]
    if candidates:
        out["name"] = max(candidates, key=len)
        for s in candidates:
            if len(s) <= 20 and " " not in s and s[0].isupper():
                out["category"] = s
                break
        for s in candidates:
            if s and s != out["name"] and s != out["category"] and len(s) <= 30:
                out["brand"] = s
                break

    # Extract day_key (first Zw-prefixed string in tokens)
    for t in tokens:
        if isinstance(t, str) and len(t) >= 5 and t.startswith("Zw") and t != "P__________":
            out["day_key"] = t
            break

    # Food PK bytes: pattern is <16 bytes>, 16(len), [B_ref, SimplePrimaryKey_ref
    # There may be 2 PKs: entry PK (first) and food PK (second)
    if bytes_ref and pk_ref:
        pk_positions = []
        for i in range(16, len(tokens) - 2):
            if (tokens[i] == 16 and i + 2 < len(tokens) and
                    tokens[i+1] == bytes_ref and tokens[i+2] == pk_ref):
                maybe = tokens[i-16:i]
                if all(isinstance(x, (int, float)) for x in maybe):
                    pk_positions.append(([int(x) for x in maybe], i))
        # Second PK is the food PK (first is server-generated entry PK)
        if len(pk_positions) >= 2:
            out["food_pk_bytes"] = pk_positions[1][0]
        elif len(pk_positions) == 1:
            out["food_pk_bytes"] = pk_positions[0][0]

    # Nutrients: GWT response reversed pattern:
    #   <value>, <Double_ref=22>, <ordinal>, <FoodMeasurement_ref=21>
    if fm_ref and dbl_ref:
        for i in range(len(tokens) - 3):
            if (tokens[i+3] == fm_ref and tokens[i+1] == dbl_ref and
                    isinstance(tokens[i+2], int) and isinstance(tokens[i], (int, float))):
                ord_ = int(tokens[i+2])
                val = float(tokens[i])
                if 0 <= ord_ <= 30:
                    out["nutrients"][ord_] = val

    # Serving: look for FoodServingSize ref pattern
    if serving_size_ref:
        for i in range(len(tokens) - 2):
            if tokens[i] == serving_size_ref:
                if i + 1 < len(tokens) and isinstance(tokens[i+1], (int, float)):
                    out["serving_qty"] = float(tokens[i+1])
                break

    # FoodMeasure ordinal
    if food_measure_ref:
        for i in range(len(tokens) - 1):
            if tokens[i] == food_measure_ref and isinstance(tokens[i+1], int):
                out["food_measure_ordinal"] = int(tokens[i+1])
                break

    return out


def get_unsaved_food_log_entry(session, food, debug=False):
    payload = build_get_unsaved_food_log_entry_payload(food)
    resp = gwt_call(session, payload, debug=debug)
    if not resp:
        return None
    tokens, st = parse_gwt_response(resp)
    if debug:
        print(f"  getUnsavedFoodLogEntry: string_table={len(st)} tokens={len(tokens)}")
    return parse_unsaved_food_log_entry(tokens, st)


# ─── updateFoodLogEntry ─────────────────────────────────────────────────────

def build_update_food_log_entry_payload(unsaved, meal_ordinal: int, day_key: str, day_num: int, servings: float):
    """Build updateFoodLogEntry payload from parsed unsaved entry."""

    # Scale nutrients — server only accepts the core 9 ordinals
    CORE_NUTRIENT_ORDINALS = {0, 2, 3, 8, 9, 10, 11, 12, 13}
    nutrients = {k: (v * servings) for k, v in (unsaved.get("nutrients") or {}).items()
                 if k in CORE_NUTRIENT_ORDINALS}

    category = unsaved.get("category") or ""
    name = unsaved.get("name") or ""
    brand = unsaved.get("brand") or ""
    food_pk = unsaved.get("food_pk_bytes")
    if not food_pk or len(food_pk) != 16:
        raise ValueError("missing food primary key bytes")

    entry_uuid = uuid.uuid4()
    entry_pk = uuid_signed_bytes(entry_uuid)

    # String table matches replay payload (28 entries)
    strings = [
        BASE_URL,
        POLICY_HASH,
        "com.loseit.core.client.service.LoseItRemoteService",
        "updateFoodLogEntry",
        "com.loseit.core.client.service.ServiceRequestToken/1076571655",
        "com.loseit.core.client.model.FoodLogEntry/264522954",
        "com.loseit.core.client.model.UserId/4281239478",
        USER_NAME,
        "com.loseit.core.client.model.FoodIdentifier/2763145970",
        category or "Food",
        "en-US",
        name,
        brand,
        "com.loseit.core.client.model.interfaces.FoodProductType/2860616120",
        "com.loseit.healthdata.model.shared.Verification/3485154600",
        "com.loseit.core.client.model.SimplePrimaryKey/3621315060",
        "[B/3308590456",
        "com.loseit.core.client.model.FoodLogEntryContext/4082213671",
        "com.loseit.core.shared.model.DayDate/1611136587",
        "java.util.Date/3385151746",
        "com.loseit.core.client.model.interfaces.FoodLogEntryType/1152459170",
        "com.loseit.core.client.model.FoodServing/1858865662",
        "com.loseit.core.client.model.FoodNutrients/1097231324",
        "java.util.HashMap/1797211028",
        "com.loseit.healthdata.model.shared.food.FoodMeasurement/2371921172",
        "java.lang.Double/858496421",
        "com.loseit.core.client.model.FoodServingSize/63998910",
        "com.loseit.core.client.model.FoodMeasure/1457474932",
    ]

    n = len(strings)
    header = f"7|0|{n}|" + "|".join(strings) + "|"

    # Build data, modeled after REPLAY_PAYLOAD
    hm_size = len(nutrients)
    parts = []
    parts += ["1", "2", "3", "4", "2", "5", "6"]

    # token
    parts += ["5", "0", "7", USER_ID, "8", str(HOURS_FROM_GMT)]

    # FoodLogEntry
    parts += [
        "6",
        "9", "-1", "10", "11", "12", "13",
        "14", "0", "-1",
        "15", "0",
        # Key string: MUST be a valid DayDate key-like string (captured).
        (unsaved.get("day_key") or day_key or ""),
        "16", "17", "16",
    ]
    parts += [str(int(b)) for b in reversed(food_pk)]

    # context + daydate
    parts += [
        "18", "0",
        "19", "20", day_key, str(day_num), str(HOURS_FROM_GMT),
        "0", "-1", "-1", "0", "0", "0",
        # entry type
        "21", str(meal_ordinal), "0",
        # FoodServing + FoodNutrients
        # Pattern from replay: 22|23|1|<servings>|24|<nutrient_count>
        "22", "23",
        "1", str(int(servings)) if servings == int(servings) else str(servings),
        "24", str(hm_size),
    ]

    # Nutrient entries
    for ord_, val in sorted(nutrients.items()):
        parts += ["25", str(int(ord_)), "26", str(float(val))]

    # Serving size & measure: keep reasonable defaults; if we parsed measure ordinal we can set it.
    measure = unsaved.get("food_measure_ordinal")
    if measure is None:
        measure = 45  # container-ish default from replay

    servings_int = str(int(servings)) if servings == int(servings) else str(servings)
    parts += [
        "27", servings_int, "1",
        "28", str(int(measure)), "1",
        "1", "2", "0",
        "P__________",
        (unsaved.get("day_key") or day_key or ""),
        "16", "17", "16",
    ]
    parts += [str(int(b)) for b in reversed(entry_pk)]

    return header + "|".join(parts) + "|"


def log_food(session, food, meal: str, when: date, servings: float, debug=False):
    meal_ord = MEAL_TYPES[meal]
    day_num = day_number_for(when)
    unsaved = get_unsaved_food_log_entry(session, food, debug=debug)
    if not unsaved:
        print("❌ getUnsavedFoodLogEntry failed")
        return False

    # Prefer day_key from unsaved response; fall back to getInitializationData
    day_key = unsaved.get("day_key") or get_daydate_key(session, day_num, debug=debug) or ""

    # Prefer original selected metadata
    if food.get("name"):
        unsaved["name"] = food["name"]
    if food.get("brand"):
        unsaved["brand"] = food["brand"]
    if food.get("category"):
        unsaved["category"] = food["category"]
    if food.get("pk_bytes"):
        unsaved["food_pk_bytes"] = food["pk_bytes"]

    payload = build_update_food_log_entry_payload(unsaved, meal_ord, day_key, day_num, servings)
    resp = gwt_call(session, payload, debug=debug)
    if not resp:
        return False

    print("✅ Logged successfully!")
    print(f"   📦 {unsaved.get('name','(food)')}")
    if unsaved.get("brand"):
        print(f"   🏷️  {unsaved['brand']}")
    print(f"   🍽️  Meal: {MEAL_NAMES.get(meal_ord, meal)}")
    print(f"   📅 Date: {when.isoformat()} (day {day_num})")
    if servings != 1:
        print(f"   🔢 Servings: {servings}")
    if unsaved.get("nutrients"):
        cals = unsaved["nutrients"].get(0)
        if cals is not None:
            print(f"   🔥 Calories (scaled): {cals * servings:.0f}")
    return True


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Log food to Lose It! via GWT-RPC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s --replay                              Test auth by logging Chobani yogurt
  %(prog)s "banana" --search                     Search for banana
  %(prog)s "pulled pork" -m dinner --pick 9      Search and log #9 to dinner
  %(prog)s "dill pickles" -m dinner --pick 1 --servings 3
""",
    )
    parser.add_argument("food", nargs="?", help="Food to search for")
    parser.add_argument("--meal", "-m", choices=list(MEAL_TYPES.keys()), default="snacks",
                        help="Meal type (default: snacks)")
    parser.add_argument("--replay", action="store_true",
                        help="Replay captured Chobani yogurt save (auth test)")
    parser.add_argument("--delete", action="store_true",
                        help="Replay captured deleteFoodLogEntry payload (dangerous)")
    parser.add_argument("--yes", action="store_true",
                        help="Skip confirmation for --delete")
    parser.add_argument("--search", "-s", action="store_true",
                        help="Search only, don't log")
    parser.add_argument("--servings", type=float, default=1.0,
                        help="Number of servings (default: 1)")
    parser.add_argument("--date", dest="date", default=None,
                        help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--pick", type=int, default=None,
                        help="Auto-pick Nth search result (1-indexed)")
    parser.add_argument("--debug", "-d", action="store_true",
                        help="Show debug output")
    parser.add_argument("--raw", action="store_true",
                        help="Show raw GWT response (search)")

    args = parser.parse_args()

    if not args.replay and not args.delete and not args.food:
        parser.print_help()
        sys.exit(1)

    token = load_token()
    session = make_session(token)

    # ── Replay save mode ──
    if args.replay:
        success = do_replay(session, debug=args.debug)
        sys.exit(0 if success else 1)

    # ── Replay delete mode ──
    if args.delete:
        success = do_delete_replay(session, debug=args.debug, yes=args.yes)
        sys.exit(0 if success else 1)

    # ── Search ──
    foods = search_foods(session, args.food, debug=args.debug)

    if args.raw:
        payload = build_search_payload(args.food)
        result = gwt_call(session, payload)
        if result:
            print(f"\n📄 Raw ({len(result)} chars):\n{result[:2000]}")

    display_results(foods)

    if args.search:
        sys.exit(0)

    if not foods:
        print("❌ No results to log.")
        sys.exit(1)

    when = parse_date_arg(args.date)

    # ── Selection ──
    if args.pick is not None:
        idx = args.pick - 1
        if idx < 0 or idx >= len(foods):
            print(f"❌ --pick must be 1..{len(foods)}")
            sys.exit(1)
    else:
        meal_name = MEAL_NAMES[MEAL_TYPES[args.meal]]
        print(f"\n🍽️  Target meal: {meal_name}")
        try:
            choice = input("\nSelect food # (or 'q' to quit): ").strip()
            if choice.lower() in ('q', 'quit', ''):
                sys.exit(0)
            idx = int(choice) - 1
            if idx < 0 or idx >= len(foods):
                print(f"Pick 1-{min(len(foods), 15)}")
                sys.exit(1)
        except (ValueError, EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(0)

    selected = foods[idx]
    brand_str = f" ({selected['brand']})" if selected.get('brand') else ""
    print(f"\n  Selected: {selected.get('name','')}{brand_str}")
    if selected.get('pk_bytes'):
        print(f"  PK bytes: {selected['pk_bytes']}")

    ok = log_food(session, selected, args.meal, when, args.servings, debug=args.debug)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
