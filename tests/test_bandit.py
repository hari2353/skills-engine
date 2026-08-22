import json
import math
from pathlib import Path
from types import SimpleNamespace

from skills_engine.feedback.bandit import FeedbackBandit, features_from


def fake_result(method: str = "exact", tier_value: str = "master"):
    return SimpleNamespace(
        raw_input="python",
        skill_id="p1",
        tier=SimpleNamespace(value=tier_value),
        method=method,
        confidence=1.0 if method != "vector" else 0.8,
    )


def make_bandit(tmp_path: Path) -> FeedbackBandit:
    return FeedbackBandit(
        weights_path=tmp_path / "model" / "bandit_weights.json",
        log_path=tmp_path / "model" / "feedback_log.jsonl",
    )


def test_features_shape():
    x = features_from(fake_result())
    assert set(x) == {"bias", "exact", "alias", "vector_sim", "is_custom", "is_external", "is_master"}
    assert x["bias"] == 1.0 and x["exact"] == 1.0 and x["is_master"] == 1.0


def test_update_moves_weights_and_persists(tmp_path):
    bandit = make_bandit(tmp_path)
    before = dict(bandit.weights)
    for _ in range(3):
        prior, posterior = bandit.update(fake_result(), accepted=True)
    assert bandit.n_updates == 3
    assert posterior > prior or bandit.weights != before
    reloaded = FeedbackBandit(
        weights_path=tmp_path / "model" / "bandit_weights.json",
        log_path=tmp_path / "model" / "feedback_log.jsonl",
    )
    assert reloaded.n_updates == 3
    assert reloaded.trained() is True


def test_negative_feedback_lowers_score(tmp_path):
    bandit = make_bandit(tmp_path)
    r = fake_result()
    start = bandit.score(r)
    for _ in range(10):
        bandit.update(r, accepted=False)
    end = bandit.score(r)
    assert end < start
    assert 0.0 <= end <= 1.0


def test_events_appended(tmp_path):
    bandit = make_bandit(tmp_path)
    bandit.update(fake_result(), accepted=True)
    lines = (tmp_path / "model" / "feedback_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    event = json.loads(lines[0])
    assert event["skill_id"] == "p1" and event["accepted"] is True


def test_sigmoid_finite_for_large_inputs():
    bandit = make_bandit(Path("unused"))
    bandit.weights = {k: 1000.0 for k in bandit.weights}
    score = bandit.score(fake_result())
    assert math.isfinite(score) and score <= 1.0
