#!/usr/bin/env python3
"""Match search results against personal food history"""

import json
import os
from difflib import SequenceMatcher

PERSONAL_DB_PATH = os.path.expanduser("~/clawd/integrations/loseit/data/personal-food-db.json")

def load_personal_db():
    """Load personal food database from JSON"""
    if not os.path.exists(PERSONAL_DB_PATH):
        return {}
    
    with open(PERSONAL_DB_PATH, 'r') as f:
        return json.load(f)

def fuzzy_match(food_name, personal_db, threshold=0.8):
    """Find best match in personal database using fuzzy string matching"""
    best_match = None
    best_score = 0
    
    food_lower = food_name.lower()
    
    for known_food in personal_db.keys():
        score = SequenceMatcher(None, food_lower, known_food.lower()).ratio()
        if score > best_score and score >= threshold:
            best_score = score
            best_match = known_food
    
    return (best_match, best_score) if best_match else (None, 0)

def get_personal_info(food_name, personal_db):
    """Get personal history for a food"""
    # Exact match first
    if food_name in personal_db:
        return personal_db[food_name]
    
    # Fuzzy match
    match, score = fuzzy_match(food_name, personal_db, threshold=0.75)
    if match:
        data = personal_db[match].copy()
        data['matched_name'] = match
        data['match_score'] = score
        return data
    
    return None

if __name__ == "__main__":
    # Test it
    db = load_personal_db()
    print(f"Loaded {len(db)} foods from history\n")
    
    test_foods = [
        "Greek Yogurt, Strawberry, Non Fat",
        "Guacamole, Mild",
        "guacamole",  # lowercase test
        "Scrambled Eggs",
    ]
    
    for food in test_foods:
        info = get_personal_info(food, db)
        if info:
            matched = info.get('matched_name', food)
            score = info.get('match_score', 1.0)
            print(f"✓ {food}")
            if score < 1.0:
                print(f"  → matched: {matched} ({score:.0%})")
            print(f"  You usually log: {info['typical_qty']} {info['unit']} = {info['calories']} cal")
        else:
            print(f"✗ {food} - not in history")
        print()
