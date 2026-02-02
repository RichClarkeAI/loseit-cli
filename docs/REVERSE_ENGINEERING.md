# Reverse Engineering the Lose It! API

A technical deep-dive into how we built a CLI for Lose It by reverse-engineering their GWT-RPC protocol.

## Background

Lose It! is a popular calorie tracking app, but they don't provide a public API. As a long-time user, I wanted to:
- Export my data programmatically
- Log foods from the command line
- Analyze my nutrition trends

Since there's no official API, I had to reverse-engineer their web app's private API.

## Discovery: GWT-RPC Protocol

Opening the browser DevTools while using https://www.loseit.com/, I noticed all API calls went to a single endpoint:

```
POST https://www.loseit.com/web/service
Content-Type: text/x-gwt-rpc; charset=UTF-8
```

The payload looked like gibberish at first:

```
7|0|12|https://d3hsih69yn4d89.cloudfront.net/web/|5ED2771F63B26294E45551B2D697E7B0|com.loseit.core.client.service.LoseItRemoteService|searchFoods|...
```

After research, I learned this is **GWT-RPC** (Google Web Toolkit Remote Procedure Call) - a protocol for Java web apps that serializes method calls to a compact pipe-delimited format.

## GWT-RPC Format

### Request Structure

```
7|0|<string_count>|<string_table>|<method_signature>|<parameters>
```

**Components:**
1. **Version markers** (`7|0`) - GWT protocol version
2. **String table** - Deduplicated strings referenced by index
3. **Method signature** - Service name, method name, parameter types
4. **Parameter values** - Serialized using string table references

### Example: searchFoods

```
7|0|12|
  https://d3hsih69yn4d89.cloudfront.net/web/|
  5ED2771F63B26294E45551B2D697E7B0|
  com.loseit.core.client.service.LoseItRemoteService|
  searchFoods|
  com.loseit.core.client.service.ServiceRequestToken/1076571655|
  java.lang.String/2004016611|
  I|Z|
  com.loseit.core.client.model.UserId/4281239478|
  Rich|
  banana|
  en-US|
1|2|3|4|6|5|6|6|7|8|8|5|0|9|47596378|10|-5|11|12|15|1|1|
```

Breaking it down:
- Strings 1-4: URL, hash, service, method
- Strings 5-12: Type references and parameters
- Data section: `1|2|3|4` = method refs, `6` = param count, `5|6|6|7|8|8` = param types, followed by values

### Response Structure

```
//OK[<data_tokens>,<string_table>]
```

Responses are even more complex - data is serialized **in reverse order** with backreferences to avoid duplication.

## Authentication

Lose It uses JWT tokens in cookies:
- `liauth` - Main auth token
- `fn_auth` - Secondary auth token

Both must be sent with requests. Tokens last ~2 weeks before expiring.

## Key Challenges

### 1. Byte Array Reversal

The first major bug I hit: logging foods would return HTTP 200 but entries wouldn't appear.

**The issue:** GWT serializes byte arrays (like UUIDs) **in reverse order**.

When sending a food's primary key:
```python
pk_bytes = [46, -70, -82, -29, 2, -110, 91, -119, -14, 69, -20, -76, -61, 0, 44, 81]
```

You must reverse it before serialization:
```python
payload += [str(int(b)) for b in reversed(pk_bytes)]
```

This took hours to debug - the server would accept the request but silently fail to save.

### 2. Nutrient Filtering

Foods have 28+ nutrient measurements, but the server **only accepts 9 core ordinals**:

```python
CORE_NUTRIENT_ORDINALS = {0, 2, 3, 8, 9, 10, 11, 12, 13}
# 0=Energy, 2=Fat, 3=SatFat, 8=Cholesterol, 9=Sodium,
# 10=Carbs, 11=Fiber, 12=Sugar, 13=Protein
```

Sending all 28 nutrients caused HTTP 500 errors. Filtering to just these 9 fixed it.

### 3. Day Key Mystery

Each diary date has a unique "day key" like `"Zwc78Lo"`. These keys are:
- Base64-encoded
- Server-generated
- Required for logging entries

**Problem:** How do you get today's day key?

I tried:
1. ❌ `getInitializationData` - only returns past days
2. ❌ Predicting the key - middle bytes are hashed
3. ✅ **Solution:** `getUnsavedFoodLogEntry` response includes the current day's key

### 4. Day Number Calculation

Day numbers are sequential integers (e.g., `9164` = Feb 2, 2026). To log to custom dates, you need to calculate the day number.

**Solution:** Use an anchor date:
```python
_DAYNUM_ANCHOR = (date(2026, 2, 2), 9164)

def day_number_for(target_date):
    anchor_date, anchor_num = _DAYNUM_ANCHOR
    return anchor_num + (target_date - anchor_date).days
```

Initially I had the anchor off by one day, causing all my test entries to appear on the wrong date!

## The Logging Flow

After reverse-engineering, the complete flow is:

### 1. Search for Food
```
POST /web/service
Method: searchFoods(token, query, locale, ...)
Returns: List of foods with name, brand, primary key
```

### 2. Get Nutrient Template
```
Method: getUnsavedFoodLogEntry(token, food_pk, locale, name)
Returns: Pre-populated entry with:
  - All nutrients for this food
  - Current day key
  - Serving size defaults
```

