from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from urllib.parse import urlparse


class Settings(BaseSettings):
    PROJECT_NAME: str = "FlowForge AI Core"
    VERSION: str = "0.2.0"
    ENVIRONMENT: str = "development"

    # PostgreSQL Connection parameters
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "flowforge"
    POSTGRES_USER: str = "flowforge_app"
    POSTGRES_PASSWORD: str = ""
    DATABASE_URL: Optional[str] = None

    # Test failure simulation hook (disabled by default)
    ENABLE_FAILURE_SIMULATION: bool = False

    # Advisory-only local inference. No cloud model or public endpoint is allowed.
    ENRICHMENT_ENABLED: bool = True
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b-instruct"
    OLLAMA_MODEL_DIGEST: str = "357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b"
    OLLAMA_TIMEOUT_SECONDS: float = Field(default=25.0, ge=1, le=30)
    OLLAMA_NUM_GPU: int = Field(default=-1, ge=-1, le=128)
    ENRICHMENT_MAX_INPUT_CHARS: int = Field(default=3000, ge=1, le=5200)

    @field_validator("OLLAMA_BASE_URL")
    @classmethod
    def local_endpoint_only(cls, value):
        parsed = urlparse(value)
        if (parsed.scheme != "http" or parsed.hostname not in {
            "localhost", "127.0.0.1", "::1", "host.docker.internal", "ollama"
        } or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ("", "/")):
            raise ValueError("Ollama endpoint must be a trusted local HTTP address")
        return value.rstrip("/")

    @field_validator("OLLAMA_MODEL")
    @classmethod
    def local_model_only(cls, value):
        import re
        if not re.fullmatch(r"[A-Za-z0-9._-]+:[A-Za-z0-9._-]+", value) or "cloud" in value.lower():
            raise ValueError("A local tagged model is required")
        return value

    @field_validator("OLLAMA_MODEL_DIGEST")
    @classmethod
    def pinned_model(cls, value):
        import re
        if not re.fullmatch(r"[a-f0-9]{64}", value):
            raise ValueError("Model digest must be a complete SHA-256 identifier")
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sync_database_url(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+psycopg://", 1)
            return url
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
