from skills_engine.embedders.hashing import HashingEmbedder
from skills_engine.normalization.normalizer import Normalizer
from skills_engine.taxonomies.loader import TaxonomyStore
from skills_engine.taxonomies.models import Skill, SkillStatus, SkillTier


def make_normalizer(status: SkillStatus = SkillStatus.ACTIVE) -> Normalizer:
    store = TaxonomyStore()
    store.add_or_update(Skill(skill_id="m1", name="Docker", tier=SkillTier.MASTER, status=status, aliases=["container runtime"]))
    return Normalizer(store, HashingEmbedder())


def test_folding_handles_case_and_punctuation():
    result = make_normalizer().normalize("  DOCKER!!!  ")
    assert result.matched_skill_id == "m1"
    assert result.method == "exact"
    assert result.confidence == 1.0


def test_alias_lookup():
    result = make_normalizer().normalize("Container Runtime")
    assert result.matched_skill_id == "m1"
    assert result.method == "alias"
    assert result.confidence == 0.95


def test_no_match_returns_defaults():
    result = make_normalizer().normalize("warp drives")
    assert result.matched_skill_id is None
    assert result.method == "none"
    assert result.confidence == 0.0


def test_search_respects_deprecated_status():
    normalizer = make_normalizer(status=SkillStatus.DEPRECATED)
    hits = normalizer.search("docker containers", k=3)
    assert all(h["status"] != "deprecated" for h in hits)


def test_stats_counts_by_tier():
    engine_store = TaxonomyStore()
    engine_store.add_or_update(Skill(skill_id="m1", name="A", tier=SkillTier.MASTER))
    engine_store.add_or_update(Skill(skill_id="c1", name="B", tier=SkillTier.CUSTOM))
    n = Normalizer(engine_store, HashingEmbedder())
    assert len(n.global_index.keys) >= 2
