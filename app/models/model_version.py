import json
from datetime import datetime
from app.extensions import db


class ModelVersion(db.Model):
    """Registry table tracking trained ML model versions, architectures, and metrics."""
    __tablename__ = "model_versions"

    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(60), nullable=False, index=True)
    version = db.Column(db.String(30), nullable=False)
    algorithm = db.Column(db.String(60), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="candidate")  # production, candidate, archived, failed
    
    metrics_json = db.Column(db.Text, nullable=False, default="{}")
    feature_schema_json = db.Column(db.Text, nullable=False, default="[]")
    
    training_date = db.Column(db.DateTime, default=datetime.utcnow)
    dataset_version = db.Column(db.String(60), nullable=False, default="synthetic_v1.0")
    file_path = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    rollback_version = db.Column(db.String(30), nullable=True)

    def get_metrics(self) -> dict:
        try:
            return json.loads(self.metrics_json)
        except Exception:
            return {}

    def get_features(self) -> list:
        try:
            return json.loads(self.feature_schema_json)
        except Exception:
            return []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "model_name": self.model_name,
            "version": self.version,
            "algorithm": self.algorithm,
            "status": self.status,
            "metrics": self.get_metrics(),
            "features": self.get_features(),
            "training_date": self.training_date.isoformat() if self.training_date else None,
            "dataset_version": self.dataset_version,
            "file_path": self.file_path,
            "is_active": self.is_active,
            "rollback_version": self.rollback_version,
        }
