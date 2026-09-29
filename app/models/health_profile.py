from datetime import datetime
from app.extensions import db


class HealthProfile(db.Model):
    """Personalized wellness profile containing baseline biometrics and preferences."""
    __tablename__ = "health_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(20), nullable=False)  # 'male', 'female', 'other'
    height_cm = db.Column(db.Float, nullable=False)
    weight_kg = db.Column(db.Float, nullable=False)
    
    activity_level = db.Column(db.String(30), nullable=False, default="moderately_active")
    # sedentary, lightly_active, moderately_active, very_active, extra_active
    
    dietary_preference = db.Column(db.String(30), nullable=False, default="balanced")
    # balanced, vegetarian, vegan, keto, mediterranean, low_carb
    
    health_goal = db.Column(db.String(30), nullable=False, default="maintenance")
    # weight_loss, muscle_gain, maintenance, stress_reduction, cardio_endurance, healthy_sleep
    
    allergies = db.Column(db.String(255), default="")  # comma-separated
    physical_limitations = db.Column(db.String(255), default="none")  # knee_pain, back_pain, asthma, none
    
    target_sleep_hours = db.Column(db.Float, default=7.5)
    target_water_liters = db.Column(db.Float, default=2.5)
    target_steps = db.Column(db.Integer, default=8000)
    
    bmi = db.Column(db.Float, nullable=True)
    bmr = db.Column(db.Float, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def calculate_metrics(self) -> None:
        """Deterministic calculations for BMI and Mifflin-St Jeor BMR estimate."""
        if self.height_cm and self.weight_kg and self.height_cm > 0:
            height_m = self.height_cm / 100.0
            self.bmi = round(self.weight_kg / (height_m ** 2), 2)
        else:
            self.bmi = 22.0

        if self.weight_kg and self.height_cm and self.age:
            # Mifflin-St Jeor formula
            if self.gender == "male":
                base_bmr = (10 * self.weight_kg) + (6.25 * self.height_cm) - (5 * self.age) + 5
            elif self.gender == "female":
                base_bmr = (10 * self.weight_kg) + (6.25 * self.height_cm) - (5 * self.age) - 161
            else:
                base_bmr = (10 * self.weight_kg) + (6.25 * self.height_cm) - (5 * self.age) - 78
            self.bmr = round(max(base_bmr, 800.0), 1)
        else:
            self.bmr = 1500.0

        # Dynamic baseline targets based on weight & activity
        if not self.target_water_liters or self.target_water_liters <= 0:
            self.target_water_liters = round(max(1.8, min(4.5, self.weight_kg * 0.033)), 2)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "age": self.age,
            "gender": self.gender,
            "height_cm": self.height_cm,
            "weight_kg": self.weight_kg,
            "activity_level": self.activity_level,
            "dietary_preference": self.dietary_preference,
            "health_goal": self.health_goal,
            "allergies": self.allergies,
            "physical_limitations": self.physical_limitations,
            "target_sleep_hours": self.target_sleep_hours,
            "target_water_liters": self.target_water_liters,
            "target_steps": self.target_steps,
            "bmi": self.bmi,
            "bmr": self.bmr,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
