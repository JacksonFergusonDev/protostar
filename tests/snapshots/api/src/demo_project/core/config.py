"""Configuration settings for demo-project."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings schema."""

    model_config = SettingsConfigDict(env_file=".env")

    project_name: str = "demo-project"
    api_v1_str: str = "/api/v1"


settings = Settings()
