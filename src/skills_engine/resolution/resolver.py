from pydantic import BaseModel, Field

from ..taxonomies.models import SkillStatus, SkillTier


class ResolvedSkill(BaseModel):
    raw_input: str
    skill_id: str | None = None
    canonical_name: str | None = None
    tier: SkillTier | None = None
    status: SkillStatus | None = None
    confidence: float = 0.0
    method: str = "none"
    explanation: str = ""
    hints: list[dict] = Field(default_factory=list)


class SkillResolver:
    def __init__(self, normalizer, ranker=None) -> None:
        self.normalizer = normalizer
        self.ranker = ranker

    def resolve(self, name: str, locale: str = "en") -> ResolvedSkill:
        r = self.normalizer.normalize(name)
        confidence = r.confidence
        explanation = r.explanation
        if self.ranker is not None and r.matched_skill_id is not None:
            adjusted = self.ranker.score(r)
            confidence = round(0.5 * confidence + 0.5 * adjusted, 4)
            explanation += f"; bandit-adjusted confidence {confidence} (model p={adjusted:.4f})"
        if r.matched_skill_id is not None:
            skill = self.normalizer.store.skills[r.matched_skill_id]
            parent = self.normalizer.store.skills.get(skill.parent_id or "")
            if parent is not None:
                explanation += f"; broader skill: {parent.name} ({parent.skill_id})"
        return ResolvedSkill(
            raw_input=name,
            skill_id=r.matched_skill_id,
            canonical_name=r.canonical_name,
            tier=r.tier,
            status=r.status,
            confidence=confidence,
            method=r.method,
            explanation=explanation,
            hints=r.hints,
        )
