from pathlib import Path
from zoneinfo import available_timezones

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DATA_DIR_MESSAGE = "DOCKET_DATA_DIR must be an absolute path"
TIME_ZONE_MESSAGE = "DOCKET_TIME_ZONE must be a time zone name"
TIME_ZONE_UNSET_MESSAGE = "DOCKET_TIME_ZONE is not set"
WORK_MINUTES_MESSAGE = "DOCKET_WORK_MINUTES must be 5 to 720"


class ConfigError(Exception):
    pass


def _default_data_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "docket"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOCKET_")

    data_dir: Path = Field(default_factory=_default_data_dir)
    time_zone: str | None = None
    work_minutes: int = Field(default=60, ge=5, le=720)

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

    @field_validator("time_zone", mode="before")
    @classmethod
    def _empty_zone_is_unset(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("time_zone")
    @classmethod
    def _known_zone(cls, value: str | None) -> str | None:
        if value is not None and value not in available_timezones():
            raise ValueError(TIME_ZONE_MESSAGE)
        return value


def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as error:
        failed = {item["loc"][0] for item in error.errors()}
        if "data_dir" in failed:
            raise ConfigError(DATA_DIR_MESSAGE) from None
        if "time_zone" in failed:
            raise ConfigError(TIME_ZONE_MESSAGE) from None
        raise ConfigError(WORK_MINUTES_MESSAGE) from None


def home_zone(settings: Settings) -> str:
    if settings.time_zone is None:
        raise ConfigError(TIME_ZONE_UNSET_MESSAGE)
    return settings.time_zone


def prepare_data_dir(settings: Settings) -> Path:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.data_dir.chmod(0o700)
    return settings.data_dir
