from datetime import datetime, date
from app.extensions import db


class DailyTask(db.Model):
    """Personalized daily wellness micro-goals generated for the user."""
    __tablename__ = "daily_tasks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    
    title = db.Column(db.String(120), nullable=False)
    target_description = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(40), nullable=False, default="wellness")  # activity, hydration, sleep, exercise, wellness
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.String(255), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def mark_completed(self, status: bool = True, notes: str = None) -> None:
        self.completed = status
        self.completed_at = datetime.utcnow() if status else None
        if notes:
            self.notes = notes

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "date": self.date.isoformat() if self.date else None,
            "title": self.title,
            "target_description": self.target_description,
            "category": self.category,
            "completed": self.completed,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
