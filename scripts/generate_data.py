"""
CLI script to generate 50,000+ synthetic development records.
"""

from pathlib import Path
import sys

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.ml.data_generator import generate_synthetic_data

if __name__ == "__main__":
    out_file = BASE_DIR / "data" / "synthetic" / "synthetic_development_data.csv"
    print(f"Generating synthetic development dataset at: {out_file}")
    df = generate_synthetic_data(num_samples=50000, output_path=str(out_file))
    print(f"Success! Generated {len(df)} records.")
