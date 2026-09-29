"""
AI Wellness Assistant Service.
Grounded strictly in the user's real application data and historical database records.
CRITICAL SAFETY BOUNDARIES:
- Does NOT diagnose illnesses or pathological conditions.
- Does NOT prescribe medications or alter clinical regimens.
- Does NOT provide emergency or acute triage advice.
- Directs users to healthcare professionals for clinical questions.
"""

from typing import Dict, Any, List
from datetime import date, timedelta
import numpy as np

from app.models.user import User
from app.models.health_profile import HealthProfile
from app.models.activity import DailyActivity
from app.models.wellness_score import WellnessScore
from app.models.task import DailyTask
from app.models.recommendation import Recommendation


class WellnessAssistantService:
    """Intelligent wellness conversational assistant grounded in personal database telemetry."""

    MEDICAL_DISCLAIMER = (
        "Note: I am an AI wellness assistant, not a doctor. I cannot provide medical diagnoses, "
        "triage emergency symptoms, or advise on medications. For clinical concerns, please consult a qualified healthcare professional."
    )

    RED_FLAG_KEYWORDS = [
        "chest pain", "shortness of breath", "stroke", "heart attack", "bleeding",
        "suicide", "depression", "overdose", "prescribe", "medication", "dose",
        "cure cancer", "diagnose", "infection", "disease", "emergency"
    ]

    @classmethod
    def answer_query(cls, user_id: int, user_message: str) -> Dict[str, Any]:
        """Process conversational query against real database state with safety filters."""
        query_lower = user_message.lower().strip()

        # Safety Check 1: Acute medical / red flag screening
        for rf in cls.RED_FLAG_KEYWORDS:
            if rf in query_lower:
                return {
                    "reply": (
                        f"Your query references clinical symptoms or medication: '{rf}'. "
                        "I am designed strictly for general health monitoring and lifestyle habits. "
                        "Please contact your primary care physician, an urgent care facility, or local emergency services (e.g. 911 / 112) immediately."
                    ),
                    "disclaimer": cls.MEDICAL_DISCLAIMER,
                    "grounded_data": None,
                }

        profile = HealthProfile.query.filter_by(user_id=user_id).first()
        today = date.today()
        today_activity = DailyActivity.query.filter_by(user_id=user_id, date=today).first()
        today_tasks = DailyTask.query.filter_by(user_id=user_id, date=today).all()
        today_score = WellnessScore.query.filter_by(user_id=user_id, date=today).first()
        today_rec = Recommendation.query.filter_by(user_id=user_id, date=today).first()

        # Last 7 days activities
        week_ago = today - timedelta(days=6)
        recent_acts = DailyActivity.query.filter(
            DailyActivity.user_id == user_id,
            DailyActivity.date >= week_ago,
            DailyActivity.date <= today,
        ).order_by(DailyActivity.date.asc()).all()

        # Context stats
        steps_list = [a.steps for a in recent_acts]
        sleep_list = [a.sleep_hours for a in recent_acts]
        water_list = [a.water_liters for a in recent_acts]

        avg_steps_7d = int(np.mean(steps_list)) if steps_list else (today_activity.steps if today_activity else 0)
        avg_sleep_7d = round(float(np.mean(sleep_list)), 1) if sleep_list else (today_activity.sleep_hours if today_activity else 0.0)
        avg_water_7d = round(float(np.mean(water_list)), 1) if water_list else (today_activity.water_liters if today_activity else 0.0)

        grounded = {
            "avg_steps_7d": avg_steps_7d,
            "avg_sleep_7d": avg_sleep_7d,
            "avg_water_7d": avg_water_7d,
            "today_steps": today_activity.steps if today_activity else 0,
            "today_water": today_activity.water_liters if today_activity else 0.0,
            "today_sleep": today_activity.sleep_hours if today_activity else 0.0,
            "today_score": today_score.total_score if today_score else None,
            "tasks_count": len(today_tasks),
            "tasks_completed": sum(1 for t in today_tasks if t.completed),
        }

        total_acts_count = DailyActivity.query.filter_by(user_id=user_id).count()

        # Intent 1: "Why did my score fall / change?"
        if any(w in query_lower for w in ["score", "why did my score", "score fall", "score drop", "score low", "score change"]):
            if today_score:
                subscores = [
                    ("Activity", today_score.activity_score),
                    ("Hydration", today_score.hydration_score),
                    ("Sleep", today_score.sleep_score),
                    ("Tasks", today_score.task_score),
                    ("Consistency", today_score.consistency_score),
                ]
                lowest = sorted(subscores, key=lambda x: x[1])[0]
                reply = (
                    f"Your Wellness Score for today stands at {today_score.total_score:.1f}/100. "
                    f"Your strongest component is {sorted(subscores, key=lambda x: x[1])[-1][0]} ({sorted(subscores, key=lambda x: x[1])[-1][1]:.0f}/100), "
                    f"while your lowest component right now is {lowest[0]} ({lowest[1]:.0f}/100). "
                    f"If you want a quick lift before the day ends, topping up your hydration or checking off your remaining daily tasks is the easiest way to give it a boost."
                )
            else:
                reply = (
                    "You haven't logged any activity today yet, so your daily wellness score is currently pending. "
                    "Once you record your steps and rest on the Activity page, I will immediately calculate your breakdown."
                )

        # Intent 2: "What should I focus on today?" / "What to do today?"
        elif any(w in query_lower for w in ["focus", "what to do", "priority", "task", "today"]):
            focus_points = []
            if today_activity:
                target_w = profile.target_water_liters if profile else 2.5
                target_s = profile.target_steps if profile else 8000
                if today_activity.water_liters < target_w:
                    rem_w = round(target_w - today_activity.water_liters, 1)
                    focus_points.append(f"drink ~{rem_w}L more water to hit your {target_w:.1f}L target")
                if today_activity.steps < target_s:
                    rem_s = target_s - today_activity.steps
                    focus_points.append(f"accumulate ~{rem_s:,} more steps to reach your {target_s:,} daily goal")
            else:
                focus_points.append("log what you actually did today in the Activity tab")

            incomplete_tasks = [t.title for t in today_tasks if not t.completed]
            if incomplete_tasks:
                focus_points.append(f"complete your daily micro-tasks ({', '.join(incomplete_tasks[:2])})")

            rec_focus = today_rec.category.replace("_", " ") if today_rec else "balanced wellness"

            if focus_points:
                reply = f"Today's strategic focus is {rec_focus.title()}. Your top priorities: {'; '.join(focus_points)}. One step at a time!"
            else:
                reply = f"Honestly, you're crushing it today! You've met your hydration and step targets. Focus on an early wind-down and good sleep tonight."

        # Intent 3: "Average sleep / steps / water this week"
        elif any(w in query_lower for w in ["sleep", "average sleep", "sleep this week", "how much sleep", "how much did i sleep", "average steps", "steps this week", "water this week"]):
            if not sleep_list and not steps_list:
                reply = (
                    "I don't have enough data recorded for you this week yet to give you actual averages. "
                    "Log today's sleep and steps on the Activity page, and I will start calculating your weekly trends right away."
                )
            else:
                days_counted = len(recent_acts)
                reply = (
                    f"Based on your actual database entries over the past 7 days ({days_counted} day{'s' if days_counted != 1 else ''} logged): "
                    f"you averaged {avg_steps_7d:,} steps per day, {avg_sleep_7d:.1f} hours of sleep per night, and {avg_water_7d:.1f} Liters of water. "
                    f"{'Looking like a very solid baseline!' if avg_sleep_7d >= 7.0 else 'A little extra pillow time might do wonders.'}"
                )

        # Intent 4: "How is my activity trending?"
        elif any(w in query_lower for w in ["trend", "trending", "how is my activity", "progress", "trajectory"]):
            if len(recent_acts) < 3:
                reply = (
                    f"You have {len(recent_acts)} day{'s' if len(recent_acts) != 1 else ''} recorded recently. "
                    "That is a great start, but I need at least 3 logged days before I can calculate a real behavioral slope and trend. "
                    "Keep logging over the next couple of days, and I'll show you exactly how you're progressing!"
                )
            else:
                from app.services.report_service import ReportService
                direction, summary = ReportService.analyze_behavioral_trends(recent_acts, [])
                reply = (
                    f"Your activity trajectory is currently {direction.upper()}. "
                    f"{summary} You can also check the Progress page for a 7, 14, or 30-day visual chart."
                )

        # Intent 5: Dietary / Meal / Nutrition questions
        elif any(w in query_lower for w in ["diet", "food", "eat", "meal", "nutrition", "calories"]):
            pref = profile.dietary_preference if profile else "balanced"
            goal = profile.health_goal if profile else "maintenance"
            allergies = profile.allergies if (profile and profile.allergies) else None
            allergy_note = f" (strictly filtered to exclude your allergy: {allergies})" if allergies else ""
            reply = (
                f"Your nutrition plan is tailored around a {pref.title()} approach supporting your goal of {goal.replace('_', ' ')}{allergy_note}. "
                "Head over to the Recommendations tab to see your full meal breakdown, calorie estimates, and whole-food suggestions for today."
            )

        # General friendly wellness reply
        else:
            first_name = profile.user.name.split(' ')[0] if profile and profile.user else 'there'
            if total_acts_count == 0:
                reply = (
                    f"Hi {first_name}! Welcome to Vitalis AI. You haven't logged any activity yet, "
                    "so I don't have historical data to analyze. Once you record your first day in the Activity tab, "
                    "you can ask me about your scores, weekly sleep, trends, and daily priorities!"
                )
            else:
                reply = (
                    f"Hi {first_name}! Over your recent logged days, your daily step average is {avg_steps_7d:,} steps and your sleep average is {avg_sleep_7d:.1f} hours. "
                    "Feel free to ask me things like 'Why did my score change?', 'What should I focus on today?', 'How is my activity trending?', or 'What is my diet guidance?'"
                )

        return {
            "reply": reply,
            "disclaimer": cls.MEDICAL_DISCLAIMER,
            "grounded_data": grounded,
        }
