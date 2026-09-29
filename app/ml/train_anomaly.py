"""
Model D — Anomaly Detection Pipeline.
Uses Isolation Forest to detect data entry issues, unusual behavioral shifts, and activity outliers.
PURPOSE: Data quality, logging validation, and behavioral pattern alerts.
DOES NOT diagnose medical conditions.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wellness.ml.train_anomaly")

ANOMALY_FEATURES = [
    "steps",
    "water_liters",
    "sleep_hours",
    "exercise_minutes",
]


def train_anomaly_model(
    data_path: Path,
    output_dir: Path,
    version: str = "v1.0.0"
) -> Dict[str, Any]:
    """Train an Isolation Forest model for behavioral anomaly and data quality detection."""
    logger.info(f"Loading data for anomaly model from {data_path}...")
    df = pd.read_csv(data_path)

    # Map dataset column names to activity feature names
    data = pd.DataFrame({
        "steps": df["avg_daily_steps"],
        "water_liters": df["avg_water_intake"],
        "sleep_hours": df["avg_sleep_duration"],
        "exercise_minutes": df["avg_exercise_minutes"],
    })

    # Add realistic edge/abnormal cases to ensure detection capability
    synthetic_anomalies = pd.DataFrame([
        {"steps": 45000, "water_liters": 0.4, "sleep_hours": 1.5, "exercise_minutes": 240},
        {"steps": 100, "water_liters": 8.5, "sleep_hours": 16.0, "exercise_minutes": 0},
        {"steps": 52000, "water_liters": 1.0, "sleep_hours": 2.0, "exercise_minutes": 300},
        {"steps": 500, "water_liters": 0.2, "sleep_hours": 14.5, "exercise_minutes": 0},
        {"steps": 38000, "water_liters": 0.5, "sleep_hours": 3.0, "exercise_minutes": 180},
    ])
    training_data = pd.concat([data, synthetic_anomalies], ignore_index=True)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(training_data[ANOMALY_FEATURES])

    # Isolation Forest with 3% contamination expectation
    model = IsolationForest(
        n_estimators=100,
        contamination=0.03,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_scaled)

    # Evaluate detection on the injected anomalies
    test_scaled = scaler.transform(synthetic_anomalies[ANOMALY_FEATURES])
    preds = model.predict(test_scaled)
    detected_count = int(np.sum(preds == -1))
    logger.info(f"Anomaly detector identified {detected_count}/{len(synthetic_anomalies)} severe outlier patterns.")

    version_dir = output_dir / "anomaly" / version
    version_dir.mkdir(parents=True, exist_ok=True)
    prod_dir = output_dir / "production"
    prod_dir.mkdir(parents=True, exist_ok=True)

    artifact = {
        "model": model,
        "scaler": scaler,
        "features": ANOMALY_FEATURES,
    }

    joblib.dump(artifact, version_dir / "anomaly_detector.joblib")
    joblib.dump(artifact, prod_dir / "anomaly_detector.joblib")

    meta = {
        "model_name": "anomaly_detector",
        "version": version,
        "algorithm": "IsolationForest",
        "contamination": 0.03,
        "features": ANOMALY_FEATURES,
        "status": "production",
        "description": "Behavioral outlier and data entry quality detection.",
    }

    with open(version_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)
    with open(prod_dir / "anomaly_metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    logger.info("Anomaly detection model trained and saved successfully.")
    return meta
