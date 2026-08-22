def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_taxonomy_stats(client):
    stats = client.get("/v1/taxonomy/stats").json()
    assert stats["total_skills"] > 25
    assert set(stats["by_tier"]) == {"custom", "external", "master"}


def test_infer_endpoint_validates_context_type(client):
    resp = client.post("/v1/skills/infer", json={"text": "hi", "context_type": "bogus"})
    assert resp.status_code == 422


def test_infer_endpoint_returns_explanations(client):
    body = client.post(
        "/v1/skills/infer",
        json={"text": "Hiring engineers with Python and Kubernetes experience.", "context_type": "job_description"},
    ).json()
    names = {s["canonical_name"] for s in body["skills"]}
    assert {"Python", "Kubernetes"} <= names
    assert all(s["explanation"] for s in body["skills"])


def test_normalize_endpoint_precedence(client):
    body = client.post("/v1/skills/normalize", json={"name": "k8s"}).json()
    assert body["skill_id"] == "esco__004"
    assert body["method"] == "alias"


def test_search_endpoint(client):
    results = client.get("/v1/skills/search", params={"q": "spark", "k": 2}).json()["results"]
    assert 0 < len(results) <= 2


def test_feedback_updates_model_weights(client):
    first = client.post("/v1/feedback", json={"raw_input": "Python", "accepted": True}).json()
    assert first["n_updates"] >= 1
    weights = client.get("/v1/model/weights").json()
    assert weights["n_updates"] == first["n_updates"]
    assert set(weights["weights"]) >= {"bias", "exact", "vector_sim"}


def test_lifecycle_report_flags_doomed_skill(client):
    report = client.get("/v1/lifecycle/report", params={"today": "2026-08-23"}).json()
    declining_targets = {a["target"] for a in report["actions"] if a["action"] == "flag_declining"}
    assert "esco__014" in declining_targets
    etl_action = next(a for a in report["actions"] if a["target"] == "esco__014")
    assert etl_action["reason"]
    assert etl_action["metrics"]["health_score"] < 0.35


def test_lifecycle_run_dry_run_makes_no_snapshot(client, tmp_path):
    body = client.post("/v1/lifecycle/run", params={"dry_run": "true", "today": "2026-08-23"}).json()
    assert body["dry_run"] is True
    assert body["snapshot_dir"] is None
    kinds = {a["action"] for a in body["actions"]}
    assert "propose_emerging" in kinds
