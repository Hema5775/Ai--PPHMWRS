"""
AI Wellness Assistant Blueprint.
Provides interactive conversational interface answering wellness queries grounded in personal data.
"""

from flask import Blueprint, render_template, g, request, jsonify, redirect, url_for
from app.routes.auth import login_required
from app.services.assistant_service import WellnessAssistantService
from app.validation.schemas import AssistantQuerySchema
from pydantic import ValidationError

assistant_bp = Blueprint("assistant", __name__)


@assistant_bp.route("/assistant")
@login_required
def index():
    return redirect(url_for("dashboard.index", open_companion=1))


@assistant_bp.route("/assistant/chat", methods=["POST"])
@login_required
def chat():
    user = g.user
    data = request.get_json(silent=True) or {}

    try:
        validated = AssistantQuerySchema(**data)
    except ValidationError:
        return jsonify({
            "reply": "Please enter a valid message.",
            "disclaimer": WellnessAssistantService.MEDICAL_DISCLAIMER,
        }), 400

    response = WellnessAssistantService.answer_query(user_id=user.id, user_message=validated.message)
    return jsonify(response)
