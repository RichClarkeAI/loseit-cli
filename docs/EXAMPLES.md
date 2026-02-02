# Example Usage

## Search for a Food

```bash
$ python3 loseit-log.py "apple" --search
🔍 Searching: apple

  #  Food                                               Brand
───  ────────────────────────────────────────────────── ────────────────────
  1  Apple, Fuji, Medium                                
  2  Apple, Honeycrisp, Large                           
  3  Apple, Gala, Small                                 
  4  Apple, Granny Smith, Medium                        
  5  Apple, Medium                                      
  6  Apple, Honeycrisp, Medium Size                     Trader Joe's
```

## Log a Food Entry

```bash
$ python3 loseit-log.py "banana" -m breakfast --pick 1
🔍 Searching: banana

  #  Food                                               Brand
───  ────────────────────────────────────────────────── ────────────────────
  1  Banana, Medium, 7" - 7 7/8" Long                   

  Selected: Banana, Medium, 7" - 7 7/8" Long
  PK bytes: [46, -70, -82, -29, 2, -110, 91, -119, -14, 69, -20, -76, -61, 0, 44, 81]
✅ Logged successfully!
   📦 Banana, Medium, 7" - 7 7/8" Long
   🍽️  Meal: Breakfast
   📅 Date: 2026-02-02 (day 9164)
   🔥 Calories (scaled): 105
```

## Log with Custom Servings

```bash
$ python3 loseit-log.py "greek yogurt" -m snacks --pick 1 --servings 2
✅ Logged successfully!
   📦 Greek Yogurt, Plain, Nonfat
   🍽️  Meal: Snacks
   📅 Date: 2026-02-02
   🔢 Servings: 2
   🔥 Calories (scaled): 200
```

## Log to a Different Date

```bash
$ python3 loseit-log.py "grilled salmon" -m dinner --pick 1 --date 2026-02-01
✅ Logged successfully!
   📦 Fish, Salmon, Filet, Grilled, Lemon Herb
   🍽️  Meal: Dinner
   📅 Date: 2026-02-01 (day 9163)
   🔥 Calories (scaled): 180
```

## Download Your Data

```bash
$ ./loseit-sync.sh
[loseit-sync] Starting export download...
[loseit-sync] Launching Playwright to grab cookies...
[loseit-sync] Got 12 cookies, downloading export...
[loseit-sync] Saved 245832 bytes to data/loseit-export.zip
[loseit-sync] Unzipping export...
[loseit-sync] Done! Data in data/export
```

## Analyze Your Data

```bash
$ ./loseit-analyze.sh
[loseit-analyze] Analyzing data...
[loseit-analyze] Done! Report saved to data/latest-report.json

$ cat data/latest-report.json
{
  "generated_at": "2026-02-02T14:35:12Z",
  "averages": {
    "7_day": {
      "calories": 1847.3,
      "protein_g": 89.2,
      "carbs_g": 201.4,
      "fat_g": 67.8
    },
    "30_day": {
      "calories": 1923.5,
      "protein_g": 92.1,
      "carbs_g": 215.3,
      "fat_g": 71.2
    }
  },
  "weight": {
    "current_lbs": 172.0,
    "start_lbs": 191.0,
    "goal_lbs": 160.0,
    "lost_lbs": 19.0
  }
}
```

## Debug Mode

```bash
$ python3 loseit-log.py "banana" -m snacks --pick 1 --debug
🔍 Searching: banana
  📤 Payload (361 chars): 7|0|12|https://d3hsih69yn4d89.cloudfront...
  📥 HTTP 200, 2459 chars

  String table (37 entries):
    [1] com.loseit.core.client.service.responses...
    [2] java.lang.Integer/3438268394
    ...

  Selected: Banana, Medium, 7" - 7 7/8" Long
  📤 Payload (571 chars): 7|0|13|https://d3hsih69yn4d89...
  📥 HTTP 200, 1826 chars
  
✅ Logged successfully!
```
