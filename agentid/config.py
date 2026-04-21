from pydantic_settings import BaseSettings, SettingsConfigDict


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


settings = Settings()
