from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, model_validator


class Settings(BaseSettings):
    control_plane_url: str = (
        "http://ai-infra-platform-api.ai-platform.svc.cluster.local:8000"
    )
    request_timeout_seconds: float = Field(default=240.0, gt=0, allow_inf_nan=False)
    upstream_timeout_seconds: float = Field(default=180.0, gt=0, allow_inf_nan=False)
    control_timeout_seconds: float = Field(default=3.0, gt=0, allow_inf_nan=False)
    audit_timeout_seconds: float = Field(default=2.0, gt=0, allow_inf_nan=False)
    control_cache_seconds: float = Field(default=2.0, ge=0, allow_inf_nan=False)
    control_stale_seconds: float = Field(default=30.0, ge=0, allow_inf_nan=False)
    default_policy: str = "weighted_random"
    default_max_tokens: int = 128
    backend_max_inflight: int = Field(default=4, ge=1)
    backend_inflight_limits: dict[str, int] = Field(default_factory=dict)
    stream_openai: bool = False
    affinity_prefix_chars: int = Field(default=1024, ge=1, le=65536)
    affinity_load_factor: float = Field(default=1.25, ge=1.0, le=10.0, allow_inf_nan=False)
    ttft_model: str = ""
    ttft_window_seconds: int = Field(default=30, ge=1, le=3600)

    @model_validator(mode="after")
    def validate_budgets(self):
        if self.audit_timeout_seconds >= self.request_timeout_seconds:
            raise ValueError("audit_timeout_seconds must be smaller than request_timeout_seconds")
        if self.control_stale_seconds < self.control_cache_seconds:
            raise ValueError("control_stale_seconds must not be smaller than control_cache_seconds")
        return self

    @field_validator("backend_inflight_limits")
    @classmethod
    def validate_limits(cls, limits: dict[str, int]) -> dict[str, int]:
        if any(not key.isdecimal() or int(key) <= 0 or str(int(key)) != key or value <= 0 for key, value in limits.items()):
            raise ValueError("backend_inflight_limits requires canonical positive backend IDs and positive limits")
        return limits


@lru_cache
def get_settings() -> Settings:
    return Settings()
