"""
Model Registry and Cache Manager.
Manages metadata, versioning, deployment, rollback, and in-memory caching of ML artifacts.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import joblib

logger = logging.getLogger("wellness.ml.registry")


class ModelRegistry:
    """Manages versioned ML artifacts and metadata tracking."""

    def __init__(self, registry_file: Path, model_dir: Path):
        self.registry_file = Path(registry_file)
        self.model_dir = Path(model_dir)
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Any] = {}

    def _load_registry_data(self) -> Dict[str, Any]:
        if not self.registry_file.exists():
            default_data = {
                "active_models": {},
                "model_history": [],
            }
            self._save_registry_data(default_data)
            return default_data

        try:
            with open(self.registry_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading model registry from {self.registry_file}: {e}")
            return {"active_models": {}, "model_history": []}

    def _save_registry_data(self, data: Dict[str, Any]) -> None:
        try:
            with open(self.registry_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving model registry to {self.registry_file}: {e}")

    def register_model(
        self,
        model_name: str,
        version: str,
        algorithm: str,
        metrics: Dict[str, Any],
        features: List[str],
        artifact_path: str,
        preprocessor_path: Optional[str] = None,
        baseline_stats: Optional[Dict[str, Any]] = None,
        set_as_active: bool = False,
    ) -> Dict[str, Any]:
        """Register a newly trained model version."""
        data = self._load_registry_data()
        
        entry = {
            "model_name": model_name,
            "version": version,
            "algorithm": algorithm,
            "metrics": metrics,
            "features": features,
            "artifact_path": str(artifact_path),
            "preprocessor_path": str(preprocessor_path) if preprocessor_path else None,
            "baseline_stats": baseline_stats or {},
            "registered_at": json.dumps(metrics.get("trained_at", "")).strip('"'),
            "status": "production" if set_as_active else "candidate",
        }

        # Check if version already exists
        data["model_history"] = [
            m for m in data.get("model_history", [])
            if not (m["model_name"] == model_name and m["version"] == version)
        ]
        data["model_history"].append(entry)

        if set_as_active:
            prev_active = data["active_models"].get(model_name)
            if prev_active and prev_active.get("version") != version:
                entry["rollback_version"] = prev_active.get("version")
            data["active_models"][model_name] = entry
            self.invalidate_cache(model_name)

        self._save_registry_data(data)
        logger.info(f"Registered model {model_name} version {version} (active={set_as_active})")
        return entry

    def get_active_model_meta(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for the currently active production model."""
        data = self._load_registry_data()
        return data.get("active_models", {}).get(model_name)

    def get_all_models(self) -> List[Dict[str, Any]]:
        data = self._load_registry_data()
        return data.get("model_history", [])

    def load_active_model_and_preprocessor(self, model_name: str) -> Dict[str, Any]:
        """
        Load active model artifact and preprocessor with caching.
        Returns dict containing: 'model', 'preprocessor', 'meta', 'status'.
        """
        if model_name in self._cache:
            return self._cache[model_name]

        meta = self.get_active_model_meta(model_name)
        if not meta:
            # Check if there is a default fallback in production folder
            prod_model_path = self.model_dir / f"{model_name}.joblib"
            prod_prep_path = self.model_dir / f"{model_name}_preprocessor.joblib"
            if prod_model_path.exists():
                try:
                    m = joblib.load(prod_model_path)
                    p = joblib.load(prod_prep_path) if prod_prep_path.exists() else None
                    result = {
                        "model": m,
                        "preprocessor": p,
                        "meta": {
                            "model_name": model_name,
                            "version": "prod-default",
                            "algorithm": m.__class__.__name__,
                            "status": "production",
                        },
                        "status": "HEALTHY",
                    }
                    self._cache[model_name] = result
                    return result
                except Exception as e:
                    logger.error(f"Failed loading production model artifact: {e}")
                    return {"model": None, "preprocessor": None, "meta": None, "status": "FAILED", "error": str(e)}

            return {"model": None, "preprocessor": None, "meta": None, "status": "FAILED", "error": "No active model registered"}

        model_path = Path(meta["artifact_path"])
        prep_path = Path(meta["preprocessor_path"]) if meta.get("preprocessor_path") else None

        if not model_path.exists():
            return {"model": None, "preprocessor": None, "meta": meta, "status": "FAILED", "error": f"Model file not found: {model_path}"}

        try:
            loaded_model = joblib.load(model_path)
            loaded_prep = joblib.load(prep_path) if (prep_path and prep_path.exists()) else None

            result = {
                "model": loaded_model,
                "preprocessor": loaded_prep,
                "meta": meta,
                "status": "HEALTHY",
            }
            self._cache[model_name] = result
            return result
        except Exception as e:
            logger.error(f"Failed loading model artifacts for {model_name}: {e}")
            return {"model": None, "preprocessor": None, "meta": meta, "status": "FAILED", "error": str(e)}

    def rollback(self, model_name: str) -> Dict[str, Any]:
        """Rollback active model to its previous known-good version."""
        data = self._load_registry_data()
        active = data.get("active_models", {}).get(model_name)
        if not active:
            return {"success": False, "message": f"No active model found for {model_name}"}

        rollback_ver = active.get("rollback_version")
        if not rollback_ver:
            # Look for the latest prior candidate/production model in history
            candidates = [
                m for m in data.get("model_history", [])
                if m["model_name"] == model_name and m["version"] != active["version"]
            ]
            if candidates:
                rollback_ver = candidates[-1]["version"]
            else:
                return {"success": False, "message": f"No previous model version available for rollback of {model_name}"}

        target = next(
            (m for m in data.get("model_history", []) if m["model_name"] == model_name and m["version"] == rollback_ver),
            None
        )
        if not target:
            return {"success": False, "message": f"Rollback target version {rollback_ver} not found in history"}

        target["status"] = "production"
        data["active_models"][model_name] = target
        self._save_registry_data(data)
        self.invalidate_cache(model_name)
        logger.info(f"Successfully rolled back {model_name} from {active['version']} to {rollback_ver}")
        return {"success": True, "message": f"Rolled back to version {rollback_ver}", "active_version": rollback_ver}

    def invalidate_cache(self, model_name: Optional[str] = None) -> None:
        if model_name:
            self._cache.pop(model_name, None)
        else:
            self._cache.clear()
