"""
Master Training Pipeline Orchestrator.
Trains and validates Model A (Recommendation), Model D (Anomaly Detection), and Model E (Similarity).
Runs automated health audits and registers production candidates.
"""

import sys
import logging
from pathlib import Path
from app.ml.data_generator import generate_synthetic_data
from app.ml.train_recommendation import train_and_select_recommendation_model
from app.ml.train_anomaly import train_anomaly_model
from app.ml.similarity_engine import train_similarity_engine
from app.ml.model_registry import ModelRegistry
from app.ml.model_health import ModelHealthMonitor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("wellness.ml.train_all")


def run_full_training_pipeline(
    data_dir: Path,
    model_dir: Path,
    registry_file: Path,
    num_samples: int = 50000,
    force_data_gen: bool = False
) -> dict:
    """Execute complete end-to-end training, selection, and health audit pipeline."""
    logger.info("==================================================")
    logger.info("STARTING MASTER ML TRAINING PIPELINE")
    logger.info("==================================================")

    data_dir = Path(data_dir)
    model_dir = Path(model_dir)
    registry_file = Path(registry_file)

    synthetic_file = data_dir / "synthetic" / "synthetic_development_data.csv"
    if force_data_gen or not synthetic_file.exists():
        logger.info(f"Generating synthetic development dataset ({num_samples} records)...")
        generate_synthetic_data(num_samples=num_samples, output_path=str(synthetic_file))
    else:
        logger.info(f"Found existing synthetic development data at {synthetic_file}")

    # 1. Train Model A: Recommendation Category Model
    logger.info("\n--- Phase 1: Training Model A (Recommendation Classifier) ---")
    rec_meta = train_and_select_recommendation_model(
        data_path=synthetic_file,
        output_dir=model_dir,
        registry_file=registry_file,
        version="v1.0.0",
        set_as_active=True,
    )

    # 2. Train Model D: Anomaly Detector (Isolation Forest)
    logger.info("\n--- Phase 2: Training Model D (Anomaly Detector) ---")
    anomaly_meta = train_anomaly_model(
        data_path=synthetic_file,
        output_dir=model_dir,
        version="v1.0.0",
    )

    # 3. Train Model E: Personalization Similarity Engine (NearestNeighbors)
    logger.info("\n--- Phase 3: Training Model E (Similarity Engine) ---")
    sim_meta = train_similarity_engine(
        data_path=synthetic_file,
        output_dir=model_dir,
        version="v1.0.0",
    )

    # 4. Master Health Audit & Smoke Tests
    logger.info("\n--- Phase 4: Executing Automated ML Health Checks ---")
    prod_dir = model_dir / "production"
    registry = ModelRegistry(registry_file=registry_file, model_dir=prod_dir)
    loaded = registry.load_active_model_and_preprocessor("recommendation_model")

    health_report = ModelHealthMonitor.run_health_checks(
        model_name="recommendation_model",
        model_artifact=loaded["model"],
        preprocessor_artifact=loaded["preprocessor"],
        meta=rec_meta,
        model_file_path=Path(rec_meta["artifact_path"]),
    )

    logger.info("Health Check Status: %s", health_report["status"])
    for chk, details in health_report["checks"].items():
        pass_str = "PASS" if details.get("passed") else "FAIL"
        logger.info(f"  [{pass_str}] {chk}: {details}")

    if not health_report["overall_passed"]:
        logger.error("ML Health Audit FAILED. Review issues: %s", health_report["issues"])
        raise RuntimeError("Trained model failed automated self-validation checks.")

    logger.info("\n==================================================")
    logger.info("MASTER ML TRAINING PIPELINE COMPLETED SUCCESSFULLY!")
    logger.info(f"Selected Algorithm: {rec_meta['algorithm']}")
    logger.info(f"Test Accuracy: {rec_meta['metrics']['accuracy']:.4f}")
    logger.info(f"Test F1 (macro): {rec_meta['metrics']['f1_macro']:.4f}")
    logger.info("==================================================")

    return {
        "recommendation": rec_meta,
        "anomaly": anomaly_meta,
        "similarity": sim_meta,
        "health": health_report,
    }


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent.parent
    data_dir = base_dir / "data"
    model_dir = base_dir / "models"
    registry_file = model_dir / "model_registry.json"
    run_full_training_pipeline(data_dir, model_dir, registry_file, num_samples=50000)
