#!/usr/bin/env bash
# Build personal food database from Lose It CSV export

set -e

EXPORT_DIR="$HOME/clawd/integrations/loseit/data/export"
OUTPUT_FILE="$HOME/clawd/integrations/loseit/data/personal-food-db.json"

if [ ! -f "$EXPORT_DIR/food-logs.csv" ]; then
    echo "❌ food-logs.csv not found"
    echo "   Run loseit-sync.sh first to download your data"
    exit 1
fi

echo "🔨 Building personal food database from CSV export..."

python3 << 'EOF'
import csv
import json
import os

EXPORT_DIR = os.path.expanduser("~/clawd/integrations/loseit/data/export")
OUTPUT_FILE = os.path.expanduser("~/clawd/integrations/loseit/data/personal-food-db.json")

# Build personal food database
food_db = {}

with open(os.path.join(EXPORT_DIR, 'food-logs.csv'), 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        name = row['Name'].strip()
        unit = row['Units'].strip()
        qty = float(row['Quantity'])
        cal = row['Calories'].replace(',', '')
        
        if cal and cal != 'n/a' and name not in food_db:
            food_db[name] = {
                "unit": unit,
                "typical_qty": qty,
                "calories": float(cal)
            }

# Save to JSON
with open(OUTPUT_FILE, 'w') as f:
    json.dump(food_db, f, indent=2)

print(f"✅ Created personal food database with {len(food_db)} foods")
print(f"   Saved to: {OUTPUT_FILE}")
EOF

echo ""
echo "📊 Your top 20 most-logged foods:"
echo ""

python3 << 'EOF'
import csv
from collections import defaultdict
import os

EXPORT_DIR = os.path.expanduser("~/clawd/integrations/loseit/data/export")

food_counts = defaultdict(lambda: {"count": 0, "unit": "", "qty": 0})

with open(os.path.join(EXPORT_DIR, 'food-logs.csv'), 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        name = row['Name'].strip()
        unit = row['Units'].strip()
        qty = float(row['Quantity'])
        
        food_counts[name]["count"] += 1
        food_counts[name]["unit"] = unit
        food_counts[name]["qty"] = qty

# Sort by count
sorted_foods = sorted(food_counts.items(), key=lambda x: x[1]["count"], reverse=True)

for i, (name, data) in enumerate(sorted_foods[:20], 1):
    print(f"{i:2}. {name[:50]:50} ({data['count']}× as {data['qty']} {data['unit']})")
EOF

echo ""
echo "💡 Now when you search, you'll see '📍 You usually log...' for matching foods"
