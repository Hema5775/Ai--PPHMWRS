import json
from datetime import datetime, date
from app.extensions import db


class WeeklyReport(db.Model):
    """Weekly aggregated behavioral analysis and trend summary."""
    __tablename__ = "weekly_reports"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    week_start = db.Column(db.Date, nullable=False)
    week_end = db.Column(db.Date, nullable=False)
    
    avg_steps = db.Column(db.Float, nullable=False, default=0.0)
    avg_sleep_hours = db.Column(db.Float, nullable=False, default=0.0)
    avg_water_liters = db.Column(db.Float, nullable=False, default=0.0)
    avg_exercise_minutes = db.Column(db.Float, nullable=False, default=0.0)
    
    exercise_consistency_pct = db.Column(db.Float, nullable=False, default=0.0)
    task_completion_pct = db.Column(db.Float, nullable=False, default=0.0)
    avg_wellness_score = db.Column(db.Float, nullable=False, default=0.0)
    
    # Model C Trend output
    trend_direction = db.Column(db.String(20), default="stable")  # improving, stable, declining
    trend_summary = db.Column(db.Text, nullable=False, default="")
    
    achievements_json = db.Column(db.Text, default="[]")
    focus_areas_json = db.Column(db.Text, default="[]")
    recommendations_summary = db.Column(db.Text, default="")
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_achievements(self) -> list:
        try:
            return json.loads(self.achievements_json)
        except Exception:
            return []

    def get_focus_areas(self) -> list:
        try:
            return json.loads(self.focus_areas_json)
        except Exception:
            return []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "week_start": self.week_start.isoformat() if self.week_start else None,
            "week_end": self.week_end.isoformat() if self.week_end else None,
            "avg_steps": round(self.avg_steps, 0),
            "avg_sleep_hours": round(self.avg_sleep_hours, 1),
            "avg_water_liters": round(self.avg_water_liters, 2),
            "avg_exercise_minutes": round(self.avg_exercise_minutes, 1),
            "exercise_consistency_pct": round(self.exercise_consistency_pct, 1),
            "task_completion_pct": round(self.task_completion_pct, 1),
            "avg_wellness_score": round(self.avg_wellness_score, 1),
            "trend_direction": self.trend_direction,
            "trend_summary": self.trend_summary,
            "achievements": self.get_achievements(),
            "focus_areas": self.get_focus_areas(),
            "recommendations_summary": self.recommendations_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
