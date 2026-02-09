# updateFoodLogEntry - GWT-RPC Payload Analysis

## String Table (28 entries, 1-indexed)
1. `https://d3hsih69yn4d89.cloudfront.net/web/` (base URL)
2. `5ED2771F63B26294E45551B2D697E7B0` (policy hash)
3. `com.loseit.core.client.service.LoseItRemoteService` (service)
4. `updateFoodLogEntry` (METHOD NAME!)
5. `com.loseit.core.client.service.ServiceRequestToken/1076571655`
6. `com.loseit.core.client.model.FoodLogEntry/264522954`
7. `com.loseit.core.client.model.UserId/4281239478`
8. `Rich` (user display name)
9. `com.loseit.core.client.model.FoodIdentifier/2763145970`
10. `Yogurt` (food category/search term?)
11. `en-US` (locale)
12. `Greek Yogurt, Strawberry, Non Fat` (food name)
13. `Chobani` (brand)
14. `com.loseit.core.client.model.interfaces.FoodProductType/2860616120`
15. `com.loseit.healthdata.model.shared.Verification/3485154600`
16. `com.loseit.core.client.model.SimplePrimaryKey/3621315060`
17. `[B/3308590456` (byte array)
18. `com.loseit.core.client.model.FoodLogEntryContext/4082213671`
19. `com.loseit.core.shared.model.DayDate/1611136587`
20. `java.util.Date/3385151746`
21. `com.loseit.core.client.model.interfaces.FoodLogEntryType/1152459170`
22. `com.loseit.core.client.model.FoodServing/1858865662`
23. `com.loseit.core.client.model.FoodNutrients/1097231324`
24. `java.util.HashMap/1797211028`
25. `com.loseit.healthdata.model.shared.food.FoodMeasurement/2371921172`
26. `java.lang.Double/858496421`
27. `com.loseit.core.client.model.FoodServingSize/63998910`
28. `com.loseit.core.client.model.FoodMeasure/1457474932`

## Method Signature
`updateFoodLogEntry(ServiceRequestToken, FoodLogEntry)` — 2 params

## Data Section (after string table)
```
1|2|3|4|        → header: string1=baseURL, string2=hash, string3=service, string4=method
2|              → 2 parameters
5|6|            → param types: ServiceRequestToken, FoodLogEntry

5|0|            → ServiceRequestToken: token=0 (null/empty)
7|47596378|8|-5| → UserId(47596378), name="Rich", offset=-5

6|              → FoodLogEntry object:
9|-1|10|11|12|13| → FoodIdentifier(-1?), "Yogurt", "en-US", "Greek Yogurt...", "Chobani"
14|0|-1|        → FoodProductType(0), verification(-1?)
15|0|           → Verification(0)
ZwdI0HK|        → SimplePrimaryKey (food ID!)
16|17|          → SimplePrimaryKey type, byte array type
16|17|-115|-32|94|82|-48|75|64|-95|55|52|-122|-82|-16|-48|120| → primary key bytes
18|0|           → FoodLogEntryContext
19|20|ZwdImkw|  → DayDate, Date, date value "ZwdImkw"
9164|-5|        → day number? timezone offset
0|-1|-1|        → ?
0|0|0|          → ?
21|1|0|         → FoodLogEntryType(1=Snack?), 0
22|23|          → FoodServing, FoodNutrients
1|2|            → serving count=1, servings=2?
24|9|           → HashMap with 9 entries (nutrients!)

## Nutrients (FoodMeasurement enum → Double value)
25|9|26|55      → FoodMeasurement[9]=? → 55.0 (probably calories? no, too low)
25|2|26|150     → FoodMeasurement[2]=? → 150.0 (calories!)
25|13|26|11     → FoodMeasurement[13]=? → 11.0
25|3|26|0       → FoodMeasurement[3]=? → 0.0
25|0|26|110     → FoodMeasurement[0]=? → 110.0
25|11|26|0      → FoodMeasurement[11]=? → 0.0
25|8|26|5       → FoodMeasurement[8]=? → 5.0
25|12|26|14     → FoodMeasurement[12]=? → 14.0
25|10|26|15     → FoodMeasurement[10]=? → 15.0

## Chobani Greek Yogurt Strawberry Non Fat (typical values per container ~150g):
- Calories: 110-150
- Protein: 14-15g
- Total Carbs: 14-15g
- Sugar: 11g
- Fat: 0g
- Sodium: 55mg
- Cholesterol: 5mg

## FoodMeasurement enum mapping (inferred):
- [0] = Calories (110)
- [2] = Sodium_mg (150) 
- [3] = Fat (0)
- [8] = Cholesterol_mg (5)
- [9] = Sodium... hmm
- [10] = Protein (15)
- [11] = Saturated Fat (0)
- [12] = Carbs (14)
- [13] = Sugar (11)

27|2|1|         → FoodServingSize: quantity=1, ...
28|45|1|        → FoodMeasure(45=container?), 1
1|2|0|          → ?
P__________|    → padding/placeholder
ZwdI0HK|        → food primary key again
16|17|16|-23|122|50|48|-46|-41|77|124|-86|-128|-99|40|-26|-33|-33|66| → entry primary key bytes
```