### 3. Save to Diary
```
Method: updateFoodLogEntry(token, entry)
Entry includes:
  - Food identifier (name, brand, category, PK)
  - Meal type (0=breakfast, 1=lunch, 2=dinner, 3=snacks)
  - Day number + day key
  - Nutrients (filtered to 9 core ordinals)
  - Serving size
  - Generated entry UUID
```

## Tools Used

### Playwright for Cookie Extraction
The CSV export requires authenticated browser cookies:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(profile_dir, headless=True)
    page = context.new_page()
    page.goto("https://www.loseit.com")
    cookies = context.cookies("https://www.loseit.com")
    
# Use cookies with requests
session = requests.Session()
session.cookies.update({c["name"]: c["value"] for c in cookies})
```

### Network Capture for Protocol Analysis
I wrote custom Playwright scripts to:
1. Navigate to Lose It
2. Intercept all GWT-RPC requests/responses  
3. Save payloads to files for analysis

Example:
```python
def on_request(request):
    if "service" in request.url and "gwt-rpc" in request.headers.get("content-type", ""):
        body = request.post_data
        # Parse method name from payload
        label = extract_method_name(body)
        save_to_file(f"{label}_request.txt", body)
```

### Manual Payload Construction
The hardest part was building valid GWT-RPC payloads from scratch. I:
1. Captured real payloads (e.g., logging Chobani yogurt)
2. Identified the pattern (string table indices, parameter ordering)
3. Built Python functions to generate payloads programmatically
4. Tested extensively with different foods/dates/servings

## Gotchas & Pitfalls

### Integer vs Float Serialization
GWT distinguishes `1` (int) from `1.0` (float). Sending `str(1.0)` when the server expects an int causes silent failures.

**Solution:** Cast to int when appropriate:
```python
servings_str = str(int(servings)) if servings == int(servings) else str(servings)
```

### Empty Strings in String Table
Empty strings (`""`) are valid and appear in the string table. They're not null - they're actual empty strings that get referenced.

### Type References
Every Java class has a "type reference" like:
```
com.loseit.core.client.model.FoodLogEntry/264522954
```

The number after `/` is a hash. You must use the exact reference from the serialization policy file (`.gwt.rpc`).

### Response Parsing
GWT responses use **backreferences** - objects are serialized once, then referenced by negative indices. Example:

```
[..., 5, -1, ...]  // -1 means "reference object at position 5"
```

This makes parsing responses harder than requests.

## What We Couldn't Figure Out (Yet)

### Query Diary Entries
We can LOG entries but can't yet QUERY what's already in the diary. The method exists (`getDailyLogEntries` or similar) but we haven't found the correct signature.

**Blocked features:**
- Delete entries (need UUIDs from query)
- Edit entries (need to fetch current entry)

### Token Refresh
Tokens expire after ~2 weeks. The app must have a refresh mechanism, but we haven't found it. For now, users must manually extract a fresh token from browser cookies.

## Performance

The CLI is surprisingly fast:
- Search: ~200ms
- Log entry: ~500ms (3 API calls)
- CSV export: ~3 seconds

Comparable to the web UI since we're hitting the same backend.

## Ethical Considerations

**Why this is (probably) okay:**
- Personal use only - accessing your own data
- No bypassing paid features (export is free)
- No scraping/bulk downloading others' data
- Minimal server load (same as using the web UI)

**Why Lose It might not like it:**
- Uses undocumented private API
- Could enable automation/bots
- No rate limiting implemented

**Recommendation:** Use responsibly. Don't abuse it. If Lose It asks us to take it down, we will.

## Lessons Learned

1. **Network DevTools are invaluable** - Inspecting actual traffic is way faster than guessing
2. **Save everything** - Capture payloads early and often for comparison
3. **Test incrementally** - Build one method at a time, verify it works before moving on
4. **Off-by-one errors are everywhere** - Especially with date/time and array indexing
5. **When in doubt, copy-paste** - If a payload works, template it rather than rebuilding from scratch

## Future Work

### Planned Features
- Automatic token refresh (intercept refresh API call)
- Query diary entries (find correct method signature)
- Delete/edit entries (depends on query)
- Bulk import from CSV
- Workout logging
- Weight logging

### Code Improvements
- Better error messages
- Retry logic for network failures
- Type hints throughout
- Unit tests (mocking GWT-RPC responses)
- Integration tests

## Conclusion

Reverse-engineering closed APIs is part detective work, part trial-and-error. The Lose It GWT-RPC protocol was particularly challenging due to:
- Unusual serialization format
- Byte array reversal quirk
- Minimal documentation
- Complex nested object structures

But now we have a working CLI that:
- Downloads full export
- Analyzes nutrition trends
- Logs foods programmatically

**Total time invested:** ~8 hours of debugging across 2 days

**Lines of code:** ~1000 (including parsers, CLI, docs)

**Would I do it again?** Absolutely. It's incredibly satisfying to crack a complex protocol and build something useful from it.

---

*Questions? Found a bug? Contributions welcome!*

**GitHub:** https://github.com/richclarke/loseit-cli (to be published)
