"""
Preprocessing Pipeline using scikit-learn ColumnTransformer.
Ensures standardized normalization for numerical features and one-hot encoding for categorical variables.
"""

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from app.ml.feature_engineering import NUMERICAL_FEATURES, CATEGORICAL_FEATURES


def build_preprocessor() -> ColumnTransformer:
    """Create a ColumnTransformer preprocessor handling numerical and categorical features."""
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "num",
                StandardScaler(),
                NUMERICAL_FEATURES,
            ),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
    )
    return preprocessor
