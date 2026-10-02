from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://agentwall:agentwall@localhost:5432/agentwall"
    redis_url: str = "redis://localhost:6379/0"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    session_ttl_seconds: int = 3600
    default_audit_log_level: str = "ARGS_ONLY"

    risk_auto_deny_threshold: int = 80

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
