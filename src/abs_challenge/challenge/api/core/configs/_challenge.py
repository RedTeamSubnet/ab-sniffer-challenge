from typing import Any, Dict, List

from pydantic import Field, SecretStr, BaseModel, AnyHttpUrl
from pydantic_settings import SettingsConfigDict

from api.core.constants import ENV_PREFIX_CHALLENGE
from ._base import FrozenBaseConfig


class FrameworkImageConfig(BaseModel):
    name: str = Field(...)
    image: str = Field(...)


class VerificationConfig(FrozenBaseConfig):
    api_key: SecretStr = Field(..., min_length=12, max_length=128)
    endpoint: AnyHttpUrl = Field(...)
    startup_url: AnyHttpUrl = Field(...)
    extra: dict = Field(default_factory=dict)

    model_config = SettingsConfigDict(env_prefix=f"{ENV_PREFIX_CHALLENGE}VERIFICATION_")


class BotRunnerConfig(FrozenBaseConfig):
    url: AnyHttpUrl = Field(...)
    api_key: SecretStr = Field(..., min_length=12, max_length=128)
    public_base_url: AnyHttpUrl = Field(...)
    device_type: str = Field(default="linux", min_length=1, max_length=32)
    bot: str = Field(default="aad-detect", min_length=1, max_length=128)
    poll_timeout_sec: int = Field(default=180, ge=1)
    poll_interval_sec: int = Field(default=2, ge=1)
    request_timeout_sec: int = Field(default=15, ge=1)
    busy_retry_count: int = Field(default=3, ge=0, le=10)
    busy_backoff_initial_sec: float = Field(default=0.5, ge=0.0)
    busy_backoff_max_sec: float = Field(default=5.0, ge=0.0)
    framework_presets: Dict[str, str] = Field(default_factory=dict)

    model_config = SettingsConfigDict(env_prefix=f"{ENV_PREFIX_CHALLENGE}BOT_RUNNER_")


class ChallengeConfig(FrozenBaseConfig):
    api_key: SecretStr = Field(..., min_length=12, max_length=128)
    docker_ulimit: int = Field(...)
    verification: VerificationConfig = Field(...)
    bot_timeout: int = Field(..., ge=1)
    repeated_framework_count: int = Field(..., ge=1)
    framework_images: List[FrameworkImageConfig] = Field(...)
    bot_runner: BotRunnerConfig = Field(...)

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX_CHALLENGE, env_nested_delimiter="__"
    )


__all__ = [
    "FrameworkImageConfig",
    "ChallengeConfig",
    "VerificationConfig",
    "BotRunnerConfig",
]
