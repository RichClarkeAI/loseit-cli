#!/usr/bin/env python3
"""
Analyze whether Rich eats more on gym days or just tracks better.
Compares Lose It food logs against LA Fitness check-in data.
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
    # Parse MM/DD/YYYY format
    dt = datetime.strptime(date_str, '%m/%d/%Y')
    gym_dates.add(dt.strftime('%Y-%m-%d'))

print(f"Total gym check-ins: {len(gym_dates)}")
print(f"Date range: {min(gym_dates)} to {max(gym_dates)}")

# Load food logs
food_logs = []
csv_path = Path.home() / 'clawd/integrations/loseit/data/export/food-logs.csv'
with open(csv_path, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Skip deleted entries
        if row.get('Deleted') == '1':
            continue
        
        # Parse date (MM/DD/YYYY format)
        try:
            dt = datetime.strptime(row['Date'], '%m/%d/%Y')
            date_key = dt.strftime('%Y-%m-%d')
        except:
            continue
        
        # Parse calories
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

print(f"\nTotal food log entries (non-deleted): {len(food_logs)}")

# Aggregate by day
daily_stats = defaultdict(lambda: {'entries': 0, 'total_cal': 0, 'items': []})
for entry in food_logs:
    d = entry['date']
    daily_stats[d]['entries'] += 1
    daily_stats[d]['total_cal'] += entry['calories']
    daily_stats[d]['items'].append(entry['name'])

print(f"Total days tracked: {len(daily_stats)}")

# Find overlapping period (dates where we have both gym data period AND food logs)
food_dates = set(daily_stats.keys())
gym_period_start = min(gym_dates)
gym_period_end = max(gym_dates)

# Only look at food log days within the gym data period
relevant_dates = [d for d in food_dates if gym_period_start <= d <= gym_period_end]
print(f"\nFood log days within gym data period ({gym_period_start} to {gym_period_end}): {len(relevant_dates)}")

# Categorize days
gym_day_stats = []
rest_day_stats = []

for date in relevant_dates:
    stats = daily_stats[date]
    day_data = {
        'date': date,
        'entries': stats['entries'],
        'total_cal': stats['total_cal'],
        'cal_per_entry': stats['total_cal'] / stats['entries'] if stats['entries'] > 0 else 0
    }
    
    if date in gym_dates:
        gym_day_stats.append(day_data)
    else:
        rest_day_stats.append(day_data)

print(f"\nDays categorized:")
print(f"  Gym days with food logs: {len(gym_day_stats)}")
print(f"  Rest days with food logs: {len(rest_day_stats)}")

# Calculate averages
def calc_averages(day_list, label):
    if not day_list:
        print(f"\n{label}: No data")
        return None
    
    total_entries = sum(d['entries'] for d in day_list)
    total_cal = sum(d['total_cal'] for d in day_list)
    n_days = len(day_list)
    
    avg_entries = total_entries / n_days
    avg_total_cal = total_cal / n_days
    avg_cal_per_entry = total_cal / total_entries if total_entries > 0 else 0
    
    # Also calculate median for robustness
    entries_list = sorted([d['entries'] for d in day_list])
    cal_list = sorted([d['total_cal'] for d in day_list])
    
    median_entries = entries_list[len(entries_list)//2]
    median_cal = cal_list[len(cal_list)//2]
    
    return {
        'n_days': n_days,
        'avg_entries': avg_entries,
        'median_entries': median_entries,
        'avg_total_cal': avg_total_cal,
        'median_total_cal': median_cal,
        'avg_cal_per_entry': avg_cal_per_entry
    }

gym_avgs = calc_averages(gym_day_stats, "Gym Days")
rest_avgs = calc_averages(rest_day_stats, "Rest Days")

print("\n" + "="*70)
print("ANALYSIS RESULTS")
print("="*70)

print(f"\n{'Metric':<30} {'Gym Days':>15} {'Rest Days':>15} {'Difference':>15}")
print("-"*70)

if gym_avgs and rest_avgs:
    # Number of entries per day
    entry_diff = gym_avgs['avg_entries'] - rest_avgs['avg_entries']
    entry_pct = (entry_diff / rest_avgs['avg_entries']) * 100 if rest_avgs['avg_entries'] > 0 else 0
    print(f"{'Avg entries/day':<30} {gym_avgs['avg_entries']:>15.1f} {rest_avgs['avg_entries']:>15.1f} {entry_diff:>+15.1f} ({entry_pct:+.0f}%)")
    print(f"{'Median entries/day':<30} {gym_avgs['median_entries']:>15.0f} {rest_avgs['median_entries']:>15.0f}")
    
    # Calories per entry
    cpe_diff = gym_avgs['avg_cal_per_entry'] - rest_avgs['avg_cal_per_entry']
    cpe_pct = (cpe_diff / rest_avgs['avg_cal_per_entry']) * 100 if rest_avgs['avg_cal_per_entry'] > 0 else 0
    print(f"{'Avg cal/entry':<30} {gym_avgs['avg_cal_per_entry']:>15.0f} {rest_avgs['avg_cal_per_entry']:>15.0f} {cpe_diff:>+15.0f} ({cpe_pct:+.0f}%)")
    
    # Total calories per day
    cal_diff = gym_avgs['avg_total_cal'] - rest_avgs['avg_total_cal']
    cal_pct = (cal_diff / rest_avgs['avg_total_cal']) * 100 if rest_avgs['avg_total_cal'] > 0 else 0
    print(f"{'Avg total cal/day':<30} {gym_avgs['avg_total_cal']:>15.0f} {rest_avgs['avg_total_cal']:>15.0f} {cal_diff:>+15.0f} ({cal_pct:+.0f}%)")
    print(f"{'Median total cal/day':<30} {gym_avgs['median_total_cal']:>15.0f} {rest_avgs['median_total_cal']:>15.0f}")
    
    print(f"\n{'Sample size (days)':<30} {gym_avgs['n_days']:>15} {rest_avgs['n_days']:>15}")

# Interpretation
print("\n" + "="*70)
print("INTERPRETATION")
print("="*70)

if gym_avgs and rest_avgs:
    print(f"""
