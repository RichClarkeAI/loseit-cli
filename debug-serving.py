#!/usr/bin/env python3
"""Debug script to see what serving data we're getting from getUnsavedFoodLogEntry"""

import sys
import os

# Load the main script functions
with open(os.path.join(os.path.dirname(__file__), 'loseit-log.py')) as f:
    code = f.read()
    # Remove the if __name__ == "__main__" block
    code = code.split('if __name__ == "__main__":')[0]
    exec(code)

token = load_token()
session = make_session(token)

# Search for banana
print("Searching for banana...")
foods = search_foods(session, "banana", debug=False)

if not foods:
    print("No results")
    sys.exit(1)

# Test first food
print(f"Found {len(foods)} foods")
if len(foods) < 14:
    print("Using first food")
    food = foods[0]
else:
    food = foods[13]  # "Banana, Medium, 7" - 7 7/8" Long"
print(f"\nFood: {food.get('name')}")
print(f"PK: {food.get('pk_bytes')}\n")

# Get unsaved entry with RAW response
payload = build_get_unsaved_food_log_entry_payload(food)
resp = gwt_call(session, payload, debug=False)

if not resp:
    print("Failed to get unsaved entry")
    sys.exit(1)

# Parse it
tokens, st = parse_gwt_response(resp)

print(f"=== STRING TABLE ({len(st)} entries) ===")
for i, s in enumerate(st):
    print(f"[{i+1:2d}] {s}")

print(f"\n=== DATA TOKENS ({len(tokens)} tokens) ===")
# Print in rows of 20 for readability
for i in range(0, len(tokens), 20):
    chunk = tokens[i:i+20]
    print(f"[{i:3d}] {chunk}")

# Now parse it
unsaved = parse_unsaved_food_log_entry(tokens, st)

print(f"\n=== PARSED RESULT ===")
print(f"serving_qty: {unsaved.get('serving_qty')}")
print(f"food_measure_ordinal: {unsaved.get('food_measure_ordinal')}")
print(f"nutrients: {unsaved.get('nutrients')}")
print(f"day_key: {unsaved.get('day_key')}")

# Look for FoodMeasure and FoodServingSize refs
fm_ref = None
fss_ref = None
for i, s in enumerate(st):
    if "FoodMeasure/" in s:
        fm_ref = i + 1
        print(f"\nFoodMeasure ref: {fm_ref} -> {s}")
    if "FoodServingSize/" in s:
        fss_ref = i + 1
        print(f"FoodServingSize ref: {fss_ref} -> {s}")

# Find those refs in tokens
if fm_ref:
    print(f"\nLooking for FoodMeasure ref ({fm_ref}) in tokens:")
    for i, t in enumerate(tokens):
        if t == fm_ref:
            context = tokens[max(0, i-5):min(len(tokens), i+6)]
            print(f"  [{i}] context: {context}")

if fss_ref:
    print(f"\nLooking for FoodServingSize ref ({fss_ref}) in tokens:")
    for i, t in enumerate(tokens):
        if t == fss_ref:
            context = tokens[max(0, i-5):min(len(tokens), i+6)]
            print(f"  [{i}] context: {context}")
