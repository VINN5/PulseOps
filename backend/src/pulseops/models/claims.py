from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ClaimType(StrEnum):
    BAD_DEPLOY = "bad_deploy"
    BAD_CONFIG = "bad_config"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    SLOW_DEPENDENCY = "slow_dependency"
    RETRY_STORM = "retry_storm"
    CAPACITY_OR_TRAFFIC = "capacity_or_traffic"
    EXTERNAL_OR_UNKNOWN = "external_or_unknown"


class VerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template: str
    params: dict[str, str] = Field(default_factory=dict)


class Hypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    claim_type: ClaimType
    service: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    supporting: list[str] = Field(default_factory=list)
    contradicting: list[str] = Field(default_factory=list)
    verification: list[VerificationRequest] = Field(default_factory=list)
