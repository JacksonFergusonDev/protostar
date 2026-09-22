"""Configuration settings for demo_project."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings schema."""

    project_name: str = "demo_project"
    api_v1_str: str = "/api/v1"

    class Config:
        """Pydantic model configuration."""

        env_file = ".env"


settings = Settings()
