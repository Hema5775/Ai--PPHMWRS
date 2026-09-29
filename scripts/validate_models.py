"""
CLI script to execute comprehensive model validation and 11-step health checks.
"""

from pathlib import Path
import sys
import json

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.ml.model_registry import ModelRegistry
from app.ml.model_health import ModelHealthMonitor

if __name__ == "__main__":
    reg_file = BASE_DIR / "models" / "model_registry.json"
    prod_dir = BASE_DIR / "models" / "production"

    print("==================================================")
    print("MODEL VALIDATION & HEALTH INTEGRITY AUDIT")
    print("==================================================")

    registry = ModelRegistry(registry_file=reg_file, model_dir=prod_dir)
    loaded = registry.load_active_model_and_preprocessor("recommendation_model")
    meta = registry.get_active_model_meta("recommendation_model")

    if not loaded.get("model"):
        print("ERROR: No active recommendation model loaded from registry or production folder!")
        sys.exit(1)

    artifact_path = Path(meta["artifact_path"]) if (meta and meta.get("artifact_path")) else None

    report = ModelHealthMonitor.run_health_checks(
        model_name="recommendation_model",
        model_artifact=loaded["model"],
        preprocessor_artifact=loaded["preprocessor"],
        meta=meta,
        model_file_path=artifact_path,
    )

    print(f"Model Name:      {report['model_name']}")
    print(f"Algorithm:       {report['algorithm']}")
    print(f"Health Status:   {report['status']}")
    print(f"Overall Passed:  {report['overall_passed']}")
    print("\nDetailed Health Checks:")
    for chk_name, chk_res in report["checks"].items():
        symbol = "PASS" if chk_res.get("passed") else "FAIL"
        print(f"  [{symbol}] {chk_name}: {chk_res}")

    if report["issues"]:
        print("\nDetected Issues / Warnings:")
        for issue in report["issues"]:
            print(f"  ! {issue}")

    if not report["overall_passed"]:
        print("\nAUDIT FAILED: Model did not satisfy minimum validation criteria.")
        sys.exit(1)
    else:
        print("\nAUDIT PASSED: All 11 health checks verified successfully!")
        sys.exit(0)
