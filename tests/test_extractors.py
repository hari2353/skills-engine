import pytest

from skills_engine.inference.contexts import PROMPTS, ContextType
from skills_engine.inference.extractors import OpenAICompatExtractor, RuleBasedExtractor, parse_skills_json
from skills_engine.taxonomies.loader import TaxonomyStore
from skills_engine.taxonomies.models import Skill, SkillStatus, SkillTier


def make_extractor():
    store = TaxonomyStore()
    store.add_or_update(Skill(skill_id="m1", name="Machine Learning", tier=SkillTier.MASTER, aliases=["ML"]))
    store.add_or_update(Skill(skill_id="m2", name="Apache Kafka", tier=SkillTier.MASTER))
    store.add_or_update(Skill(skill_id="d1", name="Old Thing", tier=SkillTier.MASTER, status=SkillStatus.DEPRECATED))
    return RuleBasedExtractor(list(store.skills.values()))


def test_multiword_and_alias_extraction():
    text = "Needs ML experience and Apache Kafka streaming knowledge."
    found = make_extractor().extract(text, ContextType.JOB_DESCRIPTION)
    assert set(found) == {"Machine Learning", "Apache Kafka"}


def test_deprecated_skills_not_extracted():
    text = "Years of Old Thing and Machine Learning work."
    found = make_extractor().extract(text, ContextType.RESUME)
    assert found == ["Machine Learning"]


def test_parse_skills_json_variants():
    assert parse_skills_json('{"skills": ["A", "B"]}') == ["A", "B"]
    assert parse_skills_json('```json\n{"skills": ["C"]}\n```') == ["C"]
    assert parse_skills_json('["D", "E"]') == ["D", "E"]
    with pytest.raises(Exception):
        parse_skills_json("not json at all")


def test_openai_extractor_hits_chat_completions(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": '{"skills": ["Python"]}'}}]}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["payload"] = json
        captured["headers"] = headers
        return FakeResponse()

    monkeypatch.setattr("skills_engine.inference.extractors.httpx.post", fake_post)
    extractor = OpenAICompatExtractor("http://llm.local/v1/", api_key="k", model="m")
    out = extractor.extract("text", ContextType.TASK)
    assert out == ["Python"]
    assert captured["url"] == "http://llm.local/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer k"
    assert PROMPTS[ContextType.TASK] in captured["payload"]["messages"][0]["content"]


def test_emit_unknown_surfaces_oov_phrases():
    text = "Works on promptfoo evaluation harnesses and Machine Learning pipelines."
    found = make_extractor().extract(text, ContextType.RESUME, emit_unknown=True)
    assert "Machine Learning" in found
    unknown = [f for f in found if f != 'Machine Learning']
    assert any('promptfoo' in u for u in unknown)
    plain = make_extractor().extract(text, ContextType.RESUME)
    assert all('promptfoo' not in p for p in plain)
