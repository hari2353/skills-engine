from skills_engine.embedders.hashing import HashingEmbedder
from skills_engine.normalization.normalizer import Normalizer
from skills_engine.resolution.resolver import SkillResolver
from skills_engine.taxonomies.loader import TaxonomyStore
from skills_engine.taxonomies.models import Skill, SkillTier


def make_store():
    store = TaxonomyStore()
    for s in [
        Skill(skill_id="m1", name="Machine Learning", tier=SkillTier.MASTER, aliases=["ML"]),
        Skill(skill_id="x1", name="Machine Learning Ops", tier=SkillTier.EXTERNAL),
        Skill(skill_id="c1", name="Machine Learning", tier=SkillTier.CUSTOM),
        Skill(skill_id="m2", name="Docker", tier=SkillTier.MASTER),
    ]:
        store.add_or_update(s)
    return store


def resolver():
    return SkillResolver(Normalizer(make_store(), HashingEmbedder()))


def test_custom_tier_wins_over_master():
    r = resolver().resolve("machine learning")
    assert r.skill_id == "c1"
    assert r.tier.value == "custom"
    assert r.method == "exact"
    assert r.confidence == 1.0
    assert "custom tier" in r.explanation


def test_alias_match_reports_provenance():
    r = resolver().resolve("ML")
    assert r.skill_id == "m1"
    assert r.method == "alias"
    assert r.confidence == 0.95
    assert "alias match" in r.explanation


def test_vector_fallback_within_custom_first():
    r = resolver().resolve("machine learning fundamentals")
    assert r.skill_id == "c1"
    assert r.method == "vector"
    assert r.confidence >= 0.6
    assert "similarity" in r.explanation


def test_unresolved_has_zero_confidence():
    r = resolver().resolve("quantum blockchain synergy")
    assert r.skill_id is None
    assert r.method == "none"
    assert r.confidence == 0.0
