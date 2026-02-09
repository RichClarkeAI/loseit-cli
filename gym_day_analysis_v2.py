#!/usr/bin/env python3
"""
Deeper analysis - tracking behavior patterns.
"""

import csv
import json
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

# Load gym check-in dates
with open(Path.home() / 'clawd/integrations/lafitness/data/checkins.json') as f:
    gym_data = json.load(f)

gym_dates = set()
for date_str in gym_data['checkins']:
    dt = datetime.strptime(date_str, '%m/%d/%Y')
    gym_dates.add(dt.strftime('%Y-%m-%d'))

# Load food logs
food_logs = []
csv_path = Path.home() / 'clawd/integrations/loseit/data/export/food-logs.csv'
with open(csv_path, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('Deleted') == '1':
            continue
        try:
            dt = datetime.strptime(row['Date'], '%m/%d/%Y')
            date_key = dt.strftime('%Y-%m-%d')
        except:
            continue
        cal_str = row.get('Calories', '0').replace(',', '')
        try:
            calories = float(cal_str)
        except:
            calories = 0
        food_logs.append({
            'date': date_key,
            'name': row.get('Name', ''),
            'calories': calories,
            'meal': row.get('Meal', '')
        })

# Aggregate by day
daily_stats = defaultdict(lambda: {'entries': 0, 'total_cal': 0, 'meals': set()})
for entry in food_logs:
    d = entry['date']
    daily_stats[d]['entries'] += 1
    daily_stats[d]['total_cal'] += entry['calories']
    daily_stats[d]['meals'].add(entry['meal'])

# Look at tracking patterns
print("="*70)
print("TRACKING PATTERN ANALYSIS")
print("="*70)

# Question: Does Rich track on gym days that he wouldn't otherwise?
# Look at "tracking gaps" - days with no logs
gym_period_start = min(gym_dates)
gym_period_end = max(gym_dates)

# Generate all days in range
start_dt = datetime.strptime(gym_period_start, '%Y-%m-%d')
end_dt = datetime.strptime(gym_period_end, '%Y-%m-%d')
all_days = []
current = start_dt
while current <= end_dt:
    all_days.append(current.strftime('%Y-%m-%d'))
    current += timedelta(days=1)

# Count tracking rates
gym_days_total = [d for d in all_days if d in gym_dates]
rest_days_total = [d for d in all_days if d not in gym_dates]

gym_days_logged = [d for d in gym_days_total if d in daily_stats]
rest_days_logged = [d for d in rest_days_total if d in daily_stats]

gym_track_rate = len(gym_days_logged) / len(gym_days_total) * 100 if gym_days_total else 0
rest_track_rate = len(rest_days_logged) / len(rest_days_total) * 100 if rest_days_total else 0

print(f"\nTracking Rate Comparison:")
print(f"  Gym days:  {len(gym_days_logged)}/{len(gym_days_total)} logged ({gym_track_rate:.1f}%)")
print(f"  Rest days: {len(rest_days_logged)}/{len(rest_days_total)} logged ({rest_track_rate:.1f}%)")
print(f"  Difference: {gym_track_rate - rest_track_rate:+.1f} percentage points")

if gym_track_rate > rest_track_rate + 5:
    print("\n  ⚠️  Rich is MORE LIKELY to log food on gym days!")
    print("     This is a form of tracking bias - gym days are over-represented.")

# Analyze by month to see if patterns change
print("\n" + "="*70)
print("MONTHLY BREAKDOWN")
print("="*70)

monthly_data = defaultdict(lambda: {'gym_entries': [], 'rest_entries': [], 'gym_cals': [], 'rest_cals': []})

for d in daily_stats:
    if gym_period_start <= d <= gym_period_end:
        month = d[:7]
        stats = daily_stats[d]
        if d in gym_dates:
            monthly_data[month]['gym_entries'].append(stats['entries'])
            monthly_data[month]['gym_cals'].append(stats['total_cal'])
        else:
            monthly_data[month]['rest_entries'].append(stats['entries'])
            monthly_data[month]['rest_cals'].append(stats['total_cal'])

print(f"\n{'Month':<10} {'Gym Days':<12} {'Rest Days':<12} {'Gym Ent':<10} {'Rest Ent':<10} {'Gym Cal':<10} {'Rest Cal':<10}")
print("-"*74)

for month in sorted(monthly_data.keys()):
    data = monthly_data[month]
    gym_n = len(data['gym_entries'])
    rest_n = len(data['rest_entries'])
    gym_ent_avg = sum(data['gym_entries'])/gym_n if gym_n > 0 else 0
    rest_ent_avg = sum(data['rest_entries'])/rest_n if rest_n > 0 else 0
    gym_cal_avg = sum(data['gym_cals'])/gym_n if gym_n > 0 else 0
    rest_cal_avg = sum(data['rest_cals'])/rest_n if rest_n > 0 else 0
    print(f"{month:<10} {gym_n:<12} {rest_n:<12} {gym_ent_avg:<10.1f} {rest_ent_avg:<10.1f} {gym_cal_avg:<10.0f} {rest_cal_avg:<10.0f}")

# Look at distribution of entries - is it different?
print("\n" + "="*70)
print("ENTRY COUNT DISTRIBUTION")
print("="*70)

gym_entry_counts = [daily_stats[d]['entries'] for d in daily_stats if d in gym_dates and gym_period_start <= d <= gym_period_end]
rest_entry_counts = [daily_stats[d]['entries'] for d in daily_stats if d not in gym_dates and gym_period_start <= d <= gym_period_end]

def percentile(lst, p):
    if not lst:
        return 0
    sorted_lst = sorted(lst)
    idx = int(len(sorted_lst) * p / 100)
    return sorted_lst[min(idx, len(sorted_lst)-1)]

print(f"\n{'Percentile':<15} {'Gym Days':>15} {'Rest Days':>15}")
print("-"*45)
for p in [25, 50, 75, 90]:
    print(f"{p}th%{'':<10} {percentile(gym_entry_counts, p):>15.0f} {percentile(rest_entry_counts, p):>15.0f}")

# Check for "complete" tracking days (3+ meals logged)
print("\n" + "="*70)
print("COMPLETE TRACKING DAYS (3+ meals)")
print("="*70)

gym_complete = sum(1 for d in daily_stats if d in gym_dates and len(daily_stats[d]['meals']) >= 3 and gym_period_start <= d <= gym_period_end)
rest_complete = sum(1 for d in daily_stats if d not in gym_dates and len(daily_stats[d]['meals']) >= 3 and gym_period_start <= d <= gym_period_end)

gym_total_logged = len([d for d in daily_stats if d in gym_dates and gym_period_start <= d <= gym_period_end])
rest_total_logged = len([d for d in daily_stats if d not in gym_dates and gym_period_start <= d <= gym_period_end])

print(f"\nGym days with complete tracking: {gym_complete}/{gym_total_logged} ({100*gym_complete/gym_total_logged if gym_total_logged else 0:.0f}%)")
print(f"Rest days with complete tracking: {rest_complete}/{rest_total_logged} ({100*rest_complete/rest_total_logged if rest_total_logged else 0:.0f}%)")

# Final verdict
print("\n" + "="*70)
print("FINAL ANALYSIS")
print("="*70)

print(f"""
Summary of findings:

1. TRACKING FREQUENCY:
   - Rich tracks food on {gym_track_rate:.0f}% of gym days vs {rest_track_rate:.0f}% of rest days
   - {'BIAS: More likely to log on gym days' if gym_track_rate > rest_track_rate + 5 else 'Similar tracking rates'}

2. ENTRIES PER DAY (when tracking):
   - Gym days: avg {sum(gym_entry_counts)/len(gym_entry_counts):.1f} entries, median {percentile(gym_entry_counts, 50):.0f}
   - Rest days: avg {sum(rest_entry_counts)/len(rest_entry_counts):.1f} entries, median {percentile(rest_entry_counts, 50):.0f}

3. CALORIES (when tracking):
   - Gym days: avg {sum([daily_stats[d]['total_cal'] for d in daily_stats if d in gym_dates and gym_period_start <= d <= gym_period_end])/len(gym_entry_counts):.0f} cal
   - Rest days: avg {sum([daily_stats[d]['total_cal'] for d in daily_stats if d not in gym_dates and gym_period_start <= d <= gym_period_end])/len(rest_entry_counts):.0f} cal

CONCLUSION:
""")

# Calculate tracking bias impact
if gym_track_rate > rest_track_rate + 10:
    print("📊 TRACKING BIAS DETECTED")
    print(f"   Rich is {gym_track_rate - rest_track_rate:.0f} percentage points more likely to log on gym days.")
    print("   This means gym days are OVER-REPRESENTED in the food log data.")
    print("   The apparent similarity in calories may hide that rest days are under-logged.")
else:
    print("📊 No significant tracking bias detected.")

avg_gym_entries = sum(gym_entry_counts)/len(gym_entry_counts) if gym_entry_counts else 0
avg_rest_entries = sum(rest_entry_counts)/len(rest_entry_counts) if rest_entry_counts else 0
entry_diff_pct = (avg_gym_entries - avg_rest_entries) / avg_rest_entries * 100 if avg_rest_entries else 0

if entry_diff_pct > 15:
    print(f"\n📝 MORE DETAILED TRACKING on gym days ({entry_diff_pct:.0f}% more entries)")
    print("   Rich logs more individual items on gym days, suggesting more thorough tracking.")
elif entry_diff_pct < -15:
    print(f"\n📝 LESS DETAILED TRACKING on gym days ({entry_diff_pct:.0f}% fewer entries)")
else:
    print(f"\n📝 Similar tracking detail ({entry_diff_pct:+.0f}% difference in entries)")

gym_cals = [daily_stats[d]['total_cal'] for d in daily_stats if d in gym_dates and gym_period_start <= d <= gym_period_end]
rest_cals = [daily_stats[d]['total_cal'] for d in daily_stats if d not in gym_dates and gym_period_start <= d <= gym_period_end]
cal_diff = (sum(gym_cals)/len(gym_cals)) - (sum(rest_cals)/len(rest_cals)) if gym_cals and rest_cals else 0

if abs(cal_diff) < 100:
    print(f"\n🍽️  SIMILAR CALORIES ({cal_diff:+.0f} cal difference)")
    print("   When Rich tracks, he logs similar total calories regardless of gym day.")
elif cal_diff > 0:
    print(f"\n🍽️  MORE CALORIES on gym days ({cal_diff:+.0f} cal)")
else:
    print(f"\n🍽️  FEWER CALORIES on gym days ({cal_diff:+.0f} cal)")
