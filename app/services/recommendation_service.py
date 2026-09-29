"""
Intelligent Hybrid Recommendation Service.
Synthesizes ML Category Predictions, Deterministic Safety Overrides,
Nutritional Database, Exercise Library, and Daily Task Engine.
"""

import json
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import current_app

from app.extensions import db
from app.models.user import User
from app.models.health_profile import HealthProfile
from app.models.activity import DailyActivity
from app.models.recommendation import Recommendation
from app.models.task import DailyTask
from app.models.wellness_score import WellnessScore
from app.ml.prediction_service import PredictionService
from app.ml.model_registry import ModelRegistry
from app.services.food_db import get_curated_meal_plan
from app.services.exercise_db import get_personalized_exercise_plan

logger = logging.getLogger("wellness.services.recommendation")


class RecommendationService:
    """Coordinates ML inference, safety filtering, and recommendation generation."""

    @classmethod
    def get_prediction_service(cls) -> PredictionService:
        base_dir = current_app.config["BASE_DIR"]
        reg_path = current_app.config["REGISTRY_PATH"]
        prod_dir = current_app.config["MODEL_DIR"]
        registry = ModelRegistry(registry_file=reg_path, model_dir=prod_dir)
        anomaly_path = prod_dir / "anomaly_detector.joblib"
        sim_path = prod_dir / "similarity_engine.joblib"
        return PredictionService(registry=registry, anomaly_path=anomaly_path, similarity_path=sim_path)

    @classmethod
    def generate_daily_recommendation(
        cls,
        user_id: int,
        target_date: Optional[date] = None,
        force_refresh: bool = False
    ) -> Recommendation:
        """
        Generate or fetch today's personalized recommendation for a user.
        Integrates ML prediction with safety filtering and task synchronization.
        """
        if target_date is None:
            target_date = date.today()

        # Check existing recommendation for today unless force_refresh
        existing = Recommendation.query.filter_by(user_id=user_id, date=target_date).first()
        if existing and not force_refresh:
            return existing

        profile = HealthProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            # Create a default baseline profile if not yet completed
            profile = HealthProfile(
                user_id=user_id,
                age=30,
                gender="other",
                height_cm=170.0,
                weight_kg=70.0,
                activity_level="moderately_active",
                dietary_preference="balanced",
                health_goal="maintenance",
            )
            profile.calculate_metrics()
            db.session.add(profile)
            db.session.commit()

        # Fetch recent 14 days of activities
        two_weeks_ago = target_date - timedelta(days=14)
        activities = DailyActivity.query.filter(
            DailyActivity.user_id == user_id,
            DailyActivity.date >= two_weeks_ago,
            DailyActivity.date <= target_date,
        ).order_by(DailyActivity.date.desc()).all()

        act_dicts = [a.to_dict() for a in activities]

        # Fetch recent wellness score
        latest_score_rec = WellnessScore.query.filter_by(user_id=user_id).order_by(WellnessScore.date.desc()).first()
        recent_score = latest_score_rec.total_score if latest_score_rec else None

        # Execute ML prediction with automated recovery
        pred_service = cls.get_prediction_service()
        pred_result = pred_service.predict_recommendation_category(
            profile_dict=profile.to_dict(),
            recent_activities=act_dicts,
            recent_wellness_score=recent_score,
        )

        category = pred_result["category"]
        confidence = pred_result["confidence"]
        model_name = pred_result["model_name"]
        model_version = pred_result["model_version"]
        is_fallback = pred_result["is_fallback"]
        fallback_level = pred_result["fallback_level"]
        features = pred_result["features"]
        top_factors = pred_result.get("top_factors", [])

        # Build traceable explanation string
        factors_text = "; ".join(top_factors) if top_factors else "Standard baseline lifestyle profile"
        explanation = (
            f"Focus Area: {category.replace('_', ' ').title()}. "
            f"Primary factors influencing this guidance: {factors_text}."
        )
        if is_fallback:
            explanation += f" (Note: Safety fallback active - {fallback_level})"

        # Generate Diet Guidance
        diet_plan = get_curated_meal_plan(
            dietary_preference=profile.dietary_preference,
            goal=profile.health_goal,
            allergies=profile.allergies,
            category_focus=category,
        )

        # Generate Exercise Guidance (respecting limitations)
        exercise_plan = get_personalized_exercise_plan(
            category=category,
            goal=profile.health_goal,
            limitations=profile.physical_limitations or "none",
            avg_minutes=features.get("avg_exercise_minutes", 25.0),
        )

        # Dynamic Hydration & Sleep targets
        target_water = round(max(1.8, min(4.8, profile.weight_kg * 0.033 + (exercise_plan["suggested_duration_minutes"] / 60.0) * 0.3)), 1)
        target_sleep = 7.5 if category != "sleep_hygiene" else 8.0

        # Adaptive step goal
        avg_steps = features.get("avg_daily_steps", 6000)
        if category == "activity_boost":
            step_target = min(10000, max(5000, int(avg_steps + 1200)))
        elif category == "active_recovery":
            step_target = max(4000, int(avg_steps * 0.85))
        else:
            step_target = int(max(6000, avg_steps))

        # Generate Daily Tasks
        task_specs = [
            {
                "title": "Daily Movement Goal",
                "target_description": f"{step_target:,} steps",
                "category": "activity",
            },
            {
                "title": "Hydration Target",
                "target_description": f"{target_water:.1f} Liters of water",
                "category": "hydration",
            },
            {
                "title": "Sleep Duration",
                "target_description": f"{target_sleep:.1f} hours restful sleep",
                "category": "sleep",
            },
            {
                "title": f"Exercise: {exercise_plan['recommended_activities'][0]}",
                "target_description": f"{exercise_plan['suggested_duration_minutes']} min {exercise_plan['intensity'].lower()} movement",
                "category": "exercise",
            },
        ]

        # Sync Daily Tasks into DB for this date
        cls._sync_daily_tasks(user_id=user_id, target_date=target_date, task_specs=task_specs)

        # Persist or update Recommendation record
        if not existing:
            rec = Recommendation(
                user_id=user_id,
                date=target_date,
                category=category,
                diet_guidance_json=json.dumps(diet_plan),
                exercise_guidance_json=json.dumps(exercise_plan),
                hydration_target_liters=target_water,
                sleep_target_hours=target_sleep,
                daily_tasks_json=json.dumps(task_specs),
                explanation=explanation,
                confidence=confidence,
                model_name=model_name,
                model_version=model_version,
                is_fallback=is_fallback,
                fallback_level=fallback_level,
                trace_features_json=json.dumps(features),
            )
            db.session.add(rec)
        else:
            rec = existing
            rec.category = category
            rec.diet_guidance_json = json.dumps(diet_plan)
            rec.exercise_guidance_json = json.dumps(exercise_plan)
            rec.hydration_target_liters = target_water
            rec.sleep_target_hours = target_sleep
            rec.daily_tasks_json = json.dumps(task_specs)
            rec.explanation = explanation
            rec.confidence = confidence
            rec.model_name = model_name
            rec.model_version = model_version
            rec.is_fallback = is_fallback
            rec.fallback_level = fallback_level
            rec.trace_features_json = json.dumps(features)

        db.session.commit()
        return rec

    @staticmethod
    def _sync_daily_tasks(user_id: int, target_date: date, task_specs: List[Dict[str, Any]]) -> None:
        """Create or maintain user daily tasks for the given day."""
        existing_tasks = DailyTask.query.filter_by(user_id=user_id, date=target_date).all()
        existing_titles = {t.title: t for t in existing_tasks}

        for spec in task_specs:
            if spec["title"] not in existing_titles:
                new_task = DailyTask(
                    user_id=user_id,
                    date=target_date,
                    title=spec["title"],
                    target_description=spec["target_description"],
                    category=spec.get("category", "wellness"),
                    completed=False,
                )
                db.session.add(new_task)
            else:
                # Update target description if existing task incomplete
                task = existing_titles[spec["title"]]
                if not task.completed:
                    task.target_description = spec["target_description"]
