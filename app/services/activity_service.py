"""
Daily Activity Logging and Processing Service.
Handles daily data entry, anomaly detection auditing (Model D), and triggers wellness score calculation.
"""

from typing import Dict, Any, List, Optional
from datetime import date, timedelta
from app.extensions import db
from app.models.activity import DailyActivity
from app.models.health_profile import HealthProfile
from app.models.wellness_score import WellnessScore
from app.models.recommendation import Recommendation
from app.models.weekly_report import WeeklyReport
from app.services.scoring_service import ScoringService
from app.services.recommendation_service import RecommendationService


class ActivityService:
    """Manages activity logging, anomaly screening, and metric updates."""

    @staticmethod
    def log_daily_activity(
        user_id: int,
        entry_date: date,
        steps: int,
        water_liters: float,
        sleep_hours: float,
        exercise_minutes: int,
        exercise_type: str = "walking",
        sleep_quality: int = 3,
        calories_burned: Optional[float] = None,
        mood: str = "neutral",
        notes: Optional[str] = None
    ) -> DailyActivity:
        """Log or update daily activity, screen for anomalies, and recalculate wellness score."""
        # Screen with Model D Anomaly Detector
        pred_service = RecommendationService.get_prediction_service()
        is_anomaly, anomaly_reason = pred_service.detect_activity_anomaly(
            steps=steps,
            water_liters=water_liters,
            sleep_hours=sleep_hours,
            exercise_minutes=exercise_minutes,
        )

        activity = DailyActivity.query.filter_by(user_id=user_id, date=entry_date).first()
        if not activity:
            activity = DailyActivity(
                user_id=user_id,
                date=entry_date,
                steps=steps,
                water_liters=water_liters,
                sleep_hours=sleep_hours,
                sleep_quality=sleep_quality,
                exercise_minutes=exercise_minutes,
                exercise_type=exercise_type,
                calories_burned=calories_burned,
                mood=mood,
                notes=notes,
                is_anomaly=is_anomaly,
                anomaly_reason=anomaly_reason,
            )
            db.session.add(activity)
        else:
            activity.steps = steps
            activity.water_liters = water_liters
            activity.sleep_hours = sleep_hours
            activity.sleep_quality = sleep_quality
            activity.exercise_minutes = exercise_minutes
            activity.exercise_type = exercise_type
            activity.calories_burned = calories_burned
            activity.mood = mood
            activity.notes = notes
            activity.is_anomaly = is_anomaly
            activity.anomaly_reason = anomaly_reason

        db.session.commit()

        # Recalculate wellness score for this date
        ScoringService.calculate_daily_wellness_score(user_id=user_id, target_date=entry_date, persist=True)

        return activity

    @staticmethod
    def get_recent_activities(user_id: int, days: int = 30) -> List[DailyActivity]:
        """Fetch past N days of activity records ordered by date ascending."""
        start_date = date.today() - timedelta(days=days - 1)
        return DailyActivity.query.filter(
            DailyActivity.user_id == user_id,
            DailyActivity.date >= start_date,
        ).order_by(DailyActivity.date.asc()).all()

    @classmethod
    def get_user_data_availability(cls, user: Any = None) -> Dict[str, Any]:
        """
        Evaluate real data availability for the specified user or user_id.
        Determines whether the user has no data, partial data, or sufficient data for
        longitudinal insights, recommendations, and anomaly detection.
        Does NOT use hardcoded user conditionals.
        """
        default_res: Dict[str, Any] = {
            "state": "no_data",
            "has_profile": False,
            "profile_completed": False,
            "activity_count": 0,
            "unique_activity_days": 0,
            "history_available": False,
            "can_show_trends": False,
            "can_show_activity_insights": False,
            "has_scores": False,
            "has_recommendations": False,
            "has_reports": False,
            "anomaly_count": 0,
            "min_date": None,
            "max_date": None,
            "days_span": 0,
        }

        if user is None:
            return default_res

        user_id = getattr(user, "id", None)
        if user_id is None:
            try:
                user_id = int(user)
            except (ValueError, TypeError):
                return default_res

        # 1. Profile evaluation
        profile = getattr(user, "profile", None)
        if profile is None:
            profile = HealthProfile.query.filter_by(user_id=user_id).first()

        has_profile = profile is not None
        profile_completed = bool(
            has_profile
            and getattr(profile, "age", None)
            and getattr(profile, "height_cm", None)
            and getattr(profile, "weight_kg", None)
            and getattr(profile, "health_goal", None)
        )

        # 2. Activity counts and unique dates
        activity_count = DailyActivity.query.filter_by(user_id=user_id).count()

        unique_activity_days = (
            db.session.query(db.func.count(db.func.distinct(DailyActivity.date)))
            .filter(DailyActivity.user_id == user_id)
            .scalar() or 0
        )

        # 3. Span and anomalies
        min_date, max_date = (
            db.session.query(db.func.min(DailyActivity.date), db.func.max(DailyActivity.date))
            .filter(DailyActivity.user_id == user_id)
            .first()
        )
        days_span = (max_date - min_date).days + 1 if (min_date and max_date) else 0
        anomaly_count = DailyActivity.query.filter_by(user_id=user_id, is_anomaly=True).count()

        # 4. Related entities
        has_scores = WellnessScore.query.filter_by(user_id=user_id).first() is not None
        has_recommendations = Recommendation.query.filter_by(user_id=user_id).first() is not None
        has_reports = WeeklyReport.query.filter_by(user_id=user_id).first() is not None

        # 5. Capabilities
        history_available = (activity_count > 0)
        can_show_activity_insights = (activity_count > 0)
        # Longitudinal trends (7d, 14d, 30d) and 7-day consistency scoring require at least 7 recorded days
        can_show_trends = (unique_activity_days >= 7)

        # 6. State evaluation
        if activity_count == 0:
            state = "no_data"
        elif unique_activity_days < 7:
            state = "partial"
        else:
            state = "sufficient"

        return {
            "state": state,
            "has_profile": has_profile,
            "profile_completed": profile_completed,
            "activity_count": activity_count,
            "unique_activity_days": unique_activity_days,
            "history_available": history_available,
            "can_show_trends": can_show_trends,
            "can_show_activity_insights": can_show_activity_insights,
            "has_scores": has_scores,
            "has_recommendations": has_recommendations,
            "has_reports": has_reports,
            "anomaly_count": anomaly_count,
            "min_date": min_date.isoformat() if min_date else None,
            "max_date": max_date.isoformat() if max_date else None,
            "days_span": days_span,
        }


def get_user_data_availability(user: Any = None) -> Dict[str, Any]:
    """Convenience module function for ActivityService.get_user_data_availability."""
    return ActivityService.get_user_data_availability(user)

