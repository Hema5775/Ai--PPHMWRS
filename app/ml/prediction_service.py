"""
Unified ML Prediction and Inference Service.
Integrates Model A, Model D, and Model E with automatic error recovery,
explainability, and multi-tier fallback safety.
"""

import math
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd
import joblib

from app.ml.feature_engineering import (
    ALL_FEATURES,
    extract_features_from_history,
    to_dataframe,
)
from app.ml.model_registry import ModelRegistry
from app.ml.model_health import ModelHealthMonitor
from app.ml.fallback import FallbackRecommendationEngine
from app.ml.drift_detection import DriftDetector

logger = logging.getLogger("wellness.ml.prediction_service")


class PredictionService:
    """Manages inference, fallback orchestration, and feature explainability."""

    def __init__(self, registry: ModelRegistry, anomaly_path: Optional[Path] = None, similarity_path: Optional[Path] = None):
        self.registry = registry
        self.anomaly_path = anomaly_path
        self.similarity_path = similarity_path
        self._anomaly_artifact = None
        self._similarity_artifact = None

    def _load_anomaly_artifact(self):
        if self._anomaly_artifact is None and self.anomaly_path and self.anomaly_path.exists():
            try:
                self._anomaly_artifact = joblib.load(self.anomaly_path)
            except Exception as e:
                logger.error(f"Failed to load anomaly detector: {e}")
        return self._anomaly_artifact

    def _load_similarity_artifact(self):
        if self._similarity_artifact is None and self.similarity_path and self.similarity_path.exists():
            try:
                self._similarity_artifact = joblib.load(self.similarity_path)
            except Exception as e:
                logger.error(f"Failed to load similarity engine: {e}")
        return self._similarity_artifact

    def predict_recommendation_category(
        self,
        profile_dict: Dict[str, Any],
        recent_activities: List[Dict[str, Any]],
        recent_wellness_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Predict recommendation category with automatic health validation and fallback hierarchy.
        Returns:
          category, confidence, model_name, model_version, is_fallback, fallback_level,
          feature_snapshot, top_factors (explainability)
        """
        # Step 1: Feature engineering
        features = extract_features_from_history(
            profile_dict=profile_dict,
            recent_activities=recent_activities,
            recent_wellness_score=recent_wellness_score,
        )
        df_input = to_dataframe(features)

        # Step 2: Attempt Level 1 Production Model
        try:
            loaded = self.registry.load_active_model_and_preprocessor("recommendation_model")
            model = loaded.get("model")
            preprocessor = loaded.get("preprocessor")
            meta = loaded.get("meta", {})

            if model is not None and preprocessor is not None:
                X_trans = preprocessor.transform(df_input)
                raw_pred = model.predict(X_trans)
                
                # Extract predicted label
                if hasattr(model, "classes_") and isinstance(raw_pred[0], (int, np.integer)):
                    # XGBoost integer mapping
                    category = str(model.classes_[raw_pred[0]])
                else:
                    category = str(raw_pred[0])

                # Extract confidence
                confidence = 0.85
                if hasattr(model, "predict_proba"):
                    proba = model.predict_proba(X_trans)
                    confidence = float(np.max(proba[0]))
                    if math.isnan(confidence) or math.isinf(confidence):
                        confidence = 0.80

                # Validate predicted category is known
                if category not in ModelHealthMonitor.VALID_RECOMMENDATION_CLASSES:
                    raise ValueError(f"Model generated invalid category: '{category}'")

                # Top contributing factors for explainability
                top_factors = self._calculate_top_factors(features, meta.get("baseline_stats"))

                return {
                    "category": category,
                    "confidence": round(confidence, 3),
                    "model_name": meta.get("algorithm", model.__class__.__name__),
                    "model_version": meta.get("version", "v1.0.0"),
                    "is_fallback": False,
                    "fallback_level": "none",
                    "features": features,
                    "top_factors": top_factors,
                }
            else:
                logger.warning("Active model or preprocessor unavailable. Triggering fallback hierarchy.")

        except Exception as e:
            error_id = f"ML-PRED-{uuid.uuid4().hex[:6].upper()}"
            logger.error(f"[{error_id}] ML prediction failed: {e}. Executing graceful fallback.")

        # Step 3: Attempt Level 2 Rollback Model if registered
        try:
            meta = self.registry.get_active_model_meta("recommendation_model")
            if meta and meta.get("rollback_version"):
                # Could load rollback candidate
                pass
        except Exception:
            pass

        # Step 4: Level 3 Deterministic Rule-Based Engine
        try:
            fallback_res = FallbackRecommendationEngine.level_3_deterministic_recommendation(
                profile_dict=profile_dict,
                recent_features=features,
            )
            top_factors = self._calculate_top_factors(features, None)
            return {
                "category": fallback_res["category"],
                "confidence": fallback_res["confidence"],
                "model_name": fallback_res["model_name"],
                "model_version": fallback_res["model_version"],
                "is_fallback": True,
                "fallback_level": fallback_res["fallback_level"],
                "features": features,
                "top_factors": top_factors,
                "rule_recommendation": fallback_res,
            }
        except Exception as e:
            logger.critical(f"Deterministic fallback failed: {e}. Proceeding to Level 4 Generic guidance.")

        # Step 5: Level 4 Generic Safe Guidance
        generic = FallbackRecommendationEngine.level_4_generic_guidance()
        return {
            "category": generic["category"],
            "confidence": generic["confidence"],
            "model_name": generic["model_name"],
            "model_version": generic["model_version"],
            "is_fallback": True,
            "fallback_level": generic["fallback_level"],
            "features": features,
            "top_factors": ["Standard baseline wellness guidance"],
            "rule_recommendation": generic,
        }

    def detect_activity_anomaly(
        self,
        steps: int,
        water_liters: float,
        sleep_hours: float,
        exercise_minutes: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluate single activity record with Model D Isolation Forest.
        Returns: (is_anomaly, reason)
        DOES NOT diagnose diseases. Strictly data quality and wellness outlier alert.
        """
        artifact = self._load_anomaly_artifact()
        if not artifact:
            # Fallback heuristic sanity check
            if steps > 50000 or sleep_hours > 20 or water_liters > 10 or exercise_minutes > 360:
                return True, "Extreme entry detected relative to standard physiological limits."
            return False, None

        try:
            model = artifact["model"]
            scaler = artifact["scaler"]
            features = artifact["features"]

            sample = np.array([[steps, water_liters, sleep_hours, exercise_minutes]])
            sample_scaled = scaler.transform(sample)
            pred = model.predict(sample_scaled)

            if pred[0] == -1:
                # Anomaly detected
                reasons = []
                if steps > 25000 or steps < 1000:
                    reasons.append(f"Steps ({steps:,}) substantially outside typical activity range")
                if water_liters < 1.0 or water_liters > 6.0:
                    reasons.append(f"Water intake ({water_liters:.1f}L) deviates from expected hydration norms")
                if sleep_hours < 4.0 or sleep_hours > 12.0:
                    reasons.append(f"Sleep duration ({sleep_hours:.1f}h) differs from regular sleep patterns")
                if exercise_minutes > 150:
                    reasons.append(f"Exercise duration ({exercise_minutes}m) is unusually high")

                reason_text = "; ".join(reasons) if reasons else "Activity pattern significantly deviates from your typical routine."
                return True, reason_text

            return False, None
        except Exception as e:
            logger.error(f"Anomaly check failed: {e}")
            return False, None

    def _calculate_top_factors(
        self,
        features: Dict[str, Any],
        baseline_stats: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Explainability: identify factors most influencing this user's wellness state."""
        factors = []

        avg_steps = features.get("avg_daily_steps", 7000)
        avg_sleep = features.get("avg_sleep_duration", 7.0)
        avg_water = features.get("avg_water_intake", 2.2)
        bmi = features.get("bmi", 22.0)
        goal = features.get("health_goal", "maintenance")
        consistency = features.get("consistency_score", 0.7)

        if avg_steps < 5000:
            factors.append(f"Lower daily movement average ({int(avg_steps):,} steps/day)")
        elif avg_steps > 10000:
            factors.append(f"High daily movement volume ({int(avg_steps):,} steps/day)")

        if avg_sleep < 6.5:
            factors.append(f"Sleep duration below target ({avg_sleep:.1f} hours/night)")
        elif avg_sleep >= 7.5:
            factors.append(f"Optimal restorative sleep average ({avg_sleep:.1f} hours/night)")

        if avg_water < 2.0:
            factors.append(f"Hydration intake below target ({avg_water:.1f} L/day)")

        if bmi >= 27.0:
            factors.append(f"Current BMI ({bmi:.1f}) in elevated wellness range")

        if goal:
            factors.append(f"Primary wellness objective: {goal.replace('_', ' ').title()}")

        if consistency < 0.60:
            factors.append(f"Activity consistency ({int(consistency*100)}%) has room for improvement")

        return factors[:4] if factors else ["Standard balanced profile baseline"]
