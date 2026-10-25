from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application Environment
    APP_ENV: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")

    # Telegram Bot
    BOT_TOKEN: str = Field(default="0000000000:AAFakeTokenForDevelopmentAndTesting000")
    BOT_USERNAME: str = Field(default="AcademicPlatformBot")
    ADMIN_TELEGRAM_IDS: Union[List[int], str] = Field(default_factory=lambda: [123456789])

    # Database Configuration
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5434)
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="")
    POSTGRES_DB: str = Field(default="academic")
    POSTGRES_SCHEMA: str = Field(default="student_platform")
    POSTGRES_SSLMODE: str = Field(default="disable")
    DATABASE_URL: str = Field(default="postgresql+asyncpg://postgres@localhost:5434/academic")

    # Redis (Optional)
    REDIS_ENABLED: bool = Field(default=False)
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_PASSWORD: str = Field(default="")

    # Task Worker & Background Processing
    TASK_WORKER_ENABLED: bool = Field(default=True)
    TASK_WORKER_POLL_INTERVAL: float = Field(default=2.0)

    @field_validator("ADMIN_TELEGRAM_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Union[str, List[int], int]) -> List[int]:
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
        """Returns the formatted asyncpg database URL."""
        if self.DATABASE_URL and self.DATABASE_URL.startswith("postgresql+asyncpg://"):
            return self.DATABASE_URL
        password_part = f":{self.POSTGRES_PASSWORD}" if self.POSTGRES_PASSWORD else ""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}{password_part}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
