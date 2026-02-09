# FoodMeasurement Enum (from GWT JS)
# Ordinal → Name → API Key → Display Name

0: Energy → energy → Energy
1: Volume → volume → Volume
2: Fat → (obfuscated) → Fat
3: (obfuscated) → (obfuscated) → (TotalFat or similar)
4: SaturatedFat → saturated_fat → Saturated Fat
5: MonounsaturatedFat → monounsaturated_fat → Monounsaturated Fat
6: PolyunsaturatedFat → polyunsaturated_fat → Polyunsaturated Fat
7: TransFat → trans_fat → Trans Fat
8: Cholesterol → cholesterol → Cholesterol
9: Sodium → sodium → Sodium
10: Carbohydrate → carbohydrate → Carbohydrate
11: Fiber → fiber → Fiber
12: Sugar → sugar → Sugar
13: Protein → protein → Protein
14: VitaminA → vitamin_a → Vitamin A
15: VitaminB6 → vitamin_b6 → Vitamin B-6
16: VitaminB12 → vitamin_b12 → Vitamin B-12
17: VitaminC → vitamin_c → Vitamin C
18: Calcium → calcium → Calcium
19: Iron → iron → Iron
20: Magnesium → magnesium → Magnesium
21: Phosphorus → phosphorus → Phosphorus
22: Potassium → potassium → Potassium
23: Zinc → zinc → Zinc
24: Thiamin → thiamin → Thiamin
25: Riboflavin → riboflavin → Riboflavin
26: Niacin → niacin → Niacin
27: Folate → folate → Folate
28: Caffeine → caffeine → Caffeine
29: (obfuscated) → (obfuscated) → (last one)

# Captured nutrient mapping from Chobani Greek Yogurt Strawberry Non Fat:
# Enum[0]=110 (Energy/Calories)
# Enum[2]=150 (likely sodium in mg or something else - needs verification)
# Enum[3]=0
# Enum[8]=5 (Cholesterol mg)
# Enum[9]=55 (Sodium mg)
# Enum[10]=15 (Carbohydrate g)
# Enum[11]=0 (Fiber g)
# Enum[12]=14 (Sugar g)
# Enum[13]=11 (Protein g)

# KEY INSIGHT: We don't need to construct nutrients manually!
# Flow: searchFoods → getUnsavedFoodLogEntry (returns pre-filled entry) → updateFoodLogEntry
