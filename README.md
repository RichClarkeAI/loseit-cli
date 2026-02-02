# Lose It! CLI

Unofficial command-line tools for Lose It! - download your data, log foods, and analyze your nutrition history.

⚠️ **Unofficial & Experimental** - This is a reverse-engineered implementation of Lose It's private API. Use at your own risk.

## Features

### ✅ Working
- **Download full export** - Get all your historical data as CSV files
- **Analyze trends** - Generate JSON reports with averages, streaks, and insights
- **Search foods** - Search Lose It's database from the command line
- **Log entries** - Add foods to your diary with custom servings and dates
- **Multiple meals** - Breakfast, lunch, dinner, snacks

### ⏳ Planned (v2.0)
- Query today's diary
- Delete entries
- Edit existing entries
- Token auto-refresh

## Installation

### Prerequisites
- Python 3.8+
- Lose It! account with valid login

### Setup

1. **Install Python dependencies:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install playwright requests
playwright install chromium
```

2. **Get your authentication token:**

Open your browser, log into https://www.loseit.com/, then:

**Chrome/Edge:**
- Press F12 → Application tab → Cookies → www.loseit.com
- Copy the value of `liauth` cookie

**Firefox:**
- Press F12 → Storage tab → Cookies → www.loseit.com
- Copy the value of `liauth` cookie

3. **Save your token:**
```bash
mkdir -p ~/.config/loseit
echo "YOUR_TOKEN_HERE" > ~/.config/loseit/token
chmod 600 ~/.config/loseit/token
```

## Usage

### Download Your Data

Download full export (all history as CSVs):
```bash
./loseit-sync.sh
```

Creates `data/export/` with:
- `food-logs.csv` - Every food you've logged
- `daily-calorie-summary.csv` - Daily totals
- `weights.csv` - Weight history
- `exercise-logs.csv` - Workouts
- `custom-foods.csv` - Foods you created
- Plus profile, recipes, notes, etc.

### Analyze Your Data

Generate insights from your export:
```bash
./loseit-analyze.sh
```

Creates `data/latest-report.json` with:
- 7-day and 30-day calorie averages
- Weight progress
- Most frequently logged foods
- Streak information
- Nutrient patterns

### Log Food

Search for a food:
```bash
python3 loseit-log.py "chicken breast" --search
```

Log a food entry:
```bash
# Basic usage
python3 loseit-log.py "banana" -m breakfast --pick 1

# With custom servings
python3 loseit-log.py "greek yogurt" -m snacks --pick 2 --servings 2

# Custom date
python3 loseit-log.py "eggs" -m breakfast --pick 1 --date 2026-01-31
```

**Meals:** `breakfast`, `lunch`, `dinner`, `snacks`

### Examples

```bash
# Search and log an apple
python3 loseit-log.py "honeycrisp apple" -m snacks --pick 1

# Log 6oz grilled salmon to dinner
python3 loseit-log.py "grilled salmon" -m dinner --pick 1 --servings 1.5

# Log coffee from yesterday
python3 loseit-log.py "coffee black" -m breakfast --pick 1 --date 2026-02-01

# Debug mode (see API calls)
python3 loseit-log.py "banana" -m snacks --pick 1 --debug
```

## How It Works

### Authentication
Uses your browser's session cookie (`liauth` token). Tokens typically last ~2 weeks before expiring.

### Data Export
- Uses Playwright to authenticate with your Lose It session
- Downloads the official CSV export from `loseit.com/export/data`
- Extracts all historical data

### Food Logging
- Reverse-engineered GWT-RPC protocol (Google Web Toolkit)
- Three-step process:
  1. `searchFoods` - Search Lose It database
  2. `getUnsavedFoodLogEntry` - Get nutrient template for selected food
  3. `updateFoodLogEntry` - Save entry to diary

### Supported Nutrients
The API tracks 9 core nutrients:
- Calories (Energy)
- Fat
- Saturated Fat
- Cholesterol
- Sodium
- Carbohydrates
- Fiber
- Sugar
- Protein

## Limitations

- **Read-only for now** (except logging new entries)
- Can't query existing diary entries yet
- Can't delete or edit existing entries
- Token must be manually refreshed every ~2 weeks
- Search result parsing is heuristic (brands may be wrong)
- Only works with Lose It database foods (no custom foods yet)

## Troubleshooting

### "No token" error
Make sure your token is saved to `~/.config/loseit/token`:
```bash
cat ~/.config/loseit/token
# Should show a long string of characters
```

### "HTTP 401" or "HTTP 403"
Your token expired. Get a fresh one from your browser cookies.

### Entries not showing up
- Check you're viewing the correct date in the Lose It app
- Verify with `--debug` flag to see the actual API responses
- The app may take a few seconds to sync

### Search returns weird results
The search result parser is heuristic - sometimes brands get mixed up. Pick the entry that looks right based on the name.

## Files

```
loseit/
├── loseit-sync.sh          # Download CSV export
├── loseit-analyze.sh       # Analyze export data
├── loseit-log.py          # Search & log foods (main CLI)
├── data/
│   ├── export/            # CSV exports
│   ├── latest-report.json # Analysis output
│   └── last-sync.json     # Sync status
└── README.md              # This file
```

## Contributing

This is a reverse-engineered project. Contributions welcome, but note:
- Lose It could change their API at any time
- No official API documentation exists
- GWT-RPC protocol is complex and brittle

## Disclaimer

**This is an unofficial, unsupported tool.** 

- Not affiliated with or endorsed by Lose It! / FitNow, Inc.
- Use at your own risk
- May break if Lose It updates their API
- Your account could potentially be banned for API usage (though unlikely)
- No warranty or support provided

## License

MIT License - see LICENSE file

## Credits

Reverse-engineered by analyzing GWT-RPC network traffic from https://www.loseit.com/

Built with:
- Python 3
- Playwright (browser automation)
- Requests (HTTP client)
- A lot of patience debugging GWT serialization formats

---

**Star this repo if you find it useful!** 🌟
