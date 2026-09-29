from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class User(db.Model):
    """User account model supporting normal and demo users with password hashing."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # 'user', 'admin'
    is_demo = db.Column(db.Boolean, default=False)
    google_id = db.Column(db.String(120), unique=True, nullable=True, index=True)
    apple_id = db.Column(db.String(120), unique=True, nullable=True, index=True)
    phone_number = db.Column(db.String(30), unique=True, nullable=True, index=True)
    auth_provider = db.Column(db.String(50), nullable=False, default="local")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    profile = db.relationship("HealthProfile", backref="user", uselist=False, cascade="all, delete-orphan")
    activities = db.relationship("DailyActivity", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    recommendations = db.relationship("Recommendation", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    tasks = db.relationship("DailyTask", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    wellness_scores = db.relationship("WellnessScore", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    weekly_reports = db.relationship("WeeklyReport", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def is_admin(self) -> bool:
        return self.role == "admin"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "is_demo": self.is_demo,
            "google_id": self.google_id,
            "apple_id": self.apple_id,
            "phone_number": self.phone_number,
            "auth_provider": self.auth_provider,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
