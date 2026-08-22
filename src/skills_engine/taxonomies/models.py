from enum import Enum

from pydantic import BaseModel, Field


class SkillTier(str, Enum):
    CUSTOM = "custom"
    EXTERNAL = "external"
    MASTER = "master"


class SkillStatus(str, Enum):
    PROVISIONAL = "provisional"
    ACTIVE = "active"
    DECLINING = "declining"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class Skill(BaseModel):
    skill_id: str
    name: str
    tier: SkillTier
    locale: str = "en"
    aliases: list[str] = Field(default_factory=list)
    vendor: str | None = None
    parent_id: str | None = None
    status: SkillStatus = SkillStatus.ACTIVE
