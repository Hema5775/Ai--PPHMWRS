import math
from typing import Dict, Any, List, Tuple
from pydantic import ValidationError


def format_pydantic_errors(err: ValidationError) -> List[Dict[str, Any]]:
    """Format Pydantic validation errors into clean, user-friendly error dictionaries."""
    formatted = []
    for error in err.errors():
        field = " -> ".join([str(loc) for loc in error.get("loc", [])])
        msg = error.get("msg", "Invalid value")
        formatted.append({
            "field": field,
            "message": msg,
            "type": error.get("type", "validation_error")
        })
    return formatted


def validate_feature_vector(features: Dict[str, Any], required_keys: List[str]) -> Tuple[bool, str]:
    """Validate that an ML feature vector has all required keys and no NaN/Inf values."""
    for key in required_keys:
        if key not in features:
            return False, f"Missing required feature: '{key}'"
        val = features[key]
        if isinstance(val, (int, float)):
            if math.isnan(val) or math.isinf(val):
                return False, f"Feature '{key}' contains NaN or infinite value: {val}"
    return True, "Valid"
