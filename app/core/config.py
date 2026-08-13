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
    secret_key: str
    correlation_id_header: str

    # Database
    database_url: str
    test_db_url: str | None = None

    # Redis
    redis_url: str
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    # Messaging
    sender_backend: str = "mock"

    # WhatsApp
    whatsapp_verify_token: str | None = None
    whatsapp_app_secret: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_access_token: str | None = None

    # Session
    session_ttl_seconds: int = 1800
    dedup_ttl_seconds: int = 60
    max_fsm_errors: int = 3
    product_match_threshold: float = 0.55
    confident_match_threshold: float = 0.75

    # Celery
    celery_task_max_retries: int | None = None
    celery_task_retry_backoff: int | None = None
    celery_task_retry_backoff_max: int | None = None
    report_tmp_dir: str | None = "/tmp/sokoflow_reports"

    # Logging
    log_level: str = "INFO"


# Singleton
settings = Settings()
