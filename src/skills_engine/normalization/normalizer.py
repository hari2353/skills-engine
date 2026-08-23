from pydantic import BaseModel

from ..rerank.reranker import RerankResult
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
    def __init__(self, store, embedder, fuzzy_threshold: float = 0.65, reranker=None,
                 rerank_candidates: int = 8, vec_weight: float = 0.5, soft_threshold: float = 0.45) -> None:
        from ..rerank.reranker import LexicalReranker

        self.store = store
        self.embedder = embedder
        self.fuzzy_threshold = fuzzy_threshold
        self.reranker = reranker or LexicalReranker()
        self.rerank_candidates = rerank_candidates
        self.vec_weight = vec_weight
        self.soft_threshold = soft_threshold
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
        reranked = self._rerank_vector_candidates(name)
        if reranked is not None:
            return reranked
        return NormalizeResult(input=name)

    def _rerank_vector_candidates(self, name: str) -> NormalizeResult | None:
        candidates: list[tuple[SkillTier, str, str, float]] = []
        for tier in TIER_ORDER:
            idx = self.indexes.get(tier)
            if not idx or not idx.keys:
                continue
            for skill_id, surface, sim in idx.search(name, k=self.rerank_candidates):
                if sim >= self.soft_threshold:
                    candidates.append((tier, skill_id, surface, sim))
        if not candidates:
            return None

        tier_rank = {SkillTier.CUSTOM: 0, SkillTier.EXTERNAL: 1, SkillTier.MASTER: 2}
        results: list[RerankResult] = []
        for tier, skill_id, surface, sim in candidates:
            if self.reranker is not None:
                lexical = self.reranker.score(name, surface)
            else:
                lexical = 0.0
            blended = round(
                (self.vec_weight * sim + (1 - self.vec_weight) * lexical) - 0.02 * tier_rank[tier],
                4,
            )
            results.append(RerankResult(skill_id, surface, tier.value, sim, lexical, self.vec_weight))
            results[-1].blended = blended

        results.sort(key=lambda r: -r.blended)
        best = results[0]
        if best.blended < self.fuzzy_threshold:
            return None
        skill = self.store.skills[best.skill_id]
        parts = [f"vector similarity {best.vector_sim:.3f}"]
        if self.reranker is not None:
            parts.append(f"reranker {best.rerank_score:.3f}")
        parts.append(f"blended {best.blended:.3f} >= threshold {self.fuzzy_threshold} against '{best.surface}' in {best.tier} tier")
        return NormalizeResult(
            input=name,
            matched_skill_id=best.skill_id,
            canonical_name=skill.name,
            tier=SkillTier(best.tier),
            status=skill.status,
            confidence=round(best.blended, 4),
            method="vector_reranked",
            explanation="; ".join(parts),
        )

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
