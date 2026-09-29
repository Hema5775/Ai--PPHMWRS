from datetime import datetime, date
from app.extensions import db


class DailyActivity(db.Model):
    """Daily logged health and lifestyle activity records."""
    __tablename__ = "daily_activities"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    
    steps = db.Column(db.Integer, nullable=False, default=0)
    water_liters = db.Column(db.Float, nullable=False, default=0.0)
    sleep_hours = db.Column(db.Float, nullable=False, default=0.0)
    sleep_quality = db.Column(db.Integer, default=3)  # 1 to 5 rating
    exercise_minutes = db.Column(db.Integer, nullable=False, default=0)
    exercise_type = db.Column(db.String(50), default="walking")
    calories_burned = db.Column(db.Float, nullable=True)
    mood = db.Column(db.String(30), default="neutral")  # great, good, neutral, tired, stressed
    notes = db.Column(db.Text, nullable=True)
    
    # Anomaly Detection tag (Data quality & outlier detection, never medical diagnosis)
    is_anomaly = db.Column(db.Boolean, default=False)
    anomaly_reason = db.Column(db.String(255), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique constraint per user per date
    __table_args__ = (
        db.UniqueConstraint("user_id", "date", name="uq_user_activity_date"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "date": self.date.isoformat() if self.date else None,
            "steps": self.steps,
            "water_liters": self.water_liters,
            "sleep_hours": self.sleep_hours,
            "sleep_quality": self.sleep_quality,
            "exercise_minutes": self.exercise_minutes,
            "exercise_type": self.exercise_type,
            "calories_burned": self.calories_burned,
            "mood": self.mood,
            "notes": self.notes,
            "is_anomaly": self.is_anomaly,
            "anomaly_reason": self.anomaly_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
