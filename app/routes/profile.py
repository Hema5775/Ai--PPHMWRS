"""
User Health Profile Blueprint.
Allows users to view and update biometrics, goals, and lifestyle preferences.
Separates user-entered inputs from calculated physiological estimates (BMI, BMR).
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from app.extensions import db
from app.routes.auth import login_required
from app.models.health_profile import HealthProfile
from app.validation.schemas import ProfileUpdateSchema
from app.validation.validators import format_pydantic_errors
from app.services.audit_service import AuditService
from app.services.recommendation_service import RecommendationService
from pydantic import ValidationError

profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/profile", methods=["GET", "POST"])
@login_required
def index():
    user = g.user
    profile = user.profile
    if not profile:
        profile = HealthProfile(
            user_id=user.id,
            age=30,
            gender="other",
            height_cm=170.0,
            weight_kg=70.0,
            activity_level="moderately_active",
            dietary_preference="balanced",
            health_goal="maintenance",
        )
        profile.calculate_metrics()
        db.session.add(profile)
        db.session.commit()

    if request.method == "POST":
        form_data = {
            "name": request.form.get("name", "").strip(),
            "age": int(request.form.get("age", profile.age)) if request.form.get("age") else None,
            "gender": request.form.get("gender", profile.gender),
            "height_cm": float(request.form.get("height_cm", profile.height_cm)) if request.form.get("height_cm") else None,
            "weight_kg": float(request.form.get("weight_kg", profile.weight_kg)) if request.form.get("weight_kg") else None,
            "activity_level": request.form.get("activity_level", profile.activity_level),
            "dietary_preference": request.form.get("dietary_preference", profile.dietary_preference),
            "health_goal": request.form.get("health_goal", profile.health_goal),
            "allergies": request.form.get("allergies", "").strip(),
            "physical_limitations": request.form.get("physical_limitations", "none").strip(),
            "target_sleep_hours": float(request.form.get("target_sleep_hours", profile.target_sleep_hours)) if request.form.get("target_sleep_hours") else None,
            "target_water_liters": float(request.form.get("target_water_liters", profile.target_water_liters)) if request.form.get("target_water_liters") else None,
            "target_steps": int(request.form.get("target_steps", profile.target_steps)) if request.form.get("target_steps") else None,
        }

        try:
            validated = ProfileUpdateSchema(**form_data)
        except ValidationError as err:
            errors = format_pydantic_errors(err)
            for e in errors:
                flash(f"{e['field']}: {e['message']}", "danger")
            return render_template("profile.html", user=user, profile=profile)

        # Update user name if changed
        if validated.name:
            user.name = validated.name

        # Update profile fields
        if validated.age is not None:
            profile.age = validated.age
        if validated.gender:
            profile.gender = validated.gender
        if validated.height_cm is not None:
            profile.height_cm = validated.height_cm
        if validated.weight_kg is not None:
            profile.weight_kg = validated.weight_kg
        if validated.activity_level:
            profile.activity_level = validated.activity_level
        if validated.dietary_preference:
            profile.dietary_preference = validated.dietary_preference
        if validated.health_goal:
            profile.health_goal = validated.health_goal
        if validated.allergies is not None:
            profile.allergies = validated.allergies
        if validated.physical_limitations is not None:
            profile.physical_limitations = validated.physical_limitations
        if validated.target_sleep_hours is not None:
            profile.target_sleep_hours = validated.target_sleep_hours
        if validated.target_water_liters is not None:
            profile.target_water_liters = validated.target_water_liters
        if validated.target_steps is not None:
            profile.target_steps = validated.target_steps

        # Recalculate deterministic biometrics
        profile.calculate_metrics()
        db.session.commit()

        AuditService.log_event("PROFILE_UPDATE", user_id=user.id, details={"health_goal": profile.health_goal})

        # Refresh recommendations for updated targets
        try:
            RecommendationService.generate_daily_recommendation(user_id=user.id, force_refresh=True)
        except Exception:
            pass

        flash("Your health profile and calculated metrics have been successfully updated.", "success")
        return redirect(url_for("profile.index"))

    return render_template("profile.html", user=user, profile=profile)
