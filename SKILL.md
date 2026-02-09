---
name: loseit
description: Lose It! nutrition tracking CLI. Log foods, search the database, sync exports, and analyze nutrition data. Use when tracking calories, logging meals, searching foods, or analyzing nutrition history with Lose It!
---

# Lose It! CLI

Unofficial CLI tools for Lose It! nutrition tracking - log foods, search database, download exports, and analyze nutrition.

## Prerequisites

- Python 3.8+
- Lose It! account
- Auth token at `~/.config/loseit/token` (from browser cookie `liauth`)

## Quick Reference

### Log Food

```bash
# Search foods
python3 loseit-log.py "chicken breast" --search

# Log with auto-pick first result
python3 loseit-log.py "banana" -m breakfast --pick 1

# Log with servings
python3 loseit-log.py "greek yogurt" -m snacks --pick 2 --servings 1.5

# Log to specific date
python3 loseit-log.py "eggs" -m breakfast --pick 1 --date 2026-01-31
```

**Meals:** `breakfast`, `lunch`, `dinner`, `snacks`

### Sync & Analyze

```bash
# Download full CSV export
./loseit-sync.sh

# Generate analysis report
./loseit-analyze.sh
```

Creates `data/export/` with CSVs and `data/latest-report.json` with insights.

### Personal Food Database

For frequently logged foods with custom portion sizes:

```bash
# Build personal DB from export history
./build-personal-db.sh

# Log using personal DB (faster, remembers your portions)
python3 loseit-log.py "scrambled eggs" -m breakfast --personal
```

## API Notes

- Uses reverse-engineered GWT-RPC protocol
- Token expires ~2 weeks; refresh from browser cookies
- Tracks: calories, fat, sat fat, cholesterol, sodium, carbs, fiber, sugar, protein

## Files

| File | Purpose |
|------|---------|
| `loseit-log.py` | Search & log foods (main CLI) |
| `loseit-sync.sh` | Download CSV export |
| `loseit-analyze.sh` | Generate analysis JSON |
| `build-personal-db.sh` | Build personal food DB |
| `data/export/` | Downloaded CSVs |
| `data/personal-foods.json` | Your frequent foods |

## Token Setup

1. Log into https://www.loseit.com/
2. DevTools → Application → Cookies → copy `liauth` value
3. Save: `echo "TOKEN" > ~/.config/loseit/token && chmod 600 ~/.config/loseit/token`
