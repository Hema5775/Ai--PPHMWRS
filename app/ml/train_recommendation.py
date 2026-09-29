"""
Model A — Wellness / Goal Recommendation Model Training Pipeline.
Trains baseline and candidate models (Logistic Regression, Random Forest, HistGradientBoosting, XGBoost).
Measures real validation metrics and registers the empirically best performer.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple

import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier

try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

from app.ml.feature_engineering import ALL_FEATURES
from app.ml.preprocessing import build_preprocessor
from app.ml.evaluate import evaluate_classifier
from app.ml.drift_detection import DriftDetector
from app.ml.model_registry import ModelRegistry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wellness.ml.train_recommendation")


def train_and_select_recommendation_model(
    data_path: Path,
    output_dir: Path,
    registry_file: Path,
    version: str = "v1.0.0",
    set_as_active: bool = True
) -> Dict[str, Any]:
    """Train candidate models, evaluate, select best, and persist."""
    logger.info(f"Loading training data from {data_path}...")
    if not data_path.exists():
        raise FileNotFoundError(f"Training dataset not found: {data_path}")

    df = pd.read_csv(data_path)
    logger.info(f"Dataset loaded: {len(df)} rows, {len(df.columns)} columns.")

    # Validate target label
    target_col = "recommendation_category"
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' missing from dataset.")

    X = df[ALL_FEATURES]
    y = df[target_col].values
    classes = np.unique(y)

    # Compute baseline distribution stats for drift monitoring
    drift_detector = DriftDetector.fit_from_dataframe(df)
    baseline_stats = drift_detector.baseline_stats

    # Train/test split with stratification
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    logger.info(f"Training set: {len(X_train)} samples, Test set: {len(X_test)} samples.")

    # Fit preprocessor
    logger.info("Fitting preprocessing pipeline on training data...")
    preprocessor = build_preprocessor()
    X_train_trans = preprocessor.fit_transform(X_train)
    X_test_trans = preprocessor.transform(X_test)

    # Candidate models definition
    candidates = {
        "LogisticRegression": LogisticRegression(max_iter=1000, random_state=42),
        "RandomForest": RandomForestClassifier(n_estimators=100, max_depth=12, random_state=42, n_jobs=-1),
        "HistGradientBoosting": HistGradientBoostingClassifier(max_iter=100, max_depth=10, random_state=42),
    }

    if XGBOOST_AVAILABLE:
        # Encode string labels for XGBoost
        class_to_idx = {c: i for i, c in enumerate(classes)}
        idx_to_class = {i: c for i, c in enumerate(classes)}
        y_train_num = np.array([class_to_idx[lbl] for lbl in y_train])
        y_test_num = np.array([class_to_idx[lbl] for lbl in y_test])

        candidates["XGBoost"] = (
            XGBClassifier(n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1, eval_metric="mlogloss"),
            class_to_idx,
            idx_to_class
        )

    results = {}
    best_candidate_name = None
    best_f1_score = -1.0
    best_model_obj = None

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    for name, item in candidates.items():
        logger.info(f"Training and evaluating candidate: {name}...")
        is_xgb = name == "XGBoost"
        
        if is_xgb:
            model_inst, c2i, i2c = item
            # Fit
            model_inst.fit(X_train_trans, y_train_num)
            # Evaluate CV
            cv_scores = cross_val_score(model_inst, X_train_trans, y_train_num, cv=cv, scoring="f1_macro", n_jobs=-1)
            # Test predictions
            y_pred_num = model_inst.predict(X_test_trans)
            y_pred = np.array([i2c[idx] for idx in y_pred_num])
            model_to_save = model_inst
        else:
            model_inst = item
            model_inst.fit(X_train_trans, y_train)
            cv_scores = cross_val_score(model_inst, X_train_trans, y_train, cv=cv, scoring="f1_macro", n_jobs=-1)
            y_pred = model_inst.predict(X_test_trans)
            model_to_save = model_inst

        metrics = evaluate_classifier(y_test, y_pred, classes=classes)
        metrics["cv_f1_macro_mean"] = round(float(np.mean(cv_scores)), 4)
        metrics["cv_f1_macro_std"] = round(float(np.std(cv_scores)), 4)
        metrics["trained_at"] = datetime.utcnow().isoformat()

        logger.info(
            f"Candidate {name} -> Test Acc: {metrics['accuracy']:.4f}, "
            f"F1 Macro: {metrics['f1_macro']:.4f}, CV F1: {metrics['cv_f1_macro_mean']:.4f}"
        )

        results[name] = {
            "metrics": metrics,
            "model_obj": model_to_save,
        }

        # Select highest macro F1
        if metrics["f1_macro"] > best_f1_score:
            best_f1_score = metrics["f1_macro"]
            best_candidate_name = name
            best_model_obj = model_to_save

    logger.info(f"Selection Result: Best model is '{best_candidate_name}' with F1 Macro = {best_f1_score:.4f}")

    # Check minimum threshold
    if best_f1_score < 0.60:
        raise RuntimeError(f"Best model candidate {best_candidate_name} failed minimum validation threshold (F1 < 0.60).")

    # Persist artifacts
    version_dir = output_dir / "recommendation" / version
    version_dir.mkdir(parents=True, exist_ok=True)
    prod_dir = output_dir / "production"
    prod_dir.mkdir(parents=True, exist_ok=True)

    model_file = version_dir / "model.joblib"
    prep_file = version_dir / "preprocessor.joblib"
    meta_file = version_dir / "metadata.json"

    prod_model_file = prod_dir / "recommendation_model.joblib"
    prod_prep_file = prod_dir / "recommendation_preprocessor.joblib"

    # Save versioned artifacts
    joblib.dump(best_model_obj, model_file)
    joblib.dump(preprocessor, prep_file)

    # Save production copies
    joblib.dump(best_model_obj, prod_model_file)
    joblib.dump(preprocessor, prod_prep_file)

    selected_metrics = results[best_candidate_name]["metrics"]
    metadata = {
        "model_name": "recommendation_model",
        "version": version,
        "algorithm": best_candidate_name,
        "metrics": selected_metrics,
        "all_candidate_metrics": {k: v["metrics"] for k, v in results.items()},
        "features": ALL_FEATURES,
        "target": target_col,
        "classes": list(classes),
        "baseline_stats": baseline_stats,
        "dataset_version": "synthetic_v1.0",
        "dataset_samples": len(df),
        "artifact_path": str(model_file),
        "preprocessor_path": str(prep_file),
        "status": "production" if set_as_active else "candidate",
        "trained_at": selected_metrics["trained_at"],
    }

    with open(meta_file, "w") as f:
        json.dump(metadata, f, indent=2)

    # Save metadata in production dir too
    with open(prod_dir / "recommendation_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    # Register in ModelRegistry
    registry = ModelRegistry(registry_file=registry_file, model_dir=prod_dir)
    registry.register_model(
        model_name="recommendation_model",
        version=version,
        algorithm=best_candidate_name,
        metrics=selected_metrics,
        features=ALL_FEATURES,
        artifact_path=str(model_file),
        preprocessor_path=str(prep_file),
        baseline_stats=baseline_stats,
        set_as_active=set_as_active,
    )

    logger.info("Recommendation model training and registration complete!")
    return metadata
