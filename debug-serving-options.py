#!/usr/bin/env python3
"""Debug script to see ALL serving size options available for a food"""

import sys
import os

# Load the main script functions
with open(os.path.join(os.path.dirname(__file__), 'loseit-log.py')) as f:
    code = f.read()
    code = code.split('if __name__ == "__main__":')[0]
    exec(code)

token = load_token()
session = make_session(token)

# Search for guacamole
foods = search_foods(session, "guacamole", debug=False)
food = foods[0]  # First result

print(f"Food: {food.get('name')}")
print(f"Brand: {food.get('brand')}\n")

# Get unsaved entry with RAW response
payload = build_get_unsaved_food_log_entry_payload(food)
resp = gwt_call(session, payload, debug=False)

if not resp:
    print("Failed to get unsaved entry")
    sys.exit(1)

# Parse it
tokens, st = parse_gwt_response(resp)

print(f"=== STRING TABLE ===")
for i, s in enumerate(st):
    print(f"[{i+1:2d}] {s}")

print(f"\n=== LOOKING FOR ALL FoodMeasure REFERENCES ===")
# Find FoodMeasure ref
fm_ref = None
for i, s in enumerate(st):
    if "FoodMeasure/" in s:
        fm_ref = i + 1
        print(f"FoodMeasure type ref: {fm_ref}")
        break

if fm_ref:
    print(f"\nAll FoodMeasure occurrences in tokens:")
    for i, t in enumerate(tokens):
        if t == fm_ref:
            # Show context around it
            context = tokens[max(0, i-5):min(len(tokens), i+10)]
            print(f"  [{i:3d}] {context}")
            # The measure ordinal should be 1 position before
            if i > 0:
                print(f"        → measure ordinal: {tokens[i-1]}")

print(f"\n=== LOOKING FOR SERVING SIZE INFO ===")
# Find FoodServingSize ref
fss_ref = None
for i, s in enumerate(st):
    if "FoodServingSize/" in s:
        fss_ref = i + 1
        print(f"FoodServingSize type ref: {fss_ref}")
        break

if fss_ref:
    print(f"\nAll FoodServingSize occurrences:")
    for i, t in enumerate(tokens):
        if t == fss_ref:
            context = tokens[max(0, i-5):min(len(tokens), i+10)]
            print(f"  [{i:3d}] {context}")
            if i > 0:
                print(f"        → serving qty: {tokens[i-1]}")
