"""
Centralized Feature Engineering.
Ensures that all transformations applied during model training are strictly replicated
during live prediction inference.
"""

from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd

NUMERICAL_FEATURES = [
    "age",
    "height_cm",
    "weight_kg",
    "bmi",
    "bmr",
    "avg_daily_steps",
    "avg_exercise_minutes",
    "avg_sleep_duration",
    "avg_water_intake",
    "consistency_score",
    "recent_wellness_score",
    "step_trend_slope",
    "sleep_consistency",
    "hydration_ratio",
]

CATEGORICAL_FEATURES = [
    "gender",
    "activity_level",
    "dietary_preference",
    "health_goal",
]

ALL_FEATURES = NUMERICAL_FEATURES + CATEGORICAL_FEATURES


def extract_features_from_history(
    profile_dict: Dict[str, Any],
    recent_activities: List[Dict[str, Any]],
    recent_wellness_score: Optional[float] = None
) -> Dict[str, Any]:
    """
    Extract standardized feature dictionary from user profile and recent daily activities (e.g. last 7-14 days).
    """
    age = float(profile_dict.get("age", 30))
    gender = str(profile_dict.get("gender", "other")).lower()
    height_cm = float(profile_dict.get("height_cm", 170.0))
    weight_kg = float(profile_dict.get("weight_kg", 70.0))
    activity_level = str(profile_dict.get("activity_level", "moderately_active"))
    dietary_preference = str(profile_dict.get("dietary_preference", "balanced"))
    health_goal = str(profile_dict.get("health_goal", "maintenance"))

    # BMI calculation
    height_m = max(height_cm / 100.0, 0.5)
    bmi = round(weight_kg / (height_m ** 2), 2)

    # BMR calculation (Mifflin-St Jeor)
    if gender == "male":
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    elif gender == "female":
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161
    else:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 78
    bmr = round(max(bmr, 800.0), 1)

    target_water = round(max(1.8, min(5.0, weight_kg * 0.033)), 2)

    # Defaults if no activities recorded yet (Cold Start baseline)
    if not recent_activities:
        activity_step_map = {
            "sedentary": 4000.0,
            "lightly_active": 6500.0,
            "moderately_active": 8500.0,
            "very_active": 11500.0,
            "extra_active": 14000.0,
        }
        activity_ex_map = {
            "sedentary": 15.0,
            "lightly_active": 25.0,
            "moderately_active": 45.0,
            "very_active": 65.0,
            "extra_active": 90.0,
        }
        avg_steps = activity_step_map.get(activity_level, 7000.0)
        avg_exercise = activity_ex_map.get(activity_level, 30.0)
        avg_sleep = float(profile_dict.get("target_sleep_hours", 7.5))
        avg_water = target_water
        consistency = 0.70
        sleep_consistency = 0.75
        step_slope = 0.0
        hydration_ratio = 1.0
        score = recent_wellness_score if recent_wellness_score is not None else 70.0
    else:
        steps_list = [a.get("steps", 0) for a in recent_activities]
        sleep_list = [a.get("sleep_hours", 7.0) for a in recent_activities]
        water_list = [a.get("water_liters", 2.0) for a in recent_activities]
        exercise_list = [a.get("exercise_minutes", 0) for a in recent_activities]

        avg_steps = float(np.mean(steps_list))
        avg_sleep = float(np.mean(sleep_list))
        avg_water = float(np.mean(water_list))
        avg_exercise = float(np.mean(exercise_list))

        # Hydration ratio
        hydration_ratio = round(avg_water / max(target_water, 1.0), 2)

        # Sleep consistency: lower variance gives higher consistency score
        if len(sleep_list) > 1:
            sleep_std = float(np.std(sleep_list))
            sleep_consistency = round(float(np.clip(1.0 - (sleep_std / 2.5), 0.1, 1.0)), 2)
        else:
            sleep_consistency = 0.75

        # Activity consistency: proportion of days meeting at least 50% target
        active_days = sum(1 for s in steps_list if s >= 4000)
        consistency = round(active_days / len(steps_list), 2)

        # Step trend slope via linear fit if at least 3 points
        if len(steps_list) >= 3:
            x = np.arange(len(steps_list))
            slope, _ = np.polyfit(x, steps_list, 1)
            step_slope = round(float(slope), 1)
        else:
            step_slope = 0.0

        if recent_wellness_score is not None:
            score = recent_wellness_score
        else:
            score = round(
                0.28 * min(avg_steps / 10000.0 * 100, 100) +
                0.22 * min(avg_water / target_water * 100, 100) +
                0.22 * min(avg_sleep / 8.0 * 100, 100) +
                0.18 * (consistency * 100) +
                0.10 * min(avg_exercise / 45.0 * 100, 100),
                1
            )

    return {
        "age": age,
        "gender": gender,
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "bmi": bmi,
        "bmr": bmr,
        "activity_level": activity_level,
        "dietary_preference": dietary_preference,
        "health_goal": health_goal,
        "avg_daily_steps": round(avg_steps, 0),
        "avg_exercise_minutes": round(avg_exercise, 0),
        "avg_sleep_duration": round(avg_sleep, 1),
        "avg_water_intake": round(avg_water, 2),
        "consistency_score": consistency,
        "recent_wellness_score": score,
        "step_trend_slope": step_slope,
        "sleep_consistency": sleep_consistency,
        "hydration_ratio": hydration_ratio,
    }


def to_dataframe(feature_dict: Dict[str, Any]) -> pd.DataFrame:
    """Convert a single feature dictionary into a pandas DataFrame aligned with ALL_FEATURES."""
    data = {k: [feature_dict.get(k)] for k in ALL_FEATURES}
    return pd.DataFrame(data)
