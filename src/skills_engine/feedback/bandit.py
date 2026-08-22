import json
import math
import time
from pathlib import Path

FEATURES = ["bias", "exact", "alias", "vector_sim", "is_custom", "is_external", "is_master"]


def features_from(result) -> dict[str, float]:
    method = result.method
    tier = result.tier.value if result.tier else ""
    return {
        "bias": 1.0,
        "exact": 1.0 if method == "exact" else 0.0,
        "alias": 1.0 if method == "alias" else 0.0,
        "vector_sim": result.confidence if method == "vector" else 0.0,
        "is_custom": 1.0 if tier == "custom" else 0.0,
        "is_external": 1.0 if tier == "external" else 0.0,
        "is_master": 1.0 if tier == "master" else 0.0,
    }


class FeedbackBandit:
    def __init__(self, weights_path: Path, log_path: Path, lr: float = 0.1) -> None:
        self.weights_path = weights_path
        self.log_path = log_path
        self.lr = lr
        self.weights: dict[str, float] = {f: 0.0 for f in FEATURES}
        self.n_updates = 0
        self._load()

    def _load(self) -> None:
        if self.weights_path.exists():
            data = json.loads(self.weights_path.read_text(encoding="utf-8"))
            self.weights.update(data.get("weights", {}))
            self.n_updates = int(data.get("n_updates", 0))

    def save(self) -> None:
        self.weights_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"weights": self.weights, "n_updates": self.n_updates}
        self.weights_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def trained(self) -> bool:
        return self.n_updates > 0

    def score(self, result) -> float:
        x = features_from(result)
        z = sum(self.weights[f] * v for f, v in x.items())
        return 1.0 / (1.0 + math.exp(-z))

    def update(self, result, accepted: bool) -> tuple[float, float]:
        x = features_from(result)
        y = 1.0 if accepted else 0.0
        prior_p = self.score(result)
        err = y - prior_p
        for feature, value in x.items():
            self.weights[feature] += self.lr * err * value
        self.n_updates += 1
        self.save()
        self._append_event(result, accepted)
        return prior_p, self.score(result)

    def _append_event(self, result, accepted: bool) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "ts": time.strftime("%Y-%m-%d"),
            "raw_input": result.raw_input,
            "skill_id": result.skill_id,
            "tier": result.tier.value if result.tier else None,
            "method": result.method,
            "accepted": accepted,
        }
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event) + "\n")
