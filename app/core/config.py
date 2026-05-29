from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "SokoFlow"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "change-me"

    # Database
    database_url: str = ""

    # Redis
    redis_url: str = ""
    celery_broker_url: str = ""
    celery_result_backend: str = ""

    # Messaging
    sender_backend: str = "mock"

    # WhatsApp
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""

    # Session
    session_ttl_seconds: int = 1800
    dedup_ttl_seconds: int = 60
    max_fsm_errors: int = 3

    # Logging
    log_level: str = "INFO"


# Singleton
settings = Settings()
