from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://opsgpt_user:opsgpt_password@opsgpt-db:5432/opsgpt_db"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    internal_api_key: str = "change-me-internal-key"
    notification_service_url: str = "http://notification-service:8004"
    enable_notifications: bool = True
    app_env: str = "development"
    cors_origins: str = "*"
    db_init_max_attempts: int = 30
    db_init_delay_seconds: int = 2

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
