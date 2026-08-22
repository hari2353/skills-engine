import hashlib
import json
from datetime import date
from pathlib import Path

from ..taxonomies.models import Skill, SkillStatus, SkillTier
from ..text import fold
from .models import LifecycleAction, LifecycleActionType
from .policy import evaluate
from .provider import load_market_signals, load_usage_signals, merge_signals


class LifecycleRunner:
    def __init__(self, store, normalizer, data_dir: Path) -> None:
        self.store = store
        self.normalizer = normalizer
        self.data_dir = data_dir

    def collect_signals(self) -> tuple[dict, dict]:
        usage_path = self.data_dir / "usage_log.jsonl"
        by_skill, candidates = load_usage_signals(usage_path)
        fallback_usage = self.data_dir / "usage_signals.jsonl"
        if not by_skill and not candidates and fallback_usage.exists():
            fb_skill, fb_candidates = load_usage_signals(fallback_usage)
            for k, v in fb_skill.items():
                by_skill.setdefault(k, v)
            for k, v in fb_candidates.items():
                candidates.setdefault(k, v)
        market = load_market_signals(self.data_dir / "market_signals.csv")
        merged = merge_signals(by_skill, market, self.store)
        return merged, candidates

    def report(self, policy, today: date | None = None) -> list[LifecycleAction]:
        today = today or date.today()
        signals, candidates = self.collect_signals()
        return evaluate(self.store, signals, candidates, policy, today)

    def apply(self, actions: list[LifecycleAction], policy=None, today: date | None = None) -> Path:
        today = today or date.today()
        applied_surface = False
        counters: dict[str, int] = {}
        for action in actions:
            if action.action == LifecycleActionType.PROMOTE:
                skill = self.store.skills.get(action.target)
                if skill:
                    skill.status = SkillStatus.ACTIVE
                    self.store.add_or_update(skill)
            elif action.action == LifecycleActionType.FLAG_DECLINING:
                skill = self.store.skills.get(action.target)
                if skill and skill.status != SkillStatus.DECLINING:
                    skill.status = SkillStatus.DECLINING
                    self.store.add_or_update(skill)
            elif action.action == LifecycleActionType.DEPRECATE:
                skill = self.store.skills.get(action.target)
                if skill:
                    skill.status = SkillStatus.DEPRECATED
                    self.store.add_or_update(skill)
            elif action.action == LifecycleActionType.ARCHIVE:
                skill = self.store.skills.get(action.target)
                if skill:
                    skill.status = SkillStatus.ARCHIVED
                    self.store.add_or_update(skill)
            elif action.action == LifecycleActionType.PROPOSE_EMERGING:
                base = fold(action.target).replace(" ", "-")[:40] or "skill"
                n = counters.get(base, 0)
                counters[base] = n + 1
                digest = hashlib.md5(action.target.encode("utf-8")).hexdigest()[:8]
                suffix = f"-{n}" if n else ""
                skill = Skill(
                    skill_id=f"cus__auto_{digest}{suffix}",
                    name=action.target.strip().title(),
                    tier=SkillTier.CUSTOM,
                    status=SkillStatus.PROVISIONAL,
                )
                self.store.add_or_update(skill)
                applied_surface = True

        snapshot_dir = self.data_dir / "snapshots" / today.isoformat()
        self.store.write_snapshot(snapshot_dir)
        self.normalizer.rebuild()

        audit = {
            "date": today.isoformat(),
            "actions": [a.model_dump(mode="json") for a in actions],
        }
        snapshot_dir.joinpath("audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
        return snapshot_dir
