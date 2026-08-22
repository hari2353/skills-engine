import json

from skills_engine.signals.market import ArbeitnowProvider, posting_text, postings_to_events
from skills_engine.signals.cli import append_events, update_market_csv, run


def fake_fetch_factory(pages_payload: dict[int, dict]):
    def fetch(page: int) -> dict:
        return pages_payload[page]

    return fetch


def test_provider_paginates_until_short_page():
    payload = {
        1: {"data": [{"slug": f"job{i}"} for i in range(25)]},
        2: {"data": [{"slug": "last"}]},
        3: {"data": [{"slug": "never"}]},
    }
    provider = ArbeitnowProvider(fetch=fake_fetch_factory(payload))
    postings = provider.fetch_postings(pages=3)
    assert len(postings) == 26


def test_posting_text_joins_fields():
    text = posting_text({"title": "Dev", "description": "Uses Python", "tags": ["docker"]})
    assert "Python" in text and "docker" in text


def test_postings_to_events(engine_fixture):
    postings = [
        {"title": "Backend Dev", "description": "Strong Python and Docker", "tags": []},
        {"title": "Researcher", "description": "Works on promptfoo evaluation harnesses", "tags": []},
    ]
    events = postings_to_events(engine_fixture, postings, source="arbeitnow")
    resolved = {e["skill_id"] for e in events if e["type"] == "resolved"}
    unresolved = [e["raw"] for e in events if e["type"] == "unresolved"]
    assert any(s.startswith("esco__") for s in resolved)
    assert any("promptfoo" in u for u in unresolved)
    assert all(e.get("source") == "arbeitnow" for e in events)


def test_cli_run_updates_signals(tmp_path, engine_fixture):
    payload = {
        1: {
            "data": [
                {"title": "Dev", "description": "Python and Docker", "tags": []},
                {"title": "Analyst", "description": "Kubernetes operations", "tags": []},
            ]
        }
    }
    provider = ArbeitnowProvider(fetch=fake_fetch_factory(payload))
    summary = run(provider, engine_fixture, tmp_path, pages=1)
    assert summary["postings"] == 2 and summary["resolved_events"] >= 3
    log_lines = (tmp_path / "usage_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert all(json.loads(l)["ts"] for l in log_lines)
    market = (tmp_path / "market_signals.csv").read_text(encoding="utf-8")
    assert "esco__007" in market and "demand" in market
