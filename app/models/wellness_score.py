import json
from datetime import datetime, date
from app.extensions import db


class WellnessScore(db.Model):
    """Transparent behavioral wellness score model."""
    __tablename__ = "wellness_scores"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    
    total_score = db.Column(db.Float, nullable=False)  # 0 to 100
    activity_score = db.Column(db.Float, nullable=False)  # 0 to 100
    hydration_score = db.Column(db.Float, nullable=False)  # 0 to 100
    sleep_score = db.Column(db.Float, nullable=False)  # 0 to 100
    task_score = db.Column(db.Float, nullable=False)  # 0 to 100
    consistency_score = db.Column(db.Float, nullable=False)  # 0 to 100
    
    calculation_formula = db.Column(db.String(255), nullable=False)
    weights_used_json = db.Column(db.Text, nullable=False, default="{}")
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_weights(self) -> dict:
        try:
            return json.loads(self.weights_used_json)
        except Exception:
            return {}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "date": self.date.isoformat() if self.date else None,
            "total_score": round(self.total_score, 1),
            "activity_score": round(self.activity_score, 1),
            "hydration_score": round(self.hydration_score, 1),
            "sleep_score": round(self.sleep_score, 1),
            "task_score": round(self.task_score, 1),
            "consistency_score": round(self.consistency_score, 1),
            "calculation_formula": self.calculation_formula,
            "weights": self.get_weights(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
