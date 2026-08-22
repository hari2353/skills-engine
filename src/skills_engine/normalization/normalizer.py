from pydantic import BaseModel

from ..store.vector_index import VectorIndex
from ..taxonomies.models import SkillStatus, SkillTier
from ..text import fold

TIER_ORDER = [SkillTier.CUSTOM, SkillTier.EXTERNAL, SkillTier.MASTER]
SEARCHABLE_STATUSES = (SkillStatus.PROVISIONAL, SkillStatus.ACTIVE, SkillStatus.DECLINING)


class NormalizeResult(BaseModel):
    input: str
    matched_skill_id: str | None = None
    canonical_name: str | None = None
    tier: SkillTier | None = None
    status: SkillStatus | None = None
    confidence: float = 0.0
    method: str = "none"
    explanation: str = "no match found in any tier"


class Normalizer:
    def __init__(self, store, embedder, fuzzy_threshold: float = 0.65) -> None:
        self.store = store
        self.embedder = embedder
        self.fuzzy_threshold = fuzzy_threshold
        self.exact_name: dict[tuple[str, str], tuple[str, str]] = {}
        self.exact_alias: dict[tuple[str, str], tuple[str, str]] = {}
        self.indexes: dict[SkillTier, VectorIndex] = {}
        self.global_index = VectorIndex(embedder)
        self.rebuild()

    def rebuild(self) -> None:
        self.exact_name.clear()
        self.exact_alias.clear()
        for tier in TIER_ORDER:
            for s in self.store.by_tier.get(tier, []):
                self.exact_name.setdefault((tier.value, fold(s.name)), (s.skill_id, s.name))
                for alias in s.aliases:
                    self.exact_alias.setdefault((tier.value, fold(alias)), (s.skill_id, s.name))

        self.indexes.clear()
        per_tier: dict[SkillTier, list[tuple[str, str]]] = {t: [] for t in TIER_ORDER}
        global_items: list[tuple[str, str]] = []
        for s in self.store.skills.values():
            if s.status not in SEARCHABLE_STATUSES:
                continue
            for surface in [s.name, *s.aliases]:
                per_tier[s.tier].append((s.skill_id, surface))
                global_items.append((s.skill_id, surface))
        for tier, items in per_tier.items():
            idx = VectorIndex(self.embedder)
            idx.build(items)
            self.indexes[tier] = idx
        self.global_index.build(global_items)

    def normalize(self, name: str) -> NormalizeResult:
        key = fold(name)
        for tier in TIER_ORDER:
            hit = self.exact_name.get((tier.value, key))
            if hit:
                skill_id, canonical = hit
                return NormalizeResult(
                    input=name,
                    matched_skill_id=skill_id,
                    canonical_name=canonical,
                    tier=tier,
                    status=self.store.skills[skill_id].status,
                    confidence=1.0,
                    method="exact",
                    explanation=f"exact name match in {tier.value} tier",
                )
        for tier in TIER_ORDER:
            hit = self.exact_alias.get((tier.value, key))
            if hit:
                skill_id, canonical = hit
                return NormalizeResult(
                    input=name,
                    matched_skill_id=skill_id,
                    canonical_name=canonical,
                    tier=tier,
                    status=self.store.skills[skill_id].status,
                    confidence=0.95,
                    method="alias",
                    explanation=f"alias match in {tier.value} tier",
                )
        for tier in TIER_ORDER:
            hits = self.indexes.get(tier)
            if not hits or not hits.keys:
                continue
            top = hits.search(name, k=1)
            if top and top[0][2] >= self.fuzzy_threshold:
                skill_id, surface, score = top[0]
                return NormalizeResult(
                    input=name,
                    matched_skill_id=skill_id,
                    canonical_name=self.store.skills[skill_id].name,
                    tier=tier,
                    status=self.store.skills[skill_id].status,
                    confidence=round(score, 4),
                    method="vector",
                    explanation=(
                        f"embedding similarity {score:.3f} >= threshold {self.fuzzy_threshold} "
                        f"against '{surface}' in {tier.value} tier"
                    ),
                )
        return NormalizeResult(input=name)

    def search(self, query: str, k: int = 5) -> list[dict]:
        hits = self.global_index.search(query, k=k)
        out = []
        for skill_id, surface, score in hits:
            skill = self.store.skills[skill_id]
            out.append(
                {
                    "skill_id": skill_id,
                    "surface": surface,
                    "canonical_name": skill.name,
                    "tier": skill.tier.value,
                    "status": skill.status.value,
                    "score": round(score, 4),
                }
            )
        return out
