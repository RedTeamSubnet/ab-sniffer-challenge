from typing import List

from pydantic import Field, SecretStr, BaseModel, AnyHttpUrl, model_validator
from pydantic_settings import SettingsConfigDict

from api.core.constants import ENV_PREFIX_CHALLENGE
from ._base import FrozenBaseConfig


class FrameworkImageConfig(BaseModel):
    name: str = Field(...)
    image: str = Field(...)
    # bot-runner driver preset used to launch this framework.
    preset: str = Field(..., min_length=1)


class RunCountsConfig(BaseModel):
    """Per-framework launch counts for each browser mode."""

    headed: int = Field(default=2, ge=0)
    headless: int = Field(default=2, ge=0)

    @model_validator(mode="after")
    def _require_at_least_one_run(self) -> "RunCountsConfig":
        if self.headed + self.headless < 1:
            raise ValueError(
                "run_counts must total at least one run per framework "
                "(headed + headless >= 1)"
            )
        return self


class VerificationConfig(FrozenBaseConfig):
    api_key: SecretStr = Field(..., min_length=12, max_length=128)
    endpoint: AnyHttpUrl = Field(...)
    startup_url: AnyHttpUrl = Field(...)
    extra: dict = Field(default_factory=dict)

    model_config = SettingsConfigDict(env_prefix=f"{ENV_PREFIX_CHALLENGE}VERIFICATION_")


class BotRunnerServerConfig(BaseModel):
    url: AnyHttpUrl = Field(...)
    device_type: str = Field(..., min_length=1, max_length=32)


class BotRunnerConfig(FrozenBaseConfig):
    servers: List[BotRunnerServerConfig] = Field(..., min_length=1)
    api_key: SecretStr = Field(..., min_length=12, max_length=128)
    public_base_url: AnyHttpUrl = Field(...)
    bot: str = Field(default="aad-detect", min_length=1, max_length=128)
    request_timeout_sec: int = Field(default=15, ge=1)
    busy_retry_count: int = Field(default=3, ge=0, le=10)
    busy_backoff_initial_sec: float = Field(default=0.5, ge=0.0)
    busy_backoff_max_sec: float = Field(default=5.0, ge=0.0)
    run_counts: RunCountsConfig = Field(default_factory=RunCountsConfig)
    shuffle_runs: bool = Field(default=True)

    model_config = SettingsConfigDict(env_prefix=f"{ENV_PREFIX_CHALLENGE}BOT_RUNNER_")


class ChallengeConfig(FrozenBaseConfig):
    api_key: SecretStr = Field(..., min_length=12, max_length=128)
    docker_ulimit: int = Field(...)
    verification: VerificationConfig = Field(...)
    bot_timeout: int = Field(..., ge=1)
    # Seconds to wait for a human-verification run to complete (a real person
    # visiting the page is much slower than a driver).
    human_timeout: int = Field(default=120, ge=1)
    # Number of human-verification runs mixed into each scoring cycle.
    human_count: int = Field(default=1, ge=0)
    framework_images: List[FrameworkImageConfig] = Field(...)
    bot_runner: BotRunnerConfig = Field(...)

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX_CHALLENGE, env_nested_delimiter="__"
    )


__all__ = [
    "FrameworkImageConfig",
    "RunCountsConfig",
    "BotRunnerServerConfig",
    "ChallengeConfig",
    "VerificationConfig",
    "BotRunnerConfig",
]
