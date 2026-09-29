"""
Automated Recovery and Multi-Tier Fallback Engine.
Provides deterministic, physiologically sound guidance when ML models fail, degrade, or are unavailable.
Hierarchy:
  LEVEL 1: Production ML Model
  LEVEL 2: Rollback / Previous Known-Good ML Model
  LEVEL 3: Validated Deterministic Heuristic Engine
  LEVEL 4: Generic Safe Wellness Guidance
"""

from typing import Dict, Any, List, Optional
import json


class FallbackRecommendationEngine:
    """Deterministic, rule-based recommendation engine for safety overrides and ML failure recovery."""

    @staticmethod
    def level_3_deterministic_recommendation(
        profile_dict: Dict[str, Any],
        recent_features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Level 3: Validated deterministic rules based on physiological parameters and lifestyle targets.
        """
        age = float(profile_dict.get("age", 30))
        weight_kg = float(profile_dict.get("weight_kg", 70.0))
        height_cm = float(profile_dict.get("height_cm", 170.0))
        bmi = float(recent_features.get("bmi", 23.0))
        goal = str(profile_dict.get("health_goal", "maintenance"))
        diet_pref = str(profile_dict.get("dietary_preference", "balanced"))
        limitations = str(profile_dict.get("physical_limitations", "none")).lower()
        allergies = str(profile_dict.get("allergies", ""))

        avg_steps = float(recent_features.get("avg_daily_steps", 6000))
        avg_sleep = float(recent_features.get("avg_sleep_duration", 7.0))
        avg_water = float(recent_features.get("avg_water_intake", 2.2))
        avg_exercise = float(recent_features.get("avg_exercise_minutes", 25))

        target_water = round(max(2.0, min(4.5, weight_kg * 0.033)), 2)
        target_sleep = 7.5

        # Determine dominant wellness focus deterministically
        if avg_sleep < 6.0:
            category = "sleep_hygiene"
            reason = "Recent sleep duration is under 6 hours; restorative sleep is prioritized for mental and metabolic recovery."
        elif avg_water < (target_water * 0.70):
            category = "hydration_focus"
            reason = f"Current fluid intake ({avg_water:.1f}L) is significantly below the baseline target ({target_water:.1f}L)."
        elif avg_steps < 5000:
            category = "activity_boost"
            reason = "Recent movement patterns are below the recommended 5,000 baseline step threshold."
        elif bmi >= 28.0 or goal == "weight_loss":
            category = "metabolic_balance"
            reason = "Focusing on metabolic efficiency, caloric awareness, and steady low-impact physical activity."
        elif goal == "muscle_gain" or avg_steps >= 10000:
            category = "strength_endurance"
            reason = "Supporting resistance stimulus, progressive overload, and sufficient recovery protein."
        else:
            category = "active_recovery"
            reason = "Balanced lifestyle maintenance focusing on steady consistency, mobility, and stress management."

        # Adaptive daily step target
        if avg_steps < 4000:
            step_target = min(6000, int(avg_steps + 1500))
        elif avg_steps < 8000:
            step_target = min(10000, int(avg_steps + 1000))
        else:
            step_target = int(avg_steps)

        # Diet Guidance
        diet_guidance = {
            "title": f"Nutritional Balance for {goal.replace('_', ' ').title()}",
            "summary": f"Prioritize wholesome whole foods adhering to your {diet_pref} preferences.",
            "macronutrient_focus": (
                "Lean proteins, fiber-rich legumes, and complex carbs"
                if diet_pref != "keto"
                else "Healthy fats, avocado, leafy greens, and moderate protein"
            ),
            "tips": [
                "Drink a full glass of water 20 minutes before meals.",
                "Incorporate colorful seasonal vegetables at both lunch and dinner.",
                "Limit ultra-processed sugary snacks in the evening.",
            ],
            "allergies_respected": allergies if allergies else "None specified",
        }

        # Exercise Guidance with safety constraint check
        exercise_options = ["Brisk walking", "Light mobility stretching", "Bodyweight squats"]
        if "knee" in limitations:
            exercise_options = ["Low-impact cycling", "Seated upper-body strength", "Gentle mat yoga"]
        elif "back" in limitations:
            exercise_options = ["Gentle walking on even terrain", "Pelvic tilts", "Bird-dog core stability"]

        exercise_guidance = {
            "title": "Low-Impact Sustainable Movement",
            "suggested_duration_minutes": 25 if avg_exercise < 20 else int(avg_exercise + 5),
            "intensity": "Moderate",
            "recommended_activities": exercise_options,
            "safety_note": f"Adjusted for your stated physical limitation: {limitations}." if limitations != "none" else "Listen to your body and stay within a comfortable range of motion.",
        }

        # Daily Tasks
        daily_tasks = [
            {"title": "Daily Step Goal", "target_description": f"{step_target:,} steps", "category": "activity"},
            {"title": "Adequate Hydration", "target_description": f"{target_water:.1f} Liters", "category": "hydration"},
            {"title": "Restorative Sleep", "target_description": f"{target_sleep:.1f} Hours", "category": "sleep"},
            {"title": "Daily Movement", "target_description": f"{exercise_guidance['suggested_duration_minutes']} min {exercise_options[0]}", "category": "exercise"},
        ]

        return {
            "category": category,
            "diet_guidance": diet_guidance,
            "exercise_guidance": exercise_guidance,
            "hydration_target_liters": target_water,
            "sleep_target_hours": target_sleep,
            "daily_tasks": daily_tasks,
            "explanation": f"Rule-based deterministic engine: {reason}",
            "confidence": 0.85,
            "model_name": "DeterministicRuleEngine",
            "model_version": "v1.0-rules",
            "is_fallback": True,
            "fallback_level": "level_3_deterministic_rule",
            "trace_features": recent_features,
        }

    @staticmethod
    def level_4_generic_guidance() -> Dict[str, Any]:
        """
        Level 4: Generic safe fallback guidance when all inputs or engines encounter unexpected failure.
        """
        return {
            "category": "active_recovery",
            "diet_guidance": {
                "title": "Universal Whole-Food Wellness",
                "summary": "Focus on nutrient-dense meals, hydration, and fiber.",
                "tips": [
                    "Keep water accessible throughout the day.",
                    "Include fresh fruit or vegetables with each meal.",
                ],
            },
            "exercise_guidance": {
                "title": "Daily Gentle Movement",
                "suggested_duration_minutes": 20,
                "intensity": "Light",
                "recommended_activities": ["Walking", "Gentle stretching", "Deep breathing exercises"],
                "safety_note": "If you experience dizziness or acute pain, stop immediately and rest.",
            },
            "hydration_target_liters": 2.5,
            "sleep_target_hours": 7.5,
            "daily_tasks": [
                {"title": "Daily Walk", "target_description": "5,000 steps", "category": "activity"},
                {"title": "Hydration", "target_description": "2.5 Liters water", "category": "hydration"},
                {"title": "Rest", "target_description": "7.5 hours sleep", "category": "sleep"},
            ],
            "explanation": "Standard universal wellness baseline active while personalized models synchronize.",
            "confidence": 0.70,
            "model_name": "GenericFallbackEngine",
            "model_version": "v1.0-generic",
            "is_fallback": True,
            "fallback_level": "level_4_safe_generic",
            "trace_features": {},
        }
