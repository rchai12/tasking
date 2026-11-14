from pathlib import Path

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DATA_DIR_MESSAGE = "DOCKET_DATA_DIR must be an absolute path"


class ConfigError(Exception):
    pass


def _default_data_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "docket"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOCKET_")

    data_dir: Path = Field(default_factory=_default_data_dir)

    @field_validator("data_dir", mode="before")
    @classmethod
    def _expand_home(cls, value: str) -> Path:
        return Path(value).expanduser()

    @field_validator("data_dir")
    @classmethod
    def _require_absolute(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError(DATA_DIR_MESSAGE)
        return value


def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError:
        raise ConfigError(DATA_DIR_MESSAGE) from None


def prepare_data_dir(settings: Settings) -> Path:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.data_dir.chmod(0o700)
    return settings.data_dir
