from pathlib import Path

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from docket import domain

DATA_DIR_MESSAGE = "DOCKET_DATA_DIR must be an absolute path"
TIME_ZONE_MESSAGE = "DOCKET_TIME_ZONE must be a time zone name"
TIME_ZONE_UNSET_MESSAGE = "DOCKET_TIME_ZONE is not set"
WORK_MINUTES_MESSAGE = "DOCKET_WORK_MINUTES must be 5 to 720"
WEB_PORT_MESSAGE = "DOCKET_WEB_PORT must be 1024 to 65535"
SETTINGS_MESSAGE = "Invalid docket settings."

_FIELD_MESSAGES = (
    ("data_dir", DATA_DIR_MESSAGE),
    ("time_zone", TIME_ZONE_MESSAGE),
    ("work_minutes", WORK_MINUTES_MESSAGE),
    ("web_port", WEB_PORT_MESSAGE),
)


class ConfigError(Exception):
    pass


def _default_data_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "docket"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOCKET_")

    data_dir: Path = Field(default_factory=_default_data_dir)
    time_zone: str | None = None
    work_minutes: int = Field(default=60, ge=domain.WORK_MINUTES_MIN, le=domain.WORK_MINUTES_MAX)
    web_port: int = Field(default=8767, ge=1024, le=65535)

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
        if value is not None and value not in domain.zone_names():
            raise ValueError(TIME_ZONE_MESSAGE)
        return value


def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as error:
        found = [item["loc"][0] for item in error.errors() if item["loc"]]
        for field, message in _FIELD_MESSAGES:
            if field in found:
                raise ConfigError(message) from None
        raise ConfigError(SETTINGS_MESSAGE) from None


def home_zone(settings: Settings) -> str:
    if settings.time_zone is None:
        raise ConfigError(TIME_ZONE_UNSET_MESSAGE)
    return settings.time_zone


def prepare_data_dir(settings: Settings) -> Path:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.data_dir.chmod(0o700)
    return settings.data_dir
