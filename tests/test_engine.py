from skills_engine.inference.contexts import ContextType


def test_infer_finds_skills_with_explanations(engine_fixture):
    out = engine_fixture.infer("Looking for Python engineers who know Docker.", ContextType.JOB_DESCRIPTION)
    names = {s["canonical_name"] for s in out["skills"]}
    assert {"Python", "Docker"} <= names
    assert all(s["explanation"] for s in out["skills"])
    assert out["degraded_to_rules"] is False
    assert out["unresolved"] == []


def test_normalize_custom_precedence_end_to_end(engine_fixture):
    result = engine_fixture.normalize("Kubernetes")
    assert result["skill_id"] == "cus__3003"
    assert result["tier"] == "custom"
    assert result["method"] == "exact"


def test_search_returns_ranked_hits(engine_fixture):
    hits = engine_fixture.search("kafka streaming", k=3)
    assert hits and hits[0]["skill_id"] == "esco__009"
    assert hits[0]["score"] >= hits[-1]["score"]


def test_stats_shape(engine_fixture):
    stats = engine_fixture.stats()
    assert stats["total_skills"] > 25
    assert set(stats["by_tier"]) == {"custom", "external", "master"}
