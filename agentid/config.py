from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://agentid:agentid@localhost:5432/agentid"
    secret_key: str = "change-me-in-production"
    api_key_prefix: str = "aid_key_"
    score_recalc_interval_minutes: int = 60
    replay_window_seconds: int = 300  # 5 min replay protection
    rate_limit_per_hour: int = 1000
    global_score_mean: float = 6.5    # updated weekly by worker
    peer_rating_min_votes: int = 10
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"  # comma-separated

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        import os
        if os.getenv("AGENTWORKER_ENV") == "production" and v == "change-me-in-production":
            raise ValueError(
                "SECRET_KEY cannot be the default placeholder in production. "
                "Set a strong unique value in your environment."
            )
        return v

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
