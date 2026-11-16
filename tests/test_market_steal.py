"""market-steal build: the 3 approved shortlist items.

1. unresolved-with-hints (HireLayer "never guessed" policy)
2. taxonomy version + snapshot changelog (Lightcast versioned releases)
3. related-skills endpoint (Lightcast /related via the existing vector index)
"""
import shutil
from datetime import date
from pathlib import Path

REPO_DATA = Path(__file__).resolve().parents[1] / "data"


def _fresh_engine(tmp_path):
    from skills_engine.config import Settings
    from skills_engine.engine import SkillsEngine

    data_dir = tmp_path / "data"
    shutil.copytree(REPO_DATA, data_dir)
    return SkillsEngine(Settings(data_dir=data_dir), enable_ranker=False)


# ---------- 1. unresolved-with-hints ----------

def test_normalize_unresolved_carries_hints(engine_fixture):
    r = engine_fixture.normalize("zzqx wibble machine learning gibberish")
    assert r["skill_id"] is None
    hints = r["hints"]
    assert 0 < len(hints) <= 3
    for h in hints:
        assert {"name", "tier", "score"} <= set(h)
        assert h["tier"] in {"custom", "external", "master"}


def test_normalize_resolved_has_no_hints(engine_fixture):
    assert engine_fixture.normalize("Python")["hints"] == []


def test_normalize_endpoint_hints_shape(client):
    body = client.post("/v1/skills/normalize",
                       json={"name": "zzqx wibble machine gibberish"}).json()
    assert body["skill_id"] is None
    assert isinstance(body.get("hints"), list) and body["hints"]


# ---------- 2. related-skills endpoint ----------

def test_related_skills_excludes_self_and_sorts(engine_fixture):
    out = engine_fixture.related("esco__004", k=3)
    assert out["skill_id"] == "esco__004"
    rel = out["related"]
    assert 0 < len(rel) <= 3
    assert all({"skill_id", "name", "tier", "score"} <= set(r) for r in rel)
    assert all(r["skill_id"] != "esco__004" for r in rel)
    scores = [r["score"] for r in rel]
    assert scores == sorted(scores, reverse=True)


def test_related_endpoint_and_unknown_id(client):
    body = client.get("/v1/skills/esco__004/related", params={"k": 2}).json()
    assert len(body["related"]) <= 2
    resp = client.get("/v1/skills/nope__999/related")
    assert resp.status_code == 404


# ---------- 3. taxonomy version + snapshot changelog ----------

def _lifecycle_runner(engine, data_dir):
    from skills_engine.lifecycle.models import LifecyclePolicy
    from skills_engine.lifecycle.runner import LifecycleRunner

    return LifecycleRunner(engine.store, engine.normalizer, data_dir), LifecyclePolicy()


def test_taxonomy_version_baseline_then_snapshot(tmp_path):
    from skills_engine.taxonomies.models import Skill, SkillStatus, SkillTier

    eng = _fresh_engine(tmp_path)
    assert eng.taxonomy_version() == "baseline"
    runner, policy = _lifecycle_runner(eng, eng.settings.data_dir)
    runner.apply(runner.report(policy, date(2026, 8, 23)), policy, date(2026, 8, 23))
    assert eng.taxonomy_version() == "2026-08-23"
    # change the store, snapshot again -> version moves, changelog shows the delta
    eng.store.add_or_update(Skill(skill_id="cus__reltest", name="Vector Databases",
                                  tier=SkillTier.CUSTOM, status=SkillStatus.ACTIVE))
    runner.apply(runner.report(policy, date(2026, 8, 24)), policy, date(2026, 8, 24))
    assert eng.taxonomy_version() == "2026-08-24"
    log = eng.changelog()
    assert log["truncated"] is False
    entry = next(e for e in log["releases"] if e["date"] == "2026-08-24")
    assert "cus__reltest" in entry["added"]  # changelog diffs use skill_ids
    assert log["releases"][-1]["date"] == "2026-08-24"


def test_version_and_changelog_endpoints(client):
    v = client.get("/v1/taxonomy/version").json()
    assert v["taxonomy_version"] == "baseline"
    run = client.post("/v1/lifecycle/run", params={"dry_run": "false", "today": "2026-08-23"}).json()
    assert run["snapshot_dir"]
    assert client.get("/v1/taxonomy/version").json()["taxonomy_version"] == "2026-08-23"
    log = client.get("/v1/taxonomy/changelog").json()
    assert log["releases"] and log["releases"][-1]["date"] == "2026-08-23"


def test_stats_includes_taxonomy_version(client):
    assert "taxonomy_version" in client.get("/v1/taxonomy/stats").json()
