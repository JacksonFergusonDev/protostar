"""Configuration settings for demo-project."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings schema."""

    project_name: str = "demo-project"
    api_v1_str: str = "/api/v1"

    class Config:
        """Pydantic model configuration."""

        env_file = ".env"


settings = Settings()
