import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base configuration class."""
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-insecure-key-change-me")
    FLASK_ENV = os.getenv("FLASK_ENV", "production")
    DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

    # Base paths
    BASE_DIR = BASE_DIR
    DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data")
    MODEL_DIR = BASE_DIR / os.getenv("MODEL_DIR", "models/production")
    REGISTRY_PATH = BASE_DIR / os.getenv("REGISTRY_PATH", "models/model_registry.json")
    LOG_DIR = BASE_DIR / "logs"

    # Database (PostgreSQL / Supabase agnostic + SQLite instance support)
    _raw_db_url = os.getenv("DATABASE_URL")
    if _raw_db_url and _raw_db_url != "sqlite:///wellness.db":
        if _raw_db_url.startswith("postgres://"):
            _raw_db_url = _raw_db_url.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = _raw_db_url
    else:
        instance_db = BASE_DIR / "instance" / "wellness.db"
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{instance_db.as_posix()}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,
        "pool_pre_ping": True,
    }

    # Google Authentication
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
    GOOGLE_OAUTH_CONFIGURED = bool(os.getenv("GOOGLE_CLIENT_ID", "").strip() and os.getenv("GOOGLE_CLIENT_SECRET", "").strip())

    # Apple Authentication (Sign in with Apple)
    APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID", "").strip()
    APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID", "").strip()
    APPLE_KEY_ID = os.getenv("APPLE_KEY_ID", "").strip()
    APPLE_PRIVATE_KEY = os.getenv("APPLE_PRIVATE_KEY", "").strip()
    APPLE_REDIRECT_URI = os.getenv("APPLE_REDIRECT_URI", "").strip()
    APPLE_OAUTH_CONFIGURED = bool(
        os.getenv("APPLE_CLIENT_ID", "").strip()
        and os.getenv("APPLE_TEAM_ID", "").strip()
        and os.getenv("APPLE_KEY_ID", "").strip()
        and os.getenv("APPLE_PRIVATE_KEY", "").strip()
    )

    # Phone & SMS / OTP Authentication
    SMS_PROVIDER = os.getenv("SMS_PROVIDER", "mock").lower().strip()
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "").strip()
    TWILIO_CONFIGURED = bool(
        os.getenv("TWILIO_ACCOUNT_SID", "").strip()
        and os.getenv("TWILIO_AUTH_TOKEN", "").strip()
        and os.getenv("TWILIO_PHONE_NUMBER", "").strip()
    )

    # Session & Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # Set to True when HTTPS is enabled in production
    PERMANENT_SESSION_LIFETIME = 86400 * 7  # 7 days

    # Wellness Score Component Weights
    WEIGHT_ACTIVITY = float(os.getenv("WEIGHT_ACTIVITY", "0.25"))
    WEIGHT_HYDRATION = float(os.getenv("WEIGHT_HYDRATION", "0.20"))
    WEIGHT_SLEEP = float(os.getenv("WEIGHT_SLEEP", "0.20"))
    WEIGHT_TASKS = float(os.getenv("WEIGHT_TASKS", "0.20"))
    WEIGHT_CONSISTENCY = float(os.getenv("WEIGHT_CONSISTENCY", "0.15"))

    # Anomaly Detection
    ENABLE_ANOMALY_DETECTION = os.getenv("ENABLE_ANOMALY_DETECTION", "True").lower() in ("true", "1")

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key-12345"
    MODEL_DIR = BASE_DIR / "models" / "test_production"


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
