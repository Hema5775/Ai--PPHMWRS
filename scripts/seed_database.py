"""
Database Seeding Script for Demo and Viva Presentation.
Populates realistic demonstration users, 30 days of historical activity logs,
wellness scores, daily tasks, and weekly reports.
Clearly labeled as DEMO DATA.
"""

from pathlib import Path
import sys
from datetime import date, timedelta
import random
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.health_profile import HealthProfile
from app.models.activity import DailyActivity
from app.models.task import DailyTask
from app.models.wellness_score import WellnessScore
from app.models.weekly_report import WeeklyReport
from app.services.activity_service import ActivityService
from app.services.scoring_service import ScoringService
from app.services.recommendation_service import RecommendationService
from app.services.report_service import ReportService

app = create_app("development")


def seed_demo_environment():
    with app.app_context():
        print("Seeding database with demo users and realistic activity data...")

        # 1. Admin User
        admin = User.query.filter_by(email="admin@wellness.ai").first()
        if not admin:
            admin = User(name="System Administrator", email="admin@wellness.ai", role="admin", is_demo=True)
            admin.set_password("AdminPass123!")
            db.session.add(admin)
            db.session.flush()

            admin_prof = HealthProfile(
                user_id=admin.id,
                age=35,
                gender="other",
                height_cm=175.0,
                weight_kg=72.0,
                activity_level="moderately_active",
                dietary_preference="mediterranean",
                health_goal="maintenance",
            )
            admin_prof.calculate_metrics()
            db.session.add(admin_prof)
            print("Created Admin user: admin@wellness.ai (Password: AdminPass123!)")

        # 2. Demo User
        demo_user = User.query.filter_by(email="demo@wellness.ai").first()
        if not demo_user:
            demo_user = User(name="Alex Taylor (Demo)", email="demo@wellness.ai", role="user", is_demo=True)
            demo_user.set_password("DemoPass123!")
            db.session.add(demo_user)
            db.session.flush()

            demo_prof = HealthProfile(
                user_id=demo_user.id,
                age=28,
                gender="female",
                height_cm=165.0,
                weight_kg=62.0,
                activity_level="moderately_active",
                dietary_preference="balanced",
                health_goal="weight_loss",
                allergies="peanuts",
                physical_limitations="none",
                target_sleep_hours=7.5,
                target_water_liters=2.5,
                target_steps=8500,
            )
            demo_prof.calculate_metrics()
            db.session.add(demo_prof)
            print("Created Demo user: demo@wellness.ai (Password: DemoPass123!)")
        else:
            demo_prof = demo_user.profile

        db.session.commit()

        # 3. Seed 30 days of realistic daily activity for demo user
        print("Generating 30 days of historical activity and wellness logs...")
        today = date.today()
        np.random.seed(42)

        for i in range(29, -1, -1):
            log_date = today - timedelta(days=i)

            # Gradual upward progress over 30 days
            day_progress_factor = (30 - i) / 30.0  # 0 to 1
            base_steps = 5500 + int(day_progress_factor * 3200)
            noise_steps = int(np.random.normal(0, 700))
            steps = max(2500, base_steps + noise_steps)

            base_water = 1.8 + (day_progress_factor * 0.8)
            water = round(max(1.2, float(base_water + np.random.normal(0, 0.2))), 1)

            base_sleep = 6.4 + (day_progress_factor * 0.9)
            sleep_h = round(max(4.5, min(9.5, float(base_sleep + np.random.normal(0, 0.4)))), 1)

            ex_mins = int(max(10, 20 + int(day_progress_factor * 25) + int(np.random.normal(0, 8))))
            calories = round(1600 + (steps * 0.04) + (ex_mins * 6.5), 0)

            moods = ["good", "great", "neutral", "good", "great"]
            mood = random.choice(moods)

            # Intentionally inject 1 outlier for Model D demonstration
            is_anomaly = False
            anomaly_reason = None
            if i == 5:
                steps = 28500
                ex_mins = 180
                is_anomaly = True
                anomaly_reason = "Unusually high step and exercise volume detected relative to your 30-day baseline."

            act = DailyActivity.query.filter_by(user_id=demo_user.id, date=log_date).first()
            if not act:
                act = DailyActivity(
                    user_id=demo_user.id,
                    date=log_date,
                    steps=steps,
                    water_liters=water,
                    sleep_hours=sleep_h,
                    sleep_quality=4 if sleep_h >= 7.0 else 3,
                    exercise_minutes=ex_mins,
                    exercise_type="walking" if ex_mins < 30 else "running",
                    calories_burned=calories,
                    mood=mood,
                    notes=f"Demo logged entry for day {30-i}/30.",
                    is_anomaly=is_anomaly,
                    anomaly_reason=anomaly_reason,
                )
                db.session.add(act)
            else:
                act.steps = steps
                act.water_liters = water
                act.sleep_hours = sleep_h
                act.exercise_minutes = ex_mins
                act.calories_burned = calories
                act.is_anomaly = is_anomaly
                act.anomaly_reason = anomaly_reason

        db.session.commit()

        # 4. Generate daily tasks & wellness scores across the 30 days
        print("Calculating wellness scores and synchronizing daily tasks...")
        for i in range(29, -1, -1):
            log_date = today - timedelta(days=i)
            # Create recommendation & tasks
            RecommendationService.generate_daily_recommendation(user_id=demo_user.id, target_date=log_date)

            # Randomly mark some tasks completed
            tasks = DailyTask.query.filter_by(user_id=demo_user.id, date=log_date).all()
            for t in tasks:
                t.completed = random.random() > 0.35  # ~65% completion rate

            db.session.commit()
            ScoringService.calculate_daily_wellness_score(user_id=demo_user.id, target_date=log_date, persist=True)

        # 5. Compile weekly reports for past 3 weeks
        print("Compiling weekly progress reports...")
        for week_offset in [14, 7, 0]:
            w_end = today - timedelta(days=week_offset)
            ReportService.generate_weekly_report(user_id=demo_user.id, week_end_date=w_end)

        print("\n==================================================")
        print("DATABASE SEEDING COMPLETE!")
        print("Demo User:  demo@wellness.ai  / DemoPass123!")
        print("Admin User: admin@wellness.ai / AdminPass123!")
        print("==================================================")


if __name__ == "__main__":
    seed_demo_environment()
