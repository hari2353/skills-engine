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


# ---------- 6. broader-skill hierarchy roll-up (parent_id already in schema) ----------

def test_normalize_explains_broader_skill(tmp_path):
    eng = _fresh_engine(tmp_path)
    dd = eng.settings.data_dir
    # give Kubernetes (esco__004) a broader parent in the shipped data
    import re as _re
    p = dd / "master_skills.csv"
    rows = p.read_text().splitlines()
    hdr = rows[0].split(",")
    i_id, i_par = hdr.index("skill_id"), hdr.index("parent_id")
    out = [rows[0]]
    for r in rows[1:]:
        cells = r.split(",")
        if cells[i_id] == "esco__004":
            cells[i_par] = "esco__007"
            r = ",".join(cells)
        out.append(r)
    p.write_text("\n".join(out) + "\n")
    from skills_engine.config import Settings
    from skills_engine.engine import SkillsEngine

    eng2 = SkillsEngine(Settings(data_dir=dd), enable_ranker=False)
    r = eng2.normalize("k8s")
    assert r["skill_id"] == "esco__004"
    assert "broader skill" in r["explanation"]
    assert "esco__007" in r["explanation"]


# ---------- 7. per-skill market endpoint (demand + capped-window trend) ----------

def test_market_signal_per_skill(tmp_path):
    import json as _json

    eng = _fresh_engine(tmp_path)
    dd = eng.settings.data_dir
    (dd / "usage_log.jsonl").write_text(
        "\n".join(_json.dumps({"ts": ts, "type": "resolved", "skill_id": "esco__004"})
                  for ts in ("2026-11-01", "2026-11-10", "2026-10-05", "2026-05-01")) + "\n")
    out = eng.market("esco__004", today=date(2026, 11, 17))
    assert out["skill_id"] == "esco__004"
    assert out["name"] == eng.store.skills["esco__004"].name
    assert out["demand"] > 0  # shipped market_signals.csv has esco__004
    assert out["mentions"] == 4
    assert out["last_seen"] == "2026-11-10"
    assert out["trend"] == "rising"  # 2 recent vs 1 older event
    from skills_engine.config import Settings
    from skills_engine.engine import SkillsEngine

    eng2 = SkillsEngine(Settings(data_dir=dd), enable_ranker=False)
    try:
        eng2.market("nope__999")
        raise AssertionError("market() must raise KeyError for unknown skill")
    except KeyError:
        pass


def test_market_endpoint(client):
    body = client.get("/v1/skills/esco__004/market").json()
    assert {"skill_id", "name", "demand", "coverage", "mentions", "last_seen", "trend"} <= set(body)
    assert client.get("/v1/skills/nope__999/market").status_code == 404


# ---------- 8. lenient-F1 alongside strict F1 in the golden gate ----------

def test_extraction_eval_lenient_f1(tmp_path):
    from skills_engine.evals.runner import run_extraction_eval

    golden = tmp_path / "golden.csv"
    golden.write_text(
        "text,context_type,expected_canonical\n"
        "Hiring engineers with Python experience.,job_description,Python\n"
        "Deploy on k8s clusters.,job_description,K8s\n",
        encoding="utf-8")
    res = run_extraction_eval(_fresh_engine(tmp_path), golden)
    assert 0 < res["lenient_f1"] <= 1.0
    assert res["lenient_f1"] >= res["f1"]  # alias expansion can only help
    k8s_row = next(r for r in res["rows"] if "k8s" in r["text"])
    assert k8s_row["match"] is False          # strict: K8s != Kubernetes
    assert k8s_row["lenient_match"] is True   # lenient: k8s is an alias of Kubernetes


def test_evals_cli_reports_lenient(engine_fixture, tmp_path, capsys):
    from skills_engine.evals.cli import main as evals_main
    import sys as _sys

    argv = _sys.argv
    _sys.argv = ["evals", "--data-dir", str(engine_fixture.settings.data_dir)]
    try:
        evals_main()
    except SystemExit:
        pass
    finally:
        _sys.argv = argv
    out = capsys.readouterr().out
    assert "lenient_f1" in out


# ---------- 9. O*NET master pack (swappable master tier, real data) ----------

def test_onet_master_pack_loads():
    from skills_engine.config import Settings
    from skills_engine.engine import SkillsEngine
    from skills_engine.taxonomies.models import SkillTier

    pack = Path(__file__).resolve().parents[1] / "data" / "packs" / "onet"
    assert (pack / "master_skills.csv").exists()
    eng = SkillsEngine(Settings(data_dir=pack), enable_ranker=False)
    assert len(eng.store.skills) >= 200
    assert all(s.tier == SkillTier.MASTER for s in eng.store.skills.values())
    onet = eng.normalize("Ruby on Rails")
    assert onet["skill_id"] is not None
    assert onet["tier"] == "master"
