from datetime import date
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Admin connection (superuser): migrations, seeding, RLS setup. Superusers BYPASS RLS.
    database_url: str = "postgresql+psycopg://shiftpilot:shiftpilot@localhost:5433/shiftpilot"
    # Runtime connection as the non-superuser app role, so RLS actually applies.
    app_database_url: str = "postgresql+psycopg://shiftpilot_app:shiftpilot_app@localhost:5433/shiftpilot"
    app_db_password: str = "shiftpilot_app"
    # The optimization worker's least-privilege role (migration 0015). Unset: the worker falls back to
    # database_url, which is fine for local development only.
    worker_database_url: str | None = None
    worker_db_password: str = "shiftpilot_worker"
    redis_url: str = "redis://localhost:6380/0"

    jwt_secret: str = "change-me-in-.env"
    jwt_ttl_minutes: int = 240

    # v2 public demo: POST /v2/session/demo issues tokens for the synthetic demo org's personas.
    # Must be false on any deployment holding real (imported) data.
    demo_sessions_enabled: bool = False
    demo_org_key: str = "spice-route"
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"
    )

    # Model routing (LiteLLM model strings)
    router_model: str = "anthropic/claude-haiku-5-5"
    main_model: str = "anthropic/claude-sonnet-5-5"
    fallback_model: str = "gemini/gemini-2.5-flash"
    judge_model: str = "openai/gpt-4.1"
    embedding_model: str = "openai/text-embedding-3-small"

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # MCP stdio (Claude Desktop) has no HTTP auth: act as this demo user (phone number).
    mcp_demo_user_phone: str = "+919800000002"

    # The sandbox data ends on Sun 2026-10-11; pin "today" so "this week" means the seeded week.
    # Set DEMO_TODAY= (empty) in .env to use the real date with your own data.
    demo_today: date | None = date(2026, 10, 11)
    usd_inr: float = 88.0
    max_agent_steps: int = 8

    def today(self) -> date:
        return self.demo_today or date.today()


@lru_cache
def settings() -> Settings:
    return Settings()
