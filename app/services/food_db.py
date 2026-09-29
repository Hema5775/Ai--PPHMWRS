"""
Structured Food and Nutritional Database.
Provides nutrient-dense, evidence-based meal and ingredient templates with allergen and dietary tags.
DOES NOT prescribe medical diets or treat medical conditions.
"""

from typing import List, Dict, Any, Optional

FOOD_DATABASE: List[Dict[str, Any]] = [
    # Balanced & Mediterranean
    {
        "id": "f_01",
        "name": "Grilled Salmon with Quinoa & Steamed Asparagus",
        "category": "lunch_dinner",
        "calories": 520,
        "protein_g": 38,
        "carbs_g": 42,
        "fat_g": 22,
        "fiber_g": 6,
        "dietary_types": ["balanced", "mediterranean"],
        "allergens": ["fish"],
        "goal_suitability": ["maintenance", "cardio_endurance", "muscle_gain"],
        "notes": "Rich in omega-3 fatty acids and complete protein.",
    },
    {
        "id": "f_02",
        "name": "Greek Yogurt Bowl with Berries, Chia Seeds & Walnuts",
        "category": "breakfast_snack",
        "calories": 340,
        "protein_g": 22,
        "carbs_g": 28,
        "fat_g": 14,
        "fiber_g": 7,
        "dietary_types": ["balanced", "vegetarian", "mediterranean"],
        "allergens": ["dairy", "tree_nuts"],
        "goal_suitability": ["weight_loss", "maintenance", "healthy_sleep"],
        "notes": "Probiotic-rich with antioxidant polyphenol berries.",
    },
    {
        "id": "f_03",
        "name": "Mediterranean Chickpea & Avocado Garden Salad",
        "category": "lunch_dinner",
        "calories": 410,
        "protein_g": 14,
        "carbs_g": 48,
        "fat_g": 18,
        "fiber_g": 12,
        "dietary_types": ["balanced", "vegetarian", "vegan", "mediterranean"],
        "allergens": [],
        "goal_suitability": ["weight_loss", "stress_reduction", "cardio_endurance"],
        "notes": "High fiber and monounsaturated healthy fats for steady satiety.",
    },
    # Vegetarian & Vegan
    {
        "id": "f_04",
        "name": "Tofu & Mixed Vegetable Stir-Fry with Brown Rice",
        "category": "lunch_dinner",
        "calories": 450,
        "protein_g": 24,
        "carbs_g": 56,
        "fat_g": 14,
        "fiber_g": 8,
        "dietary_types": ["vegetarian", "vegan", "balanced"],
        "allergens": ["soy"],
        "goal_suitability": ["muscle_gain", "maintenance", "weight_loss"],
        "notes": "Plant-based complete protein with antioxidant-rich brassica greens.",
    },
    {
        "id": "f_05",
        "name": "Overnight Oats with Almond Milk, Flax & Banana",
        "category": "breakfast_snack",
        "calories": 360,
        "protein_g": 12,
        "carbs_g": 58,
        "fat_g": 9,
        "fiber_g": 10,
        "dietary_types": ["vegetarian", "vegan", "balanced"],
        "allergens": ["tree_nuts"],
        "goal_suitability": ["cardio_endurance", "healthy_sleep", "maintenance"],
        "notes": "Slow-release beta-glucan carbs for sustained morning energy.",
    },
    {
        "id": "f_06",
        "name": "Red Lentil Dahl with Spinach & Turmeric",
        "category": "lunch_dinner",
        "calories": 390,
        "protein_g": 20,
        "carbs_g": 62,
        "fat_g": 6,
        "fiber_g": 14,
        "dietary_types": ["vegetarian", "vegan", "mediterranean", "balanced"],
        "allergens": [],
        "goal_suitability": ["weight_loss", "stress_reduction", "maintenance"],
        "notes": "Anti-inflammatory turmeric and high gut-friendly prebiotic fiber.",
    },
    # Low Carb & Keto
    {
        "id": "f_07",
        "name": "Spinach & Herb Omelette with Sliced Avocado",
        "category": "breakfast_snack",
        "calories": 380,
        "protein_g": 22,
        "carbs_g": 6,
        "fat_g": 30,
        "fiber_g": 5,
        "dietary_types": ["keto", "low_carb", "vegetarian"],
        "allergens": ["eggs"],
        "goal_suitability": ["weight_loss", "muscle_gain", "maintenance"],
        "notes": "Low glycemic impact with high satiety choline and lutein.",
    },
    {
        "id": "f_08",
        "name": "Herb-Roasted Chicken Breast with Zucchini Noodles & Pesto",
        "category": "lunch_dinner",
        "calories": 480,
        "protein_g": 44,
        "carbs_g": 8,
        "fat_g": 31,
        "fiber_g": 4,
        "dietary_types": ["keto", "low_carb", "balanced"],
        "allergens": ["dairy", "tree_nuts"],
        "goal_suitability": ["muscle_gain", "weight_loss"],
        "notes": "High lean protein for muscle repair with fresh herb micro-nutrients.",
    },
    {
        "id": "f_09",
        "name": "Cauliflower Rice Bowl with Sautéed Tempeh & Sesame",
        "category": "lunch_dinner",
        "calories": 320,
        "protein_g": 20,
        "carbs_g": 12,
        "fat_g": 18,
        "fiber_g": 7,
        "dietary_types": ["keto", "low_carb", "vegan", "vegetarian"],
        "allergens": ["soy", "sesame"],
        "goal_suitability": ["weight_loss", "maintenance"],
        "notes": "Low-carb vegan alternative rich in fermented prebiotic isoflavones.",
    },
    # Hydration & Recovery
    {
        "id": "f_10",
        "name": "Electrolyte Cucumber-Mint Hydration Salad",
        "category": "breakfast_snack",
        "calories": 140,
        "protein_g": 3,
        "carbs_g": 12,
        "fat_g": 9,
        "fiber_g": 3,
        "dietary_types": ["balanced", "vegan", "vegetarian", "mediterranean", "low_carb"],
        "allergens": [],
        "goal_suitability": ["stress_reduction", "healthy_sleep", "weight_loss"],
        "notes": "Natural potassium and silica for cellular hydration and cooling.",
    },
]


