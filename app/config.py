from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
    )

    webhook_secret: SecretStr

    database_url: str
    database_echo: bool = False


settings = Settings()  # type: ignore[call-arg] # Loaded from .env file
