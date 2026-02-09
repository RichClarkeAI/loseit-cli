#!/usr/bin/env bash
# loseit-analyze.sh — Analyze Lose It! export CSVs and produce a JSON report
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPORT_DIR="$SCRIPT_DIR/data/export"
REPORT_FILE="$SCRIPT_DIR/data/latest-report.json"
VENV="$HOME/clawd/email-triage/venv"

if [ ! -d "$EXPORT_DIR" ]; then
    echo "[loseit-analyze] ERROR: No export data at $EXPORT_DIR — run loseit-sync.sh first"
    exit 1
fi

echo "[loseit-analyze] Analyzing data..."

"$VENV/bin/python3" - "$EXPORT_DIR" "$REPORT_FILE" <<'PYEOF'
import sys, json, csv, os
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

export_dir = Path(sys.argv[1])
report_path = sys.argv[2]

now = datetime.now()
today = now.date()

def parse_date(s):
    """Try common date formats."""
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None

def safe_float(v, default=0.0):
    try:
        return float(v)
    except (ValueError, TypeError):
        return default

def read_csv(name):
    path = export_dir / name
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

# ── Load data ──
food_logs = read_csv("food-logs.csv")
daily_cals = read_csv("daily-calorie-summary.csv")
weights = read_csv("weights.csv")
protein_log = read_csv("protein(g).csv")
fasting_logs = read_csv("fasting-logs.csv")
exercise_logs = read_csv("exercise-logs.csv")
profile_rows = read_csv("profile.csv")

# Profile
profile = {}
for row in profile_rows:
    name = row.get("Name", "").strip()
    val = row.get("Value", "").strip()
    if name and val:
        profile[name] = val

# ── Food logs analysis ──
# Filter out deleted
active_food = [r for r in food_logs if r.get("Deleted", "").strip().lower() != "true"]

# Group by date
food_by_date = defaultdict(list)
for r in active_food:
    d = parse_date(r.get("Date", ""))
    if d:
        food_by_date[d].append(r)

def period_stats(days):
    cutoff = today - timedelta(days=days)
    period_dates = {d: entries for d, entries in food_by_date.items() if d > cutoff}
    if not period_dates:
        return {"days_logged": 0, "avg_calories": 0, "avg_protein": 0, "avg_carbs": 0, "avg_fat": 0, "total_days": days}

    daily_totals = []
    for d, entries in sorted(period_dates.items()):
        cals = sum(safe_float(e.get("Calories")) for e in entries)
        protein = sum(safe_float(e.get("Protein (g)")) for e in entries)
        carbs = sum(safe_float(e.get("Carbohydrates (g)")) for e in entries)
        fat = sum(safe_float(e.get("Fat (g)")) for e in entries)
        daily_totals.append({"date": str(d), "calories": round(cals), "protein": round(protein, 1),
                             "carbs": round(carbs, 1), "fat": round(fat, 1)})

    n = len(daily_totals)
    return {
        "days_logged": n,
        "total_days": days,
        "consistency_pct": round(n / days * 100, 1),
        "avg_calories": round(sum(t["calories"] for t in daily_totals) / n),
        "avg_protein": round(sum(t["protein"] for t in daily_totals) / n, 1),
        "avg_carbs": round(sum(t["carbs"] for t in daily_totals) / n, 1),
        "avg_fat": round(sum(t["fat"] for t in daily_totals) / n, 1),
        "daily_breakdown": daily_totals[-7:],  # last 7 entries for detail
    }

stats_7d = period_stats(7)
stats_30d = period_stats(30)

# Days since last food log
food_dates = sorted(food_by_date.keys())
days_since_food = (today - food_dates[-1]).days if food_dates else None

# ── Calorie trend from daily summary ──
cal_summary_by_date = {}
for r in daily_cals:
    d = parse_date(r.get("Date", ""))
    if d:
        cal_summary_by_date[d] = {
            "food_cals": safe_float(r.get("Food cals")),
            "exercise_cals": safe_float(r.get("Exercise cals")),
            "budget_cals": safe_float(r.get("Budget cals")),
        }

# ── Weight trend ──
active_weights = [r for r in weights if r.get("Deleted", "").strip().lower() != "true"]
weight_entries = []
for r in active_weights:
    d = parse_date(r.get("Date", ""))
    w = safe_float(r.get("Weight"))
    if d and w > 0:
        weight_entries.append({"date": str(d), "weight": round(w, 1), "date_obj": d})

weight_entries.sort(key=lambda x: x["date_obj"])
days_since_weighin = (today - weight_entries[-1]["date_obj"]).days if weight_entries else None

# Weight trend: last 10 entries
recent_weights = [{"date": w["date"], "weight": w["weight"]} for w in weight_entries[-10:]]
weight_change_30d = None
if len(weight_entries) >= 2:
    cutoff_30 = today - timedelta(days=30)
    older = [w for w in weight_entries if w["date_obj"] <= cutoff_30]
    newer = weight_entries[-1]
    if older:
        weight_change_30d = round(newer["weight"] - older[-1]["weight"], 1)