def get_curated_meal_plan(
    dietary_preference: str = "balanced",
    goal: str = "maintenance",
    allergies: Optional[str] = "",
    category_focus: str = "balanced"
) -> Dict[str, Any]:
    """Filter and select appropriate meals matching preference and safety constraints."""
    user_allergies = [a.strip().lower() for a in allergies.split(",") if a.strip()] if allergies else []
    
    matching_meals = []
    for food in FOOD_DATABASE:
        # Check dietary preference match
        if dietary_preference in food["dietary_types"] or dietary_preference == "balanced":
            # Check allergens constraint
            has_allergen = any(a in user_allergies for a in food["allergens"])
            if not has_allergen:
                matching_meals.append(food)

    if not matching_meals:
        # Fallback to allergen-free defaults
        matching_meals = [f for f in FOOD_DATABASE if not any(a in user_allergies for a in f["allergens"])]

    breakfasts = [m for m in matching_meals if m["category"] == "breakfast_snack"]
    mains = [m for m in matching_meals if m["category"] == "lunch_dinner"]

    selected_breakfast = breakfasts[0] if breakfasts else FOOD_DATABASE[1]
    selected_lunch = mains[0] if mains else FOOD_DATABASE[0]
    selected_dinner = mains[1] if len(mains) > 1 else FOOD_DATABASE[2]

    return {
        "title": f"Nutritional Plan for {dietary_preference.title()} ({goal.replace('_', ' ').title()})",
        "meals": [
            {"meal": "Breakfast", "name": selected_breakfast["name"], "calories": selected_breakfast["calories"], "notes": selected_breakfast["notes"]},
            {"meal": "Lunch", "name": selected_lunch["name"], "calories": selected_lunch["calories"], "notes": selected_lunch["notes"]},
            {"meal": "Dinner", "name": selected_dinner["name"], "calories": selected_dinner["calories"], "notes": selected_dinner["notes"]},
        ],
        "hydration_tip": "Drink a glass of water upon waking and before each major meal.",
        "safety_disclaimer": "Meal suggestions are for general wellness only and do not replace personalized dietary advice from a registered dietitian.",
    }
