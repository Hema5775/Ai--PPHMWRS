"""
ML Contract and Inference Tests (Section 43).
"""

from pathlib import Path
import numpy as np
from app.ml.feature_engineering import ALL_FEATURES
from app.ml.model_registry import ModelRegistry
from app.ml.model_health import ModelHealthMonitor


def test_ml_contract_schema_and_prediction(app):
    reg_path = Path("models/model_registry.json")
    prod_dir = Path("models/production")
    registry = ModelRegistry(registry_file=reg_path, model_dir=prod_dir)

    loaded = registry.load_active_model_and_preprocessor("recommendation_model")
    model = loaded.get("model")
    preprocessor = loaded.get("preprocessor")
    meta = registry.get_active_model_meta("recommendation_model")

    assert model is not None, "Active ML model must be loadable"
    assert preprocessor is not None, "Preprocessing pipeline must be loadable"

    # Contract 1: Schema Match
    assert set(meta.get("features", [])) == set(ALL_FEATURES)

    # Contract 2: Valid Benchmark Sample Inference
    sample = ModelHealthMonitor.get_test_benchmark_sample()
    X_trans = preprocessor.transform(sample)

    pred = model.predict(X_trans)
    assert pred is not None
    assert len(pred) == 1

    label = str(pred[0])
    assert label in ModelHealthMonitor.VALID_RECOMMENDATION_CLASSES

    # Contract 3: Probabilities & Confidence
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(X_trans)
        assert not np.any(np.isnan(proba))
        assert not np.any(np.isinf(proba))
        conf = float(np.max(proba[0]))
        assert 0.0 <= conf <= 1.0
