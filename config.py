import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # --------------------------------------------------
    # Core
    # --------------------------------------------------
    SECRET_KEY = os.environ.get("SECRET_KEY", "a-very-secret-key")
    MONGO_URI = os.environ.get(
        "MONGO_URI", "mongodb://127.0.0.1:27017/recruitmentDB"
    )

    # --------------------------------------------------
    # Email Configuration (GMAIL SMTP – FINAL)
    # --------------------------------------------------
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))

    # 🔴 Gmail REQUIRES this
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "1") == "1"
    MAIL_USE_SSL = False

    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")

    # MUST NOT BE NONE
    MAIL_DEFAULT_SENDER = (
        os.environ.get("MAIL_DEFAULT_SENDER_NAME", "Recruitment Team"),
        os.environ.get("MAIL_DEFAULT_SENDER_EMAIL", MAIL_USERNAME),
    )

    # --------------------------------------------------
    # Celery
    # --------------------------------------------------
    CELERY_BROKER_URL = os.environ.get(
        "CELERY_BROKER_URL", "redis://127.0.0.1:6379/0"
    )
    CELERY_RESULT_BACKEND = os.environ.get(
        "CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/0"
    )
    
    # Force Celery to bypass Redis/RabbitMQ and execute tasks immediately on the main thread
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

    # --------------------------------------------------
    # Feature Flags
    # --------------------------------------------------
    ENABLED_FEATURES = [
        "RECRUITMENT_DASHBOARD",
        "ONBOARDING_PORTAL",
    ]

    # --------------------------------------------------
    # Flask
    # --------------------------------------------------
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
