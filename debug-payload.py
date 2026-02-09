#!/usr/bin/env python3
"""Debug script to see what payload we're building"""

import sys
import os
from datetime import date

# Load the main script functions
with open(os.path.join(os.path.dirname(__file__), 'loseit-log.py')) as f:
    code = f.read()
    code = code.split('if __name__ == "__main__":')[0]
    exec(code)

token = load_token()
session = make_session(token)

# Search for orange
foods = search_foods(session, "orange", debug=False)
food = None
for f in foods:
    if 'Small Navel' in f.get('name', ''):
        food = f
        break

if not food:
    print("Food not found")
    sys.exit(1)

print(f"Food: {food.get('name')}")
print(f"PK: {food.get('pk_bytes')}\n")

# Get unsaved entry
unsaved = get_unsaved_food_log_entry(session, food, debug=False)
print(f"Unsaved entry parsed:")
print(f"  serving_qty: {unsaved.get('serving_qty')}")
print(f"  food_measure_ordinal: {unsaved.get('food_measure_ordinal')}")
print(f"  day_key: {unsaved.get('day_key')}")
print()

# Build payload
meal_ord = 3  # snacks
day_num = day_number_for(date.today())
servings = 1.0
day_key = unsaved.get("day_key") or ""

payload = build_update_food_log_entry_payload(unsaved, meal_ord, day_key, day_num, servings)

# Find the serving-related parts
parts = payload.split("|")

# Find where "27" and "28" appear (FoodServingSize and FoodMeasure refs)
for i, part in enumerate(parts):
    if part == "27":
        print(f"FoodServingSize section (index {i}):")
        context = parts[max(0, i-2):min(len(parts), i+10)]
        print(f"  {' | '.join(context)}")
    if part == "28":
        print(f"\nFoodMeasure section (index {i}):")
        context = parts[max(0, i-2):min(len(parts), i+10)]
        print(f"  {' | '.join(context)}")

# Compare to REPLAY_PAYLOAD
print(f"\n\nFor comparison, REPLAY_PAYLOAD serving section:")
replay_parts = REPLAY_PAYLOAD.split("|")
for i, part in enumerate(replay_parts):
    if part == "27":
        context = replay_parts[max(0, i-2):min(len(replay_parts), i+10)]
        print(f"  {' | '.join(context)}")
