"""
Fault Injection and Resilience Tests (Section 14 & 47).
Demonstrates that the application and recommendation service survive ML model failure,
corrupted artifacts, or missing dependencies by activating the multi-tier fallback engine.
"""

from pathlib import Path
from app.ml.model_registry import ModelRegistry
from app.ml.prediction_service import PredictionService
from app.ml.fallback import FallbackRecommendationEngine


def test_level_3_deterministic_fallback():
    profile = {
        "age": 32,
        "gender": "female",
        "height_cm": 165.0,
        "weight_kg": 60.0,
        "activity_level": "sedentary",
        "dietary_preference": "balanced",
        "health_goal": "weight_loss",
        "physical_limitations": "knee_pain",
    }
    features = {
        "bmi": 22.03,
        "avg_daily_steps": 3800,
        "avg_sleep_duration": 5.5,
        "avg_water_intake": 1.5,
        "avg_exercise_minutes": 15,
    }

    fallback_res = FallbackRecommendationEngine.level_3_deterministic_recommendation(
        profile_dict=profile,
        recent_features=features,
    )

    assert fallback_res is not None
    assert fallback_res["is_fallback"] is True
    assert fallback_res["fallback_level"] == "level_3_deterministic_rule"
    assert fallback_res["category"] in ["sleep_hygiene", "hydration_focus", "activity_boost"]
    assert len(fallback_res["daily_tasks"]) >= 3


def test_prediction_service_with_broken_model(app):
    # Initialize a registry pointing to a non-existent directory to simulate missing model
    broken_registry = ModelRegistry(registry_file=Path("models/non_existent.json"), model_dir=Path("models/non_existent"))
    pred_service = PredictionService(registry=broken_registry)

    profile = {
        "age": 28,
        "gender": "male",
        "height_cm": 175.0,
        "weight_kg": 72.0,
        "activity_level": "moderately_active",
        "dietary_preference": "mediterranean",
        "health_goal": "maintenance",
    }

    # Must NOT raise exception! Must gracefully return Level 3 fallback recommendation
    result = pred_service.predict_recommendation_category(
        profile_dict=profile,
        recent_activities=[],
    )

    assert result is not None
    assert result["is_fallback"] is True
    assert result["fallback_level"] in ["level_3_deterministic_rule", "level_4_safe_generic"]
    assert result["category"] is not None
    assert len(result["top_factors"]) > 0
