from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")

    BOT_TOKEN: str = Field(default="0000000000:AAFakeTokenForDevelopmentAndTesting000")
    BOT_USERNAME: str = Field(default="AcademicPlatformBot")
    TELEGRAM_API_URL: str = Field(default="")
    BOT_API_POOL_LIMIT: int = Field(default=500, ge=10, le=2000)
    ADMIN_TELEGRAM_IDS: list[int] | str = Field(default_factory=lambda: [123456789])

    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5434)
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="")
    POSTGRES_DB: str = Field(default="academic")
    POSTGRES_SCHEMA: str = Field(default="student_platform")
    POSTGRES_SSLMODE: str = Field(default="disable")
    DATABASE_URL: str = Field(default="postgresql+asyncpg://postgres@localhost:5434/academic")
    DB_POOL_SIZE: int = Field(default=30, ge=1, le=80)
    DB_MAX_OVERFLOW: int = Field(default=40, ge=0, le=80)
    DB_POOL_TIMEOUT: float = Field(default=15.0, gt=0, le=120)
    DB_POOL_RECYCLE: int = Field(default=1800, ge=60, le=86400)
    DB_POOL_PRE_PING: bool = Field(default=False)

    REDIS_ENABLED: bool = Field(default=False)
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_PASSWORD: str = Field(default="")
    CELERY_BROKER_DB: int = Field(default=0, ge=0, le=15)
    CELERY_RESULT_DB: int = Field(default=1, ge=0, le=15)
    CELERY_TASK_ALWAYS_EAGER: bool = Field(default=False)

    TASK_WORKER_ENABLED: bool = Field(default=True)
    TASK_WORKER_POLL_INTERVAL: float = Field(default=2.0)
    BOT_POLLING_ENABLED: bool = Field(default=True)

    @field_validator("ADMIN_TELEGRAM_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: str | list[int] | int) -> list[int]:
        if isinstance(v, list):
            return [int(x) for x in v]
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            clean = v.strip().strip("[]")
            if not clean:
                return []
            return [int(x.strip()) for x in clean.split(",") if x.strip()]
        return []

    def get_asyncpg_database_url(self) -> str:
        if self.DATABASE_URL and self.DATABASE_URL.startswith("postgresql+asyncpg://"):
            return self.DATABASE_URL
        password_part = f":{self.POSTGRES_PASSWORD}" if self.POSTGRES_PASSWORD else ""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}{password_part}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    def validate_for_production(self) -> None:
        """Reject unsafe defaults before a production process starts."""
        if self.APP_ENV.lower() not in {"production", "prod"}:
            return
        if not self.BOT_TOKEN or self.BOT_TOKEN.startswith(("0000000000:", "your_", "test_")):
            raise ValueError("BOT_TOKEN must be a real Telegram bot token in production")
        if not self.DATABASE_URL.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must be a PostgreSQL asyncpg URL in production")
        if self.POSTGRES_SSLMODE == "disable":
            raise ValueError("POSTGRES_SSLMODE must not be disable in production")
        if not self.DB_POOL_PRE_PING:
            raise ValueError("DB_POOL_PRE_PING must be enabled in production")


settings = Settings()
