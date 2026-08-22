from datetime import date

import pytest

from skills_engine.embedders.hashing import HashingEmbedder
from skills_engine.lifecycle.models import Candidate, LifecycleActionType, LifecyclePolicy, SkillSignals
from skills_engine.lifecycle.policy import evaluate, health_score, recency_weight
from skills_engine.lifecycle.runner import LifecycleRunner
from skills_engine.normalization.normalizer import Normalizer
from skills_engine.taxonomies.loader import TaxonomyStore
from skills_engine.taxonomies.models import Skill, SkillStatus, SkillTier

TODAY = date(2026, 8, 23)


def build_store():
    store = TaxonomyStore()
    store.add_or_update(Skill(skill_id="s_old", name="Legacy ETL Tool", tier=SkillTier.MASTER))
    store.add_or_update(
        Skill(skill_id="s_prov", name="Prompt Engineering", tier=SkillTier.CUSTOM, status=SkillStatus.PROVISIONAL)
    )
    return store


def test_recency_half_life_math():
    assert recency_weight(0, 912.5) == pytest.approx(1.0)
    assert recency_weight(912.5, 912.5) == pytest.approx(0.5)
    assert recency_weight(-50, 912.5) == 1.0


def test_health_score_breakdown():
    sig = SkillSignals(mentions=10, last_seen=TODAY, market_demand=1.0, content_coverage=1.0)
    policy = LifecyclePolicy()
    score, metrics = health_score(sig, policy, TODAY)
    assert score == pytest.approx(1.0)
    assert metrics["days_since_last_seen"] == 0.0


def test_decline_promote_emerge_actions():
    store = build_store()
    signals = {"s_old": SkillSignals(mentions=2, last_seen=date(2025, 6, 1))}
    candidates = {
        "prompt engineering": Candidate(surface="prompt engineering", mentions=5),
        "agentic workflows": Candidate(surface="agentic workflows", mentions=3),
        "obscure thing": Candidate(surface="obscure thing", mentions=1),
    }
    actions = evaluate(store, signals, candidates, LifecyclePolicy(), TODAY)
    kinds = {(a.action, a.target) for a in actions}
    assert (LifecycleActionType.FLAG_DECLINING, "s_old") in kinds
    assert (LifecycleActionType.PROMOTE, "s_prov") in kinds
    assert (LifecycleActionType.PROPOSE_EMERGING, "agentic workflows") in kinds
    assert all(a.target != "obscure thing" for a in actions)
    declining = next(a for a in actions if a.action == LifecycleActionType.FLAG_DECLINING)
    assert "below declining threshold" in declining.reason
    assert "health_score" in declining.metrics


def test_no_signals_means_no_action():
    actions = evaluate(build_store(), {}, {}, LifecyclePolicy(), TODAY)
    assert all(a.target != "s_old" for a in actions)


def test_runner_apply_writes_snapshot_and_updates_statuses(tmp_path):
    from skills_engine.normalization.normalizer import Normalizer

    store = build_store()
    normalizer = Normalizer(store, HashingEmbedder())
    runner = LifecycleRunner(store, normalizer, tmp_path)
    signals = {"s_old": SkillSignals(mentions=2, last_seen=date(2025, 6, 1))}
    candidates = {"agentic workflows": Candidate(surface="Agentic Workflows", mentions=4)}
    policy = LifecyclePolicy()

    store.skills["s_old"].status = SkillStatus.DECLINING
    actions = evaluate(store, signals, candidates, policy, TODAY)

    snapshot_dir = runner.apply(actions, policy, TODAY)

    assert (snapshot_dir / "audit.json").exists()
    assert (snapshot_dir / "custom_skills.csv").exists()
    assert store.skills["s_old"].status == SkillStatus.DEPRECATED
    auto = [s for s in store.skills.values() if s.skill_id.startswith("cus__auto_")]
    assert len(auto) == 1 and auto[0].name == "Agentic Workflows"
    audit = (snapshot_dir / "audit.json").read_text(encoding="utf-8")
    assert "propose_emerging" in audit
