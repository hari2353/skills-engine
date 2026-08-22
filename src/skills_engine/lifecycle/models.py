from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class LifecycleActionType(str, Enum):
    PROPOSE_EMERGING = "propose_emerging"
    PROMOTE = "promote"
    FLAG_DECLINING = "flag_declining"
    DEPRECATE = "deprecate"
    ARCHIVE = "archive"


class LifecycleAction(BaseModel):
    action: LifecycleActionType
    target: str
    reason: str
    metrics: dict[str, float] = Field(default_factory=dict)


class SkillSignals(BaseModel):
    mentions: int = 0
    last_seen: date | None = None
    market_demand: float = 0.0
    content_coverage: float = 0.0


class Candidate(BaseModel):
    surface: str
    mentions: int = 0
    last_seen: date | None = None


class LifecyclePolicy(BaseModel):
    half_life_days: float = 912.5
    declining_threshold: float = 0.35
    retire_after_days: int = 270
    archive_after_days: int = 180
    promote_min_mentions: int = 5
    emerge_min_mentions: int = 3
    recency_weight: float = 0.4
    demand_weight: float = 0.4
    coverage_weight: float = 0.2
