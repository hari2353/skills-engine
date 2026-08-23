from __future__ import annotations

import re

TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(TOKEN_RE.findall(text.lower()))


class LexicalReranker:
    def score(self, query: str, candidate_text: str) -> float:
        q = _tokens(query)
        c = _tokens(candidate_text)
        if not q or not c:
            return 0.0
        overlap = len(q & c)
        precision = overlap / len(c)
        recall = overlap / len(q)
        if precision + recall == 0:
            return 0.0
        return round(2 * precision * recall / (precision + recall), 4)


class CrossEncoderReranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-base") -> None:
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(model_name)

    def score(self, query: str, candidate_text: str) -> float:
        import math

        logit = float(self.model.predict([(query, candidate_text)]))
        return round(1.0 / (1.0 + math.exp(-logit)), 4)


def get_reranker(backend: str = "lexical"):
    if backend == "cross_encoder":
        return CrossEncoderReranker()
    if backend == "lexical":
        return LexicalReranker()
    raise ValueError(f"unknown reranker backend '{backend}'")


class RerankResult:
    __slots__ = ("skill_id", "surface", "tier", "vector_sim", "rerank_score", "blended")

    def __init__(self, skill_id: str, surface: str, tier: str, vector_sim: float, rerank_score: float, vec_weight: float) -> None:
        self.skill_id = skill_id
        self.surface = surface
        self.tier = tier
        self.vector_sim = vector_sim
        self.rerank_score = rerank_score
        self.blended = round(vec_weight * vector_sim + (1 - vec_weight) * rerank_score, 4)

    @property
    def rank_key(self) -> tuple[float, int]:
        return (self.blended, -TIER_ORDER_INDEX.get(self.tier, 0))


TIER_ORDER_INDEX = {"custom": 0, "external": 1, "master": 2}
