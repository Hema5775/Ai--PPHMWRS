"""
Model B — Transparent Wellness Score Service.
Computes a transparent, behavioral wellness score (0-100) based on configurable behavioral dimensions.
DOES NOT represent a medical diagnosis or clinical pathology index.
"""

import json
from typing import Dict, Any, Optional
from datetime import date
from flask import current_app
from app.extensions import db
from app.models.wellness_score import WellnessScore
from app.models.activity import DailyActivity
from app.models.task import DailyTask
from app.models.health_profile import HealthProfile


class ScoringService:
    """Calculates and records normalized wellness scores with visible weight breakdowns."""

    @staticmethod
    def calculate_daily_wellness_score(
        user_id: int,
        target_date: Optional[date] = None,
        persist: bool = True
    ) -> WellnessScore:
        """
        Compute daily wellness score based on today's activity, hydration, sleep, task completion, and consistency.
        """
        if target_date is None:
            target_date = date.today()

        profile = HealthProfile.query.filter_by(user_id=user_id).first()
        activity = DailyActivity.query.filter_by(user_id=user_id, date=target_date).first()
        tasks = DailyTask.query.filter_by(user_id=user_id, date=target_date).all()

        # Configurable weights
        try:
            w_act = current_app.config.get("WEIGHT_ACTIVITY", 0.25)
            w_hyd = current_app.config.get("WEIGHT_HYDRATION", 0.20)
            w_slp = current_app.config.get("WEIGHT_SLEEP", 0.20)
            w_tsk = current_app.config.get("WEIGHT_TASKS", 0.20)
            w_con = current_app.config.get("WEIGHT_CONSISTENCY", 0.15)
        except RuntimeError:
            w_act, w_hyd, w_slp, w_tsk, w_con = 0.25, 0.20, 0.20, 0.20, 0.15

        target_steps = profile.target_steps if (profile and profile.target_steps) else 8000
        target_water = profile.target_water_liters if (profile and profile.target_water_liters) else 2.5
        target_sleep = profile.target_sleep_hours if (profile and profile.target_sleep_hours) else 7.5

        # 1. Activity Score (0 - 100)
        if activity:
            step_ratio = min(activity.steps / max(target_steps, 1000), 1.0)
            exercise_ratio = min(activity.exercise_minutes / 45.0, 1.0)
            activity_score = round((step_ratio * 70.0) + (exercise_ratio * 30.0), 1)
        else:
            activity_score = 0.0

        # 2. Hydration Score (0 - 100)
        if activity:
            hydration_ratio = min(activity.water_liters / max(target_water, 1.0), 1.25)
            hydration_score = round(min(hydration_ratio * 100.0, 100.0), 1)
        else:
            hydration_score = 0.0

        # 3. Sleep Score (0 - 100)
        if activity and activity.sleep_hours > 0:
            duration_ratio = min(activity.sleep_hours / max(target_sleep, 4.0), 1.0)
            quality_ratio = (activity.sleep_quality or 3) / 5.0
            sleep_score = round((duration_ratio * 70.0) + (quality_ratio * 30.0), 1)
        else:
            sleep_score = 0.0

        # 4. Task Completion Score (0 - 100)
        if tasks:
            completed_count = sum(1 for t in tasks if t.completed)
            task_score = round((completed_count / len(tasks)) * 100.0, 1)
        else:
            task_score = 70.0 if activity else 0.0  # Default neutral baseline if tasks not populated yet

        # 5. Consistency Score (0 - 100) based on last 7 days of logging
        from datetime import timedelta
        week_ago = target_date - timedelta(days=6)
        active_days_count = DailyActivity.query.filter(
            DailyActivity.user_id == user_id,
            DailyActivity.date >= week_ago,
            DailyActivity.date <= target_date,
        ).count()
        consistency_score = round((active_days_count / 7.0) * 100.0, 1)

        # Total Weighted Score
        total_score = round(
            (w_act * activity_score) +
            (w_hyd * hydration_score) +
            (w_slp * sleep_score) +
            (w_tsk * task_score) +
            (w_con * consistency_score),
            1
        )
        total_score = max(0.0, min(100.0, total_score))

        formula_str = (
            f"Wellness Score = {w_act}×{activity_score:.0f} (Activity) + "
            f"{w_hyd}×{hydration_score:.0f} (Hydration) + "
            f"{w_slp}×{sleep_score:.0f} (Sleep) + "
            f"{w_tsk}×{task_score:.0f} (Tasks) + "
            f"{w_con}×{consistency_score:.0f} (Consistency)"
        )

        weights_dict = {
            "activity": w_act,
            "hydration": w_hyd,
            "sleep": w_slp,
            "tasks": w_tsk,
            "consistency": w_con,
        }

        # Check existing
        score_record = WellnessScore.query.filter_by(user_id=user_id, date=target_date).first()
        if not score_record:
            score_record = WellnessScore(
                user_id=user_id,
                date=target_date,
                total_score=total_score,
                activity_score=activity_score,
                hydration_score=hydration_score,
                sleep_score=sleep_score,
                task_score=task_score,
                consistency_score=consistency_score,
                calculation_formula=formula_str,
                weights_used_json=json.dumps(weights_dict),
            )
            if persist:
                db.session.add(score_record)
        else:
            score_record.total_score = total_score
            score_record.activity_score = activity_score
            score_record.hydration_score = hydration_score
            score_record.sleep_score = sleep_score
            score_record.task_score = task_score
            score_record.consistency_score = consistency_score
            score_record.calculation_formula = formula_str
            score_record.weights_used_json = json.dumps(weights_dict)

        if persist:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

        return score_record
