"""
Automated 11-Step ML Health Monitor and Drift Tests.
"""

from pathlib import Path
from app.ml.model_registry import ModelRegistry
from app.ml.model_health import ModelHealthMonitor
from app.ml.drift_detection import DriftDetector


def test_11_step_health_audit(app):
    reg_path = Path("models/model_registry.json")
    prod_dir = Path("models/production")
    registry = ModelRegistry(registry_file=reg_path, model_dir=prod_dir)

    loaded = registry.load_active_model_and_preprocessor("recommendation_model")
    meta = registry.get_active_model_meta("recommendation_model")

    report = ModelHealthMonitor.run_health_checks(
        model_name="recommendation_model",
        model_artifact=loaded.get("model"),
        preprocessor_artifact=loaded.get("preprocessor"),
        meta=meta,
    )

    assert report["overall_passed"] is True
    assert report["status"] in ["HEALTHY", "WARNING"]
    assert report["checks"]["check_1_file_exists"]["passed"]
    assert report["checks"]["check_2_model_loaded"]["passed"]
    assert report["checks"]["check_3_preprocessor_exists"]["passed"]
    assert report["checks"]["check_4_schema_match"]["passed"]
    assert report["checks"]["check_5_valid_sample_prediction"]["passed"]
    assert report["checks"]["check_6_prediction_category_valid"]["passed"]
    assert report["checks"]["check_7_confidence_valid"]["passed"]
    assert report["checks"]["check_8_classes_valid"]["passed"]
    assert report["checks"]["check_9_no_nan_or_inf"]["passed"]


def test_drift_detector():
    baseline = {
        "avg_daily_steps": {"mean": 8000.0, "std": 1500.0, "min": 2000, "max": 18000, "p25": 7000, "p50": 8000, "p75": 9000}
    }
    detector = DriftDetector(baseline_stats=baseline)

    # Normal sample
    normal_res = detector.check_sample_drift({"avg_daily_steps": 8200})
    assert not normal_res["has_drift_warning"]

    # Extreme sample (>3.5 std)
    outlier_res = detector.check_sample_drift({"avg_daily_steps": 18000})
    assert outlier_res["has_drift_warning"]