Key Findings:
1. Entries per day: {'MORE' if entry_diff > 0 else 'FEWER'} entries on gym days ({entry_pct:+.0f}%)
2. Calories per entry: {'HIGHER' if cpe_diff > 0 else 'LOWER'} on gym days ({cpe_pct:+.0f}%)  
3. Total daily calories: {'HIGHER' if cal_diff > 0 else 'LOWER'} on gym days ({cal_pct:+.0f}%)
""")

    # Diagnosis
    if abs(entry_pct) > 15 and abs(cpe_pct) < 10:
        print("📊 VERDICT: TRACKING BIAS")
        print("   More entries but similar calories-per-entry suggests Rich")
        print("   logs MORE THOROUGHLY on gym days, not necessarily eating more.")
    elif abs(entry_pct) < 10 and abs(cpe_pct) > 15:
        print("🍔 VERDICT: ACTUALLY EATING MORE")
        print("   Similar entry counts but higher calories-per-entry suggests Rich")
        print("   actually EATS BIGGER PORTIONS on gym days.")
    elif entry_pct > 10 and cpe_pct > 10:
        print("📊🍔 VERDICT: BOTH - Tracks better AND eats more")
        print("   Both more entries AND higher calories per entry on gym days.")
    else:
        print("🤷 VERDICT: MINIMAL DIFFERENCE")
        print("   No significant pattern between gym and rest days.")

# Show some examples
print("\n" + "="*70)
print("SAMPLE DATA")
print("="*70)

print("\nRecent gym days with food logs:")
for day in sorted(gym_day_stats, key=lambda x: x['date'], reverse=True)[:5]:
    print(f"  {day['date']}: {day['entries']} entries, {day['total_cal']:.0f} cal")

print("\nRecent rest days with food logs:")
for day in sorted(rest_day_stats, key=lambda x: x['date'], reverse=True)[:5]:
    print(f"  {day['date']}: {day['entries']} entries, {day['total_cal']:.0f} cal")

# Statistical test (if enough data)
if len(gym_day_stats) >= 10 and len(rest_day_stats) >= 10:
    print("\n" + "="*70)
    print("STATISTICAL SIGNIFICANCE")
    print("="*70)
    try:
        from scipy import stats
        
        gym_entries = [d['entries'] for d in gym_day_stats]
        rest_entries = [d['entries'] for d in rest_day_stats]
        gym_cals = [d['total_cal'] for d in gym_day_stats]
        rest_cals = [d['total_cal'] for d in rest_day_stats]
        
        t_entries, p_entries = stats.ttest_ind(gym_entries, rest_entries)
        t_cals, p_cals = stats.ttest_ind(gym_cals, rest_cals)
        
        print(f"\nEntries/day: t={t_entries:.2f}, p={p_entries:.3f} {'*' if p_entries < 0.05 else '(not significant)'}")
        print(f"Calories/day: t={t_cals:.2f}, p={p_cals:.3f} {'*' if p_cals < 0.05 else '(not significant)'}")
    except ImportError:
        print("\n(scipy not available for statistical tests)")
