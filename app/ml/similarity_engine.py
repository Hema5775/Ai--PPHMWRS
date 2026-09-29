"""
Model E — Personalization and Similarity Engine.
Uses NearestNeighbors with cosine similarity on standardized behavioral vectors
to identify similar profile clusters and personalize recommendation templates.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import pandas as pd
import joblib
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wellness.ml.similarity")

SIMILARITY_NUMERICAL = ["age", "bmi", "avg_daily_steps", "avg_sleep_duration", "avg_water_intake"]
SIMILARITY_CATEGORICAL = ["gender", "activity_level", "dietary_preference", "health_goal"]


def train_similarity_engine(
    data_path: Path,
    output_dir: Path,
    version: str = "v1.0.0"
) -> Dict[str, Any]:
    """Fit NearestNeighbors similarity index on the synthetic cohort dataset."""
    logger.info(f"Training similarity index from {data_path}...")
    df = pd.read_csv(data_path)

    # Sample representative 5,000 reference cohort records for fast similarity lookup
    cohort = df.sample(n=min(5000, len(df)), random_state=42).reset_index(drop=True)

    transformer = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), SIMILARITY_NUMERICAL),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), SIMILARITY_CATEGORICAL),
        ]
    )

    X_cohort = transformer.fit_transform(cohort[SIMILARITY_NUMERICAL + SIMILARITY_CATEGORICAL])

    nn = NearestNeighbors(n_neighbors=5, metric="cosine", algorithm="brute")
    nn.fit(X_cohort)

    version_dir = output_dir / "similarity" / version
    version_dir.mkdir(parents=True, exist_ok=True)
    prod_dir = output_dir / "production"
    prod_dir.mkdir(parents=True, exist_ok=True)

    artifact = {
        "nn": nn,
        "transformer": transformer,
        "cohort_data": cohort[["bmi", "health_goal", "dietary_preference", "recommendation_category"]].to_dict(orient="records"),
    }

    joblib.dump(artifact, version_dir / "similarity_engine.joblib")
    joblib.dump(artifact, prod_dir / "similarity_engine.joblib")

    meta = {
        "model_name": "similarity_engine",
        "version": version,
        "algorithm": "NearestNeighbors (Cosine)",
        "cohort_size": len(cohort),
        "status": "production",
    }

    with open(version_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)
    with open(prod_dir / "similarity_metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    logger.info("Similarity engine successfully trained and registered.")
    return meta
