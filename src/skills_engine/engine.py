import json
from datetime import date

from .config import Settings
from .embedders.hashing import get_embedder
from .feedback.bandit import FeedbackBandit
from .inference.contexts import ContextType
from .inference.extractors import RuleBasedExtractor, get_extractor
from .normalization.normalizer import Normalizer
from .resolution.resolver import SkillResolver
from .taxonomies.loader import TaxonomyStore
from .taxonomies.models import SkillStatus
from .text import fold

STALE_STATUSES = (SkillStatus.DEPRECATED, SkillStatus.ARCHIVED)


class SkillsEngine:
    def __init__(self, settings: Settings, enable_ranker: bool = True) -> None:
        self.settings = settings
        self.store = TaxonomyStore()
        self.store.load_dir(settings.data_dir)
        self.embedder = get_embedder(settings.embedding_backend)
        self.ranker = (
            FeedbackBandit(
                weights_path=settings.data_dir / "model" / "bandit_weights.json",
                log_path=settings.data_dir / "model" / "feedback_log.jsonl",
            )
            if enable_ranker
            else None
        )
        self.normalizer = Normalizer(self.store, self.embedder, settings.fuzzy_threshold)
        self.resolver = SkillResolver(self.normalizer, self.ranker)
        self.extractor = get_extractor(
            list(self.store.skills.values()),
            settings.llm_base_url,
            settings.llm_api_key,
            settings.llm_model,
        )

    def infer(self, text: str, context_type: ContextType = ContextType.JOB_DESCRIPTION, locale: str = "en", log_usage: bool = False, emit_unknown: bool = False) -> dict:
        degraded = False
        try:
            raw_skills = self.extractor.extract(text, context_type, emit_unknown=emit_unknown)
        except Exception:
            raw_skills = RuleBasedExtractor(list(self.store.skills.values())).extract(text, context_type, emit_unknown)
            degraded = True
        resolved = [self.resolver.resolve(raw, locale) for raw in raw_skills]
        usable = [r for r in resolved if r.skill_id is not None and r.status not in STALE_STATUSES]
        unresolved = [r.raw_input for r in resolved if r.skill_id is None]
        if log_usage:
            self._log_usage(resolved)
        return {
            "context_type": context_type.value,
            "locale": locale,
            "degraded_to_rules": degraded,
            "dropped_stale_matches": len(resolved) - len(usable),
            "skills": [r.model_dump(mode="json") for r in usable],
            "unresolved": unresolved,
        }

    def normalize(self, name: str, locale: str = "en") -> dict:
        return self.resolver.resolve(name, locale).model_dump(mode="json")

    def search(self, query: str, k: int = 5) -> list[dict]:
        return self.normalizer.search(query, k=k)

    def stats(self) -> dict:
        by_tier: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for s in self.store.skills.values():
            by_tier[s.tier.value] = by_tier.get(s.tier.value, 0) + 1
            by_status[s.status.value] = by_status.get(s.status.value, 0) + 1
        return {"total_skills": len(self.store.skills), "by_tier": by_tier, "by_status": by_status}

    def feedback(self, raw_input: str, accepted: bool) -> dict:
        if self.ranker is None:
            return {"error": "ranker disabled"}
        resolved = self.resolver.resolve(raw_input)
        prior_p, posterior_p = self.ranker.update(resolved, accepted)
        return {
            "raw_input": raw_input,
            "resolved_skill_id": resolved.skill_id,
            "prior_confidence": round(prior_p, 4),
            "posterior_confidence": round(posterior_p, 4),
            "n_updates": self.ranker.n_updates,
            "weights": self.ranker.weights,
        }

    def _log_usage(self, resolved) -> None:
        usage_path = self.settings.data_dir / "usage_log.jsonl"
        usage_path.parent.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        with usage_path.open("a", encoding="utf-8") as fh:
            for r in resolved:
                if r.skill_id is not None:
                    fh.write(json.dumps({"ts": today, "type": "resolved", "skill_id": r.skill_id}) + "\n")
                else:
                    fh.write(json.dumps({"ts": today, "type": "unresolved", "raw": fold(r.raw_input)}) + "\n")
