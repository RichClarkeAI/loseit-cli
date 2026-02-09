# Changelog

All notable changes to Lose It! CLI will be documented in this file.

## [1.0.0] - 2026-02-02

### Added
- **CSV Export Download** (`loseit-sync.sh`)
  - Downloads complete data export from Lose It
  - Extracts to `data/export/` with all historical CSVs
  - Uses Playwright for cookie-based authentication

- **Data Analysis** (`loseit-analyze.sh`)
  - Generates JSON report from CSV exports
  - 7-day and 30-day calorie averages
  - Weight progress tracking
  - Most logged foods
  - Nutrient patterns

- **Food Search** (`loseit-log.py --search`)
  - Search Lose It's food database from CLI
  - Shows top 15 results with brands
  - Heuristic name/brand parsing

- **Food Logging** (`loseit-log.py`)
  - Log foods to breakfast, lunch, dinner, or snacks
  - Custom serving sizes (default: 1)
  - Custom dates (default: today)
  - Supports 9 core nutrients (calories, fat, carbs, protein, etc.)
  - Three-step GWT-RPC workflow:
    1. searchFoods
    2. getUnsavedFoodLogEntry
    3. updateFoodLogEntry

- **Authentication**
  - Token-based auth via `~/.config/loseit/token`
  - Uses browser session cookie (`liauth`)
  - ~2 week token lifetime

- **Debug Mode**
  - `--debug` flag shows full GWT-RPC payloads and responses
  - Useful for troubleshooting API issues

### Technical Details
- Reverse-engineered GWT-RPC protocol
- Fixed GWT byte array serialization (must reverse)
- Fixed nutrient filtering (server only accepts 9 core ordinals)
- Fixed day_key source (comes from unsaved response, not init data)
- Day number calculation using anchor date

### Known Limitations
- Cannot query existing diary entries
- Cannot delete entries programmatically
- Cannot edit existing entries
- Token must be manually refreshed
- Search brand parsing is heuristic/imperfect
- Only works with Lose It database foods

## [Unreleased] - Future

### Planned for v2.0
- Query diary entries for a given day
- Delete entries by UUID
- Edit existing entries (change servings/meal)
- Automatic token refresh
- Bulk import from CSV
- Custom food support
- Better search result parsing
- Workout logging
- Weight logging

---

## Version History

- **1.0.0** (2026-02-02) - Initial release with export, analysis, search, and logging
