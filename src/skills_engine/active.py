"""Active learning helpers (cross-pollinated from DataPerf/ML practice).

Uncertainty sampling: pick the examples the current model is least sure
about, so a labeling budget goes where it buys the most information.
Pure Python, no ML framework.
"""

from __future__ import annotations

import math


def entropy(probabilities: list[float]) -> float:
    """Shannon entropy (nats) of a probability distribution."""
    if not probabilities:
        raise ValueError("probabilities must be non-empty")
    if any(p < 0 for p in probabilities):
        raise ValueError("probabilities must be >= 0")
    total = sum(probabilities)
    if total <= 0:
        raise ValueError("probabilities must sum to > 0")
    normalized = [p / total for p in probabilities]
    return -sum(p * math.log(p) for p in normalized if p > 0)


def _score(item: dict, score_key: str) -> float:
    if score_key in item:
        return float(item[score_key])
    if "probabilities" in item:
        return 1.0 - max(item["probabilities"])
    if "probability" in item:
        return 1.0 - float(item["probability"])
    raise ValueError(f"item has no {score_key!r} or probabilities")


def uncertainty_sample(items: list[dict], *, k: int, score_key: str = "uncertainty") -> list[dict]:
    """Return the ``k`` items with highest uncertainty, stable by id."""
    if k < 0:
        raise ValueError("k must be >= 0")
    if k == 0 or not items:
        return []
    k = min(k, len(items))
    ranked = sorted(
        items,
        key=lambda item: (-_score(item, score_key), str(item.get("id", ""))),
    )
    return [dict(item) for item in ranked[:k]]


def margin_sample(items: list[dict], *, k: int, probabilities_key: str = "probabilities") -> list[dict]:
    """Select items with the smallest gap between the top two probabilities."""
    if k < 0:
        raise ValueError("k must be >= 0")
    if k == 0 or not items:
        return []

    def margin(item: dict) -> float:
        probs = sorted(item.get(probabilities_key, []), reverse=True)
        if len(probs) < 2:
            return 1.0
        return probs[0] - probs[1]

    ranked = sorted(items, key=lambda item: (margin(item), str(item.get("id", ""))))
    return [dict(item) for item in ranked[: min(k, len(items))]]
