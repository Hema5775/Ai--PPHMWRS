"""
Data Drift Detection System.
Monitors incoming input distributions compared with training baseline statistics.
Flags significant behavioral drift without automatically retraining without validation.
"""

from typing import Dict, Any, List, Optional
import numpy as np
from scipy import stats


class DriftDetector:
    """Monitors feature distribution shifts against training baseline statistics."""

    DRIFT_FEATURES = [
        "age",
        "bmi",
        "avg_daily_steps",
        "avg_sleep_duration",
        "avg_water_intake",
        "avg_exercise_minutes",
    ]

    def __init__(self, baseline_stats: Optional[Dict[str, Dict[str, float]]] = None):
        self.baseline_stats = baseline_stats or {}

    @classmethod
    def fit_from_dataframe(cls, df: Any) -> "DriftDetector":
        """Compute baseline statistical profile from a training DataFrame."""
        stats_dict = {}
        for col in cls.DRIFT_FEATURES:
            if col in df.columns:
                series = df[col].dropna().astype(float)
                stats_dict[col] = {
                    "mean": float(series.mean()),
                    "std": float(series.std()) if series.std() > 0 else 1.0,
                    "min": float(series.min()),
                    "max": float(series.max()),
                    "p25": float(series.quantile(0.25)),
                    "p50": float(series.median()),
                    "p75": float(series.quantile(0.75)),
                }
        return cls(baseline_stats=stats_dict)

    def check_sample_drift(self, sample_features: Dict[str, Any]) -> Dict[str, Any]:
        """Check if an individual input sample lies in extreme outlier/drift territory."""
        drift_warnings = []
        for col, col_stats in self.baseline_stats.items():
            val = sample_features.get(col)
            if val is not None and isinstance(val, (int, float)):
                mean = col_stats["mean"]
                std = col_stats["std"]
                z_score = abs(val - mean) / max(std, 1e-4)
                if z_score > 3.5:
                    drift_warnings.append({
                        "feature": col,
                        "value": val,
                        "mean": round(mean, 2),
                        "z_score": round(z_score, 2),
                        "severity": "HIGH",
                    })
        return {
            "has_drift_warning": len(drift_warnings) > 0,
            "warnings": drift_warnings,
        }

    def check_batch_drift(self, recent_samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Check a recent batch of activity/profile records against training baseline.
        Uses 2-sample Kolmogorov-Smirnov test or normalized difference of means.
        """
        if not self.baseline_stats or len(recent_samples) < 10:
            return {
                "status": "INSUFFICIENT_DATA",
                "drift_detected": False,
                "message": "Minimum 10 recent samples required for statistical drift monitoring.",
                "feature_drift": {},
            }

        drift_detected = False
        feature_drift = {}

        for col, col_stats in self.baseline_stats.items():
            vals = [float(s[col]) for s in recent_samples if col in s and s[col] is not None]
            if len(vals) >= 10:
                recent_mean = float(np.mean(vals))
                baseline_mean = col_stats["mean"]
                baseline_std = max(col_stats["std"], 1e-4)
                shift = abs(recent_mean - baseline_mean) / baseline_std

                # If mean shift exceeds 1.5 standard deviations of the baseline
                is_drifted = shift > 1.5
                if is_drifted:
                    drift_detected = True

                feature_drift[col] = {
                    "baseline_mean": round(baseline_mean, 2),
                    "recent_mean": round(recent_mean, 2),
                    "std_shift": round(shift, 2),
                    "is_drifted": is_drifted,
                }

        return {
            "status": "WARNING" if drift_detected else "HEALTHY",
            "drift_detected": drift_detected,
            "message": (
                "Input distribution has changed significantly. Consider retraining the model."
                if drift_detected
                else "Input distributions are consistent with training baseline."
            ),
            "feature_drift": feature_drift,
        }
