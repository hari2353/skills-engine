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


# ---------- 4. bandit rejections -> lifecycle health (outcome curation) ----------

def test_health_score_neutral_without_feedback():
    from skills_engine.lifecycle.models import LifecyclePolicy, SkillSignals
    from skills_engine.lifecycle.policy import health_score

    sig = SkillSignals(mentions=2, last_seen=date(2026, 8, 20))
    score, metrics = health_score(sig, LifecyclePolicy(), date(2026, 8, 23))
    assert metrics["outcome_multiplier"] == 1.0
    assert metrics["rejections"] == 0.0
    assert score > 0.35  # unchanged by absence of feedback


def test_health_score_penalized_by_rejections():
    from skills_engine.lifecycle.models import LifecyclePolicy, SkillSignals
    from skills_engine.lifecycle.policy import health_score

    sig = SkillSignals(mentions=2, last_seen=date(2026, 8, 20), acceptances=0, rejections=6)
    score, metrics = health_score(sig, LifecyclePolicy(), date(2026, 8, 23))
    assert metrics["reject_rate"] == 1.0
    assert metrics["outcome_multiplier"] == 0.7  # 1 - outcome_weight * 1.0
    assert score < 0.35  # crosses the declining threshold from ~0.4


def test_rejections_drive_declining_action(tmp_path):
    import json as _json

    from skills_engine.lifecycle.models import LifecycleActionType

    eng = _fresh_engine(tmp_path)
    dd = eng.settings.data_dir
    (dd / "usage_log.jsonl").write_text(
        "\n".join(_json.dumps({"ts": "2026-08-20", "type": "resolved", "skill_id": "cus__3002"})
                  for _ in range(4)) + "\n")
    model = dd / "model"
    model.mkdir(parents=True, exist_ok=True)
    (model / "feedback_log.jsonl").write_text(
        "\n".join(_json.dumps({"ts": "2026-08-21", "raw_input": "Transcript Chunking",
                               "skill_id": "cus__3002", "accepted": False})
                  for _ in range(6)) + "\n")
    runner, policy = _lifecycle_runner(eng, dd)
    actions = runner.report(policy, date(2026, 8, 23))
    act = next((a for a in actions if a.target == "cus__3002"), None)
    assert act is not None and act.action == LifecycleActionType.FLAG_DECLINING
    assert act.metrics["rejections"] == 6
    assert act.metrics["outcome_multiplier"] == 0.7


# ---------- 5. SKILL.md export for agent registries ----------

def test_export_skill_md_per_tier(tmp_path):
    eng = _fresh_engine(tmp_path)
    out = tmp_path / "skills-md"
    n = eng.export_skill_md(out)
    assert n >= 3
    files = list(out.rglob("SKILL.md"))
    assert len(files) == n
    custom = (out / "custom" / "SKILL.md").read_text()
    assert "name: skills-engine-custom" in custom
    assert "description:" in custom
    assert "| skill_id | name | status | aliases |" in custom


def test_export_skill_md_caps_rows(tmp_path):
    from skills_engine.taxonomies.models import Skill, SkillStatus, SkillTier

    eng = _fresh_engine(tmp_path)
    for i in range(60):
        eng.store.add_or_update(Skill(skill_id=f"cus__cap{i}", name=f"Cap Skill {i}",
                                      tier=SkillTier.CUSTOM, status=SkillStatus.ACTIVE))
    out = tmp_path / "cap-md"
    eng.export_skill_md(out, per_file_cap=50)
    text = (out / "custom" / "SKILL.md").read_text()
    assert "truncated" in text.lower()
    assert "| cus__cap59 |" not in text
    assert "| cus__cap49 |" in text
