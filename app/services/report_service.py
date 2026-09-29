"""
Model C — Trend / Progress Analysis and Weekly Report Service.
Uses robust slope estimation and rolling comparisons to identify behavioral progress trends.
Generates comprehensive weekly summaries with factual achievements and focus areas.
"""

import json
from datetime import date, timedelta
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from app.extensions import db
from app.models.weekly_report import WeeklyReport
from app.models.activity import DailyActivity
from app.models.wellness_score import WellnessScore
from app.models.task import DailyTask


class ReportService:
    """Computes Model C trend slopes and compiles weekly progress analytics."""

    @staticmethod
    def analyze_behavioral_trends(
        current_week_activities: List[DailyActivity],
        prev_week_activities: List[DailyActivity]
    ) -> Tuple[str, str]:
        """
        Model C: Compares recent behavior against previous week using percentage shifts and robust slope.
        Returns: (trend_direction, trend_summary)
        """
        if not current_week_activities:
            return "stable", "Keep logging your daily activity to reveal personal wellness trends."

        cur_steps = [a.steps for a in current_week_activities]
        cur_sleep = [a.sleep_hours for a in current_week_activities]
        cur_water = [a.water_liters for a in current_week_activities]

        cur_avg_steps = float(np.mean(cur_steps)) if cur_steps else 0.0
        cur_avg_sleep = float(np.mean(cur_sleep)) if cur_sleep else 0.0
        cur_avg_water = float(np.mean(cur_water)) if cur_water else 0.0

        if prev_week_activities:
            prev_steps = [a.steps for a in prev_week_activities]
            prev_sleep = [a.sleep_hours for a in prev_week_activities]
            prev_avg_steps = float(np.mean(prev_steps)) if prev_steps else cur_avg_steps
            prev_avg_sleep = float(np.mean(prev_sleep)) if prev_sleep else cur_avg_sleep

            step_delta_pct = ((cur_avg_steps - prev_avg_steps) / max(prev_avg_steps, 1000)) * 100
            sleep_delta_h = cur_avg_sleep - prev_avg_sleep

            insights = []
            if step_delta_pct >= 8.0:
                insights.append(f"Average daily movement increased by {abs(step_delta_pct):.0f}% compared with last week.")
            elif step_delta_pct <= -8.0:
                insights.append(f"Daily steps dipped by {abs(step_delta_pct):.0f}% compared with the prior week.")
            else:
                insights.append("Daily step volume remained consistent with the previous week.")

            if sleep_delta_h >= 0.4:
                insights.append(f"Nightly sleep duration expanded by {abs(sleep_delta_h):.1f} hours.")
            elif sleep_delta_h <= -0.4:
                insights.append(f"Sleep duration averaged {abs(sleep_delta_h):.1f} hours less than last week.")

            # Overall direction
            if step_delta_pct >= 5.0 and sleep_delta_h >= -0.2:
                direction = "improving"
            elif step_delta_pct <= -8.0 and sleep_delta_h < -0.3:
                direction = "declining"
            else:
                direction = "stable"

            summary = " ".join(insights)
            return direction, summary

        # If only current week exists, compute 7-day linear slope
        if len(cur_steps) >= 3:
            x = np.arange(len(cur_steps))
            slope, _ = np.polyfit(x, cur_steps, 1)
            if slope > 250:
                direction = "improving"
                summary = f"Your daily step count showed an upward trajectory across the week (+{int(slope)} steps/day slope)."
            elif slope < -250:
                direction = "declining"
                summary = f"Daily movement trended downward across recent days ({int(slope)} steps/day slope)."
            else:
                direction = "stable"
                summary = f"Steady daily activity observed throughout the logged days (average {int(cur_avg_steps):,} steps)."
            return direction, summary

        return "stable", "Baseline established. Continue recording daily entries to track your weekly trajectory."

    @classmethod
    def generate_weekly_report(
        cls,
        user_id: int,
        week_end_date: Optional[date] = None
    ) -> WeeklyReport:
        """Aggregate past 7 days of metrics and save/update WeeklyReport."""
        if week_end_date is None:
            week_end_date = date.today()

        week_start_date = week_end_date - timedelta(days=6)
        prev_week_start = week_start_date - timedelta(days=7)
        prev_week_end = week_start_date - timedelta(days=1)

        cur_activities = DailyActivity.query.filter(
            DailyActivity.user_id == user_id,
            DailyActivity.date >= week_start_date,
            DailyActivity.date <= week_end_date,
        ).order_by(DailyActivity.date.asc()).all()

        prev_activities = DailyActivity.query.filter(
            DailyActivity.user_id == user_id,
            DailyActivity.date >= prev_week_start,
            DailyActivity.date <= prev_week_end,
        ).order_by(DailyActivity.date.asc()).all()

        # Averages
        if cur_activities:
            avg_steps = float(np.mean([a.steps for a in cur_activities]))
            avg_sleep = float(np.mean([a.sleep_hours for a in cur_activities]))
            avg_water = float(np.mean([a.water_liters for a in cur_activities]))
            avg_ex = float(np.mean([a.exercise_minutes for a in cur_activities]))
            active_ex_days = sum(1 for a in cur_activities if a.exercise_minutes >= 20)
            ex_consistency = (active_ex_days / 7.0) * 100.0
        else:
            avg_steps, avg_sleep, avg_water, avg_ex, ex_consistency = 0.0, 0.0, 0.0, 0.0, 0.0

        # Tasks completed
        tasks = DailyTask.query.filter(
            DailyTask.user_id == user_id,
            DailyTask.date >= week_start_date,
            DailyTask.date <= week_end_date,
        ).all()
        task_comp = (sum(1 for t in tasks if t.completed) / len(tasks) * 100.0) if tasks else 0.0

        # Average wellness score
        scores = WellnessScore.query.filter(
            WellnessScore.user_id == user_id,
            WellnessScore.date >= week_start_date,
            WellnessScore.date <= week_end_date,
        ).all()
        avg_score = float(np.mean([s.total_score for s in scores])) if scores else 0.0

        # Model C Trend Analysis
        trend_direction, trend_summary = cls.analyze_behavioral_trends(cur_activities, prev_activities)

        # Achievements
        achievements = []
        if avg_steps >= 8000:
            achievements.append("Maintained 8,000+ daily step average.")
        if avg_sleep >= 7.0:
            achievements.append("Achieved 7+ hours nightly average sleep target.")
        if avg_water >= 2.2:
            achievements.append("Consistent daily hydration baseline achieved.")
        if ex_consistency >= 70.0:
            achievements.append(f"High exercise frequency ({int(ex_consistency)}% active days).")
        if not achievements and cur_activities:
            achievements.append(f"Recorded {len(cur_activities)} active daily logs this week.")

        # Focus areas
        focus_areas = []
        if avg_steps < 6000:
            focus_areas.append("Incorporate short 10-minute movement breaks to lift step totals.")
        if avg_sleep < 6.5:
            focus_areas.append("Establish a consistent wind-down routine 45 minutes before bedtime.")
        if avg_water < 2.0:
            focus_areas.append("Keep a refillable water bottle at your workspace.")
        if task_comp < 60.0:
            focus_areas.append("Review daily micro-tasks earlier in the morning.")

        rec_summary = (
            f"Overall behavioral trend is {trend_direction.upper()}. "
            f"Continue prioritizing balance across movement, hydration, and sleep hygiene."
        )

        report = WeeklyReport.query.filter_by(user_id=user_id, week_start=week_start_date).first()
        if not report:
            report = WeeklyReport(
                user_id=user_id,
                week_start=week_start_date,
                week_end=week_end_date,
                avg_steps=avg_steps,
                avg_sleep_hours=avg_sleep,
                avg_water_liters=avg_water,
                avg_exercise_minutes=avg_ex,
                exercise_consistency_pct=ex_consistency,
                task_completion_pct=task_comp,
                avg_wellness_score=avg_score,
                trend_direction=trend_direction,
                trend_summary=trend_summary,
                achievements_json=json.dumps(achievements),
                focus_areas_json=json.dumps(focus_areas),
                recommendations_summary=rec_summary,
            )
            db.session.add(report)
        else:
            report.week_end = week_end_date
            report.avg_steps = avg_steps
            report.avg_sleep_hours = avg_sleep
            report.avg_water_liters = avg_water
            report.avg_exercise_minutes = avg_ex
            report.exercise_consistency_pct = ex_consistency
            report.task_completion_pct = task_comp
            report.avg_wellness_score = avg_score
            report.trend_direction = trend_direction
            report.trend_summary = trend_summary
            report.achievements_json = json.dumps(achievements)
            report.focus_areas_json = json.dumps(focus_areas)
            report.recommendations_summary = rec_summary

        db.session.commit()
        return report
