"""
CLI script to train and select production models for Model A, Model D, and Model E.
"""

from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.ml.train_all import run_full_training_pipeline

if __name__ == "__main__":
    data_dir = BASE_DIR / "data"
    model_dir = BASE_DIR / "models"
    registry_file = model_dir / "model_registry.json"

    print("Executing complete ML training and model selection pipeline...")
    results = run_full_training_pipeline(
        data_dir=data_dir,
        model_dir=model_dir,
        registry_file=registry_file,
        num_samples=50000,
        force_data_gen=False,
    )
    print("\nTraining Pipeline Completed Successfully!")
    print(f"Active Algorithm: {results['recommendation']['algorithm']}")
    print(f"Validation F1 Macro: {results['recommendation']['metrics']['f1_macro']:.4f}")
    print(f"Validation Accuracy: {results['recommendation']['metrics']['accuracy']:.4f}")
