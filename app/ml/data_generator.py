"""
Dataset Generator for Development and Validation.
Generates a realistic, clearly labeled synthetic dataset: 'synthetic_development_data'.

IMPORTANT:
- This dataset is strictly labeled for DEVELOPMENT AND BENCHMARKING ONLY.
- It does NOT pretend to be real clinical trial or EHR data.
- Distributions are based on documented physiological norms (WHO, CDC, ACSM guidelines)
  with controlled relationships between lifestyle inputs and wellness recommendation outcomes.
"""

import os
import numpy as np
import pandas as pd
from pathlib import Path

# Fix seed for reproducible baseline generation
SEED = 42
np.random.seed(SEED)

CATEGORIES = [
    "activity_boost",       # For sedentary/low step counts needing gradual movement
    "sleep_hygiene",        # For poor sleep duration / erratic sleep patterns
    "hydration_focus",      # For insufficient fluid intake relative to body weight/activity
    "metabolic_balance",    # For weight management / elevated BMI with balanced nutrition
    "strength_endurance",   # For active users seeking muscle gain or athletic stamina
    "active_recovery",      # For high-strain users showing signs of fatigue or high minutes
]


def generate_synthetic_data(num_samples: int = 50000, output_path: str = None) -> pd.DataFrame:
    """Generate 50,000+ realistic synthetic wellness records."""
    print(f"Generating {num_samples} synthetic wellness records for development...")

    # Demographics
    ages = np.random.randint(18, 76, size=num_samples)
    genders = np.random.choice(["male", "female", "other"], size=num_samples, p=[0.48, 0.48, 0.04])
    
    # Height in cm (realistic Gaussian distribution by gender)
    heights = np.zeros(num_samples)
    for i, g in enumerate(genders):
        if g == "male":
            heights[i] = np.random.normal(176, 7.5)
        elif g == "female":
            heights[i] = np.random.normal(163, 6.8)
        else:
            heights[i] = np.random.normal(170, 7.0)
    heights = np.clip(heights, 140, 205).round(1)

    # Weight in kg (correlated with height + realistic BMI variation)
    weights = np.zeros(num_samples)
    for i in range(num_samples):
        h_m = heights[i] / 100.0
        # target BMI between 18.5 and 36
        target_bmi = np.random.gamma(shape=9.0, scale=2.8)  # peak around 24-27
        target_bmi = np.clip(target_bmi, 18.0, 42.0)
        weights[i] = target_bmi * (h_m ** 2)
    weights = np.clip(weights, 42.0, 145.0).round(1)

    bmis = (weights / ((heights / 100.0) ** 2)).round(2)

    # Calculate BMR (Mifflin-St Jeor formula)
    bmrs = np.zeros(num_samples)
    for i in range(num_samples):
        if genders[i] == "male":
            bmrs[i] = (10 * weights[i]) + (6.25 * heights[i]) - (5 * ages[i]) + 5
        elif genders[i] == "female":
            bmrs[i] = (10 * weights[i]) + (6.25 * heights[i]) - (5 * ages[i]) - 161
        else:
            bmrs[i] = (10 * weights[i]) + (6.25 * heights[i]) - (5 * ages[i]) - 78
    bmrs = np.clip(bmrs, 900, 2600).round(1)

    # Activity level
    activity_levels = np.random.choice(
        ["sedentary", "lightly_active", "moderately_active", "very_active", "extra_active"],
        size=num_samples,
        p=[0.25, 0.30, 0.25, 0.15, 0.05]
    )

    # Dietary preferences
    dietary_preferences = np.random.choice(
        ["balanced", "vegetarian", "vegan", "keto", "mediterranean", "low_carb"],
        size=num_samples,
        p=[0.40, 0.18, 0.08, 0.10, 0.14, 0.10]
    )

    # Health goals
    health_goals = np.random.choice(
        ["weight_loss", "muscle_gain", "maintenance", "stress_reduction", "cardio_endurance", "healthy_sleep"],
        size=num_samples,
        p=[0.30, 0.20, 0.20, 0.10, 0.10, 0.10]
    )

    # Activity metrics influenced by activity_level
    avg_daily_steps = np.zeros(num_samples)
    avg_exercise_mins = np.zeros(num_samples)

    for i, act in enumerate(activity_levels):
        if act == "sedentary":
            avg_daily_steps[i] = np.random.normal(3800, 1000)
            avg_exercise_mins[i] = np.random.normal(12, 8)
        elif act == "lightly_active":
            avg_daily_steps[i] = np.random.normal(6200, 1200)
            avg_exercise_mins[i] = np.random.normal(25, 10)
        elif act == "moderately_active":
            avg_daily_steps[i] = np.random.normal(8800, 1500)
            avg_exercise_mins[i] = np.random.normal(45, 12)
        elif act == "very_active":
            avg_daily_steps[i] = np.random.normal(11800, 1800)
            avg_exercise_mins[i] = np.random.normal(70, 15)
        else: # extra_active
            avg_daily_steps[i] = np.random.normal(14500, 2200)
            avg_exercise_mins[i] = np.random.normal(95, 20)

    avg_daily_steps = np.clip(avg_daily_steps, 1000, 25000).astype(int)
    avg_exercise_mins = np.clip(avg_exercise_mins, 0, 180).astype(int)

    # Sleep hours (mean ~7.1h, std ~1.2)
    avg_sleep_duration = np.random.normal(7.1, 1.15, size=num_samples)
    avg_sleep_duration = np.clip(avg_sleep_duration, 3.5, 11.0).round(1)

    # Water intake in Liters (correlated with weight + activity)
    base_water = weights * 0.033
    water_noise = np.random.normal(0, 0.5, size=num_samples)
    avg_water_intake = np.clip(base_water + (avg_exercise_mins / 60.0) * 0.4 + water_noise, 1.0, 5.5).round(2)

    # Target water liters
    target_water = (weights * 0.033).round(2)
    hydration_ratio = (avg_water_intake / np.maximum(target_water, 1.0)).round(2)

    # Consistency scores (0.0 to 1.0)
    consistency_score = np.random.beta(a=5, b=2, size=num_samples).round(2)
    sleep_consistency = np.random.beta(a=6, b=2, size=num_samples).round(2)

    # Step trend slope (-150 to +150 steps/day)
    step_trend_slope = np.random.normal(5, 50, size=num_samples).round(1)

    # Recent wellness score (0 - 100)
    recent_wellness_score = (
        0.28 * np.clip((avg_daily_steps / 10000.0) * 100, 0, 100) +
        0.22 * np.clip((avg_water_intake / target_water) * 100, 0, 100) +
        0.22 * np.clip((avg_sleep_duration / 8.0) * 100, 0, 100) +
        0.18 * (consistency_score * 100) +
        0.10 * np.clip((avg_exercise_mins / 45.0) * 100, 0, 100)
    ).round(1)
    recent_wellness_score = np.clip(recent_wellness_score, 15.0, 99.0)

    # Ground truth labels derived from transparent physiological and behavioral heuristics
    # with controlled probabilistic noise to simulate real-world variance
    recommendation_categories = []
    for i in range(num_samples):
        scores = {cat: 0.0 for cat in CATEGORIES}

        # Sleep issues prioritization
        if avg_sleep_duration[i] < 6.2 or sleep_consistency[i] < 0.55:
            scores["sleep_hygiene"] += 4.5
        if health_goals[i] == "healthy_sleep":
            scores["sleep_hygiene"] += 3.0

        # Dehydration prioritization
        if hydration_ratio[i] < 0.70 or avg_water_intake[i] < 1.7:
            scores["hydration_focus"] += 4.2

        # Sedentary / low activity prioritization
        if avg_daily_steps[i] < 5500 or activity_levels[i] == "sedentary":
            scores["activity_boost"] += 4.0
        if health_goals[i] == "cardio_endurance" and avg_daily_steps[i] < 8000:
            scores["activity_boost"] += 2.5

        # Metabolic & weight balance
        if bmis[i] >= 27.5 or health_goals[i] == "weight_loss":
            scores["metabolic_balance"] += 3.5
        if health_goals[i] == "weight_loss" and bmis[i] >= 25.0:
            scores["metabolic_balance"] += 2.0

        # Strength and muscle building
        if health_goals[i] == "muscle_gain" or (activity_levels[i] in ["very_active", "extra_active"] and avg_sleep_duration[i] >= 7.0):
            scores["strength_endurance"] += 4.0

        # Active recovery needed
        if avg_exercise_mins[i] > 65 and (avg_sleep_duration[i] < 6.5 or consistency_score[i] < 0.50):
            scores["active_recovery"] += 4.0
        if health_goals[i] == "stress_reduction":
            scores["active_recovery"] += 2.8

        # Add slight stochastic noise for realistic boundaries
        for cat in CATEGORIES:
            scores[cat] += np.random.normal(0, 0.4)

        best_cat = max(scores, key=scores.get)
        recommendation_categories.append(best_cat)

    df = pd.DataFrame({
        "dataset_type": "synthetic_development_data",
        "age": ages,
        "gender": genders,
        "height_cm": heights,
        "weight_kg": weights,
        "bmi": bmis,
        "bmr": bmrs,
        "activity_level": activity_levels,
        "dietary_preference": dietary_preferences,
        "health_goal": health_goals,
        "avg_daily_steps": avg_daily_steps,
        "avg_exercise_minutes": avg_exercise_mins,
        "avg_sleep_duration": avg_sleep_duration,
        "avg_water_intake": avg_water_intake,
        "target_water_liters": target_water,
        "hydration_ratio": hydration_ratio,
        "consistency_score": consistency_score,
        "sleep_consistency": sleep_consistency,
        "step_trend_slope": step_trend_slope,
        "recent_wellness_score": recent_wellness_score,
        "recommendation_category": recommendation_categories,
    })

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_p, index=False)
        print(f"Synthetic dataset saved successfully to {out_p} ({len(df)} rows)")

    return df


if __name__ == "__main__":
    generate_synthetic_data(50000, "data/synthetic/synthetic_development_data.csv")
