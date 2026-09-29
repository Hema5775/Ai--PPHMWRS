"""
Structured Exercise Library and Safety Rule Engine.
Maps wellness categories and user physical limitations into safe, personalized exercise routines.
DOES NOT medically clear users for vigorous activity.
"""

from typing import List, Dict, Any, Optional

EXERCISE_DATABASE: List[Dict[str, Any]] = [
    # Walking & Low Impact
    {
        "id": "ex_01",
        "name": "Brisk Outdoor Walking",
        "category": "walking",
        "intensity": "light_moderate",
        "contraindications": [],
        "target_goals": ["weight_loss", "cardio_endurance", "stress_reduction", "maintenance"],
        "description": "Continuous walking at a conversational pace (approx. 100-115 steps/min).",
    },
    {
        "id": "ex_02",
        "name": "Low-Impact Indoor Incline Walking",
        "category": "walking",
        "intensity": "moderate",
        "contraindications": ["knee_pain"],
        "target_goals": ["weight_loss", "cardio_endurance"],
        "description": "Gentle incline walking on treadmill or hill paths to elevate heart rate without joint pounding.",
    },
    # Light & Moderate Cardio
    {
        "id": "ex_03",
        "name": "Stationary Cycling / Spin",
        "category": "moderate_cardio",
        "intensity": "moderate",
        "contraindications": [],
        "target_goals": ["cardio_endurance", "weight_loss"],
        "description": "Smooth cadence pedal cycle providing aerobic stimulus with zero joint impact.",
    },
    {
        "id": "ex_04",
        "name": "Light Jogging / Run-Walk Intervals",
        "category": "moderate_cardio",
        "intensity": "moderate_high",
        "contraindications": ["knee_pain", "back_pain", "asthma"],
        "target_goals": ["cardio_endurance", "weight_loss"],
        "description": "Alternating 2 minutes jogging with 1 minute recovery walking.",
    },
    # Basic Strength
    {
        "id": "ex_05",
        "name": "Bodyweight Squats & Wall Push-Ups",
        "category": "basic_strength",
        "intensity": "moderate",
        "contraindications": ["knee_pain"],
        "target_goals": ["muscle_gain", "maintenance", "weight_loss"],
        "description": "Foundational compound resistance movements focusing on knee-over-toe alignment and core engagement.",
    },
    {
        "id": "ex_06",
        "name": "Seated Dumbbell / Resistance Band Press & Rows",
        "category": "basic_strength",
        "intensity": "light_moderate",
        "contraindications": [],
        "target_goals": ["muscle_gain", "maintenance"],
        "description": "Upper body posture reinforcement suitable for individuals with lower-body joint sensitivity.",
    },
    # Mobility & Stretching
    {
        "id": "ex_07",
        "name": "Dynamic Hip Openers & Cat-Cow Mobility",
        "category": "mobility",
        "intensity": "light",
        "contraindications": [],
        "target_goals": ["stress_reduction", "healthy_sleep", "maintenance"],
        "description": "Gentle spinal flexion/extension and pelvic mobility to reduce postural stiffness.",
    },
    {
        "id": "ex_08",
        "name": "Full-Body Static Evening Stretch Flow",
        "category": "stretching",
        "intensity": "light",
        "contraindications": [],
        "target_goals": ["healthy_sleep", "stress_reduction"],
        "description": "Relaxing 15-minute static stretching sequence to downregulate nervous system before bedtime.",
    },
    # Active Recovery
    {
        "id": "ex_09",
        "name": "Mindful Nature Walk & Breathwork",
        "category": "recovery",
        "intensity": "light",
        "contraindications": [],
        "target_goals": ["stress_reduction", "healthy_sleep"],
        "description": "Slow stroll focusing on 4-second inhale, 6-second exhale parasympathetic activation.",
    },
]


def get_personalized_exercise_plan(
    category: str,
    goal: str = "maintenance",
    limitations: str = "none",
    avg_minutes: float = 25.0
) -> Dict[str, Any]:
    """Select exercise guidance taking into account physical limitations and focus category."""
    user_limitation = limitations.lower().strip()
    
    # Filter safe exercises
    safe_exercises = []
    for ex in EXERCISE_DATABASE:
        if user_limitation != "none" and user_limitation in ex["contraindications"]:
            continue
        safe_exercises.append(ex)

    # Determine recommended duration
    if avg_minutes < 15:
        target_duration = 20
    elif avg_minutes > 60:
        target_duration = 45
    else:
        target_duration = int(avg_minutes + 5)

    if category == "sleep_hygiene" or category == "active_recovery":
        routines = [e for e in safe_exercises if e["category"] in ["recovery", "stretching", "mobility"]]
        title = "Gentle Restorative Movement & Flexibility"
        intensity = "Light"
    elif category == "strength_endurance":
        routines = [e for e in safe_exercises if e["category"] in ["basic_strength", "moderate_cardio"]]
        title = "Progressive Resistance & Functional Stamina"
        intensity = "Moderate"
    elif category == "activity_boost":
        routines = [e for e in safe_exercises if e["category"] in ["walking", "light_moderate"]]
        title = "Step Volume Booster & Low-Impact Aerobics"
        intensity = "Light-Moderate"
    else:
        routines = [e for e in safe_exercises if goal in e["target_goals"]]
        title = "Balanced Daily Physical Vitality"
        intensity = "Moderate"

    if not routines:
        routines = [EXERCISE_DATABASE[0]]

    selected_names = [r["name"] for r in routines[:3]]

    safety_note = (
        f"Exercise selections automatically excluded high-impact movements due to your noted limitation: '{limitations}'."
        if limitations != "none"
        else "Always warm up for 3-5 minutes and stop immediately if you feel acute discomfort."
    )

    return {
        "title": title,
        "intensity": intensity,
        "suggested_duration_minutes": target_duration,
        "recommended_activities": selected_names,
        "safety_note": safety_note,
        "exercises_detail": [
            {"name": r["name"], "category": r["category"], "description": r["description"]}
            for r in routines[:3]
        ]
    }