# ── Protein goal tracking (target 150g/day) ──
PROTEIN_TARGET = 150
protein_30d_avg = stats_30d.get("avg_protein", 0)
protein_7d_avg = stats_7d.get("avg_protein", 0)
protein_goal_pct_30d = round(protein_30d_avg / PROTEIN_TARGET * 100, 1) if PROTEIN_TARGET else 0
protein_goal_pct_7d = round(protein_7d_avg / PROTEIN_TARGET * 100, 1) if PROTEIN_TARGET else 0

# ── Fasting compliance ──
active_fasts = [r for r in fasting_logs if r.get("Deleted", "").strip().lower() != "true"]

def parse_datetime(s):
    for fmt in ("%m/%d/%Y %I:%M %p", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None

fasting_stats = {"total_fasts": len(active_fasts), "completed": 0, "recent_fasts": []}
cutoff_30 = now - timedelta(days=30)
recent_fasts = []
for f in active_fasts:
    actual_start = parse_datetime(f.get("Actual start", ""))
    actual_end = parse_datetime(f.get("Actual end", ""))
    scheduled_dur = f.get("Scheduled duration", "").strip()

    completed = actual_start is not None and actual_end is not None
    if completed:
        fasting_stats["completed"] += 1
        duration_hrs = (actual_end - actual_start).total_seconds() / 3600
        if actual_start >= cutoff_30:
            recent_fasts.append({
                "start": str(actual_start),
                "end": str(actual_end),
                "duration_hrs": round(duration_hrs, 1),
                "scheduled": scheduled_dur,
            })

fasting_stats["recent_fasts"] = recent_fasts[-5:]  # last 5
fasting_stats["fasts_last_30d"] = len(recent_fasts)
if fasting_stats["completed"] > 0:
    fasting_stats["completion_rate_pct"] = round(fasting_stats["completed"] / fasting_stats["total_fasts"] * 100, 1)

# ── Build report ──
report = {
    "generated_at": now.isoformat(),
    "profile": profile,
    "summary": {
        "days_since_last_food_log": days_since_food,
        "days_since_last_weighin": days_since_weighin,
        "latest_weight": weight_entries[-1]["weight"] if weight_entries else None,
        "weight_change_30d": weight_change_30d,
    },
    "last_7_days": {
        "days_logged": stats_7d["days_logged"],
        "consistency_pct": stats_7d.get("consistency_pct", 0),
        "avg_calories": stats_7d["avg_calories"],
        "macros": {
            "avg_protein_g": stats_7d["avg_protein"],
            "avg_carbs_g": stats_7d["avg_carbs"],
            "avg_fat_g": stats_7d["avg_fat"],
        },
        "protein_goal_pct": protein_goal_pct_7d,
        "daily_breakdown": stats_7d.get("daily_breakdown", []),
    },
    "last_30_days": {
        "days_logged": stats_30d["days_logged"],
        "consistency_pct": stats_30d.get("consistency_pct", 0),
        "avg_calories": stats_30d["avg_calories"],
        "macros": {
            "avg_protein_g": stats_30d["avg_protein"],
            "avg_carbs_g": stats_30d["avg_carbs"],
            "avg_fat_g": stats_30d["avg_fat"],
        },
        "protein_goal_pct": protein_goal_pct_30d,
    },
    "protein_tracking": {
        "daily_target_g": PROTEIN_TARGET,
        "avg_7d": protein_7d_avg,
        "avg_30d": protein_30d_avg,
        "on_track": protein_30d_avg >= PROTEIN_TARGET * 0.9,
    },
    "weight_trend": recent_weights,
    "fasting": fasting_stats,
    "data_range": {
        "first_food_log": str(food_dates[0]) if food_dates else None,
        "last_food_log": str(food_dates[-1]) if food_dates else None,
        "total_food_log_days": len(food_by_date),
        "total_weight_entries": len(weight_entries),
    },
}

with open(report_path, "w") as f:
    json.dump(report, f, indent=2)

print(f"[loseit-analyze] Report saved to {report_path}")
print(f"  Last food log: {days_since_food} days ago" if days_since_food is not None else "  No food logs found")
print(f"  Last weigh-in: {days_since_weighin} days ago" if days_since_weighin is not None else "  No weight entries found")
print(f"  30d avg calories: {stats_30d['avg_calories']}")
print(f"  30d avg protein: {protein_30d_avg}g / {PROTEIN_TARGET}g target ({protein_goal_pct_30d}%)")
print(f"  30d consistency: {stats_30d.get('consistency_pct', 0)}%")
if weight_entries:
    print(f"  Current weight: {weight_entries[-1]['weight']} lbs")
if weight_change_30d is not None:
    direction = "↓" if weight_change_30d < 0 else "↑" if weight_change_30d > 0 else "→"
    print(f"  30d weight change: {direction} {abs(weight_change_30d)} lbs")
PYEOF

echo "[loseit-analyze] Done!"
