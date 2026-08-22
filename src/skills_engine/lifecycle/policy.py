from datetime import date

from ..taxonomies.models import SkillStatus
from ..text import fold
from .models import Candidate, LifecycleAction, LifecycleActionType, SkillSignals


def recency_weight(days_since_last_seen: float, half_life_days: float) -> float:
    return 0.5 ** (max(days_since_last_seen, 0.0) / half_life_days)


def health_score(signals: SkillSignals, policy, today: date) -> tuple[float, dict[str, float]]:
    if signals.last_seen is None:
        days = None
        recency = 0.0
    else:
        days = (today - signals.last_seen).days
        recency = recency_weight(days, policy.half_life_days)
    score = (
        policy.recency_weight * recency
        + policy.demand_weight * signals.market_demand
        + policy.coverage_weight * signals.content_coverage
    )
    metrics = {
        "health_score": round(score, 4),
        "recency_component": round(recency, 4),
        "market_demand": signals.market_demand,
        "content_coverage": signals.content_coverage,
        "mentions": float(signals.mentions),
        "days_since_last_seen": float(days) if days is not None else -1.0,
    }
    return round(score, 4), metrics


def _existing_surfaces(store) -> set[str]:
    surfaces: set[str] = set()
    for s in store.skills.values():
        surfaces.add(fold(s.name))
        for alias in s.aliases:
            surfaces.add(fold(alias))
    return surfaces


def evaluate(store, signals_by_skill: dict[str, SkillSignals], candidates: dict[str, Candidate], policy, today: date) -> list[LifecycleAction]:
    actions: list[LifecycleAction] = []
    existing = _existing_surfaces(store)

    for skill in store.skills.values():
        sig = signals_by_skill.get(skill.skill_id)

        if skill.status == SkillStatus.PROVISIONAL:
            cand = candidates.get(fold(skill.name))
            mentions = cand.mentions if cand else (sig.mentions if sig else 0)
            if mentions >= policy.promote_min_mentions:
                actions.append(
                    LifecycleAction(
                        action=LifecycleActionType.PROMOTE,
                        target=skill.skill_id,
                        reason=f"provisional skill reached {mentions} mentions >= promote threshold {policy.promote_min_mentions}",
                        metrics={"mentions": float(mentions)},
                    )
                )
            continue

        if sig is None or (sig.mentions == 0 and sig.market_demand == 0.0 and sig.content_coverage == 0.0 and sig.last_seen is None):
            continue

        score, metrics = health_score(sig, policy, today)
        days = metrics["days_since_last_seen"]

        if skill.status in (SkillStatus.ACTIVE, SkillStatus.DECLINING):
            if score < policy.declining_threshold:
                actions.append(
                    LifecycleAction(
                        action=LifecycleActionType.FLAG_DECLINING,
                        target=skill.skill_id,
                        reason=f"health score {score} below declining threshold {policy.declining_threshold}",
                        metrics=metrics,
                    )
                )
                if skill.status == SkillStatus.DECLINING and days >= policy.retire_after_days:
                    actions.append(
                        LifecycleAction(
                            action=LifecycleActionType.DEPRECATE,
                            target=skill.skill_id,
                            reason=f"declining for {int(days)} days >= retire horizon {policy.retire_after_days}; soft-deleted (kept for audit)",
                            metrics=metrics,
                        )
                    )
        elif skill.status == SkillStatus.DEPRECATED and days >= policy.archive_after_days:
            actions.append(
                LifecycleAction(
                    action=LifecycleActionType.ARCHIVE,
                    target=skill.skill_id,
                    reason=f"deprecated {int(days)} days >= archive horizon {policy.archive_after_days}",
                    metrics=metrics,
                )
            )

    for key, cand in sorted(candidates.items()):
        if fold(cand.surface) in existing:
            continue
        if cand.mentions >= policy.emerge_min_mentions:
            actions.append(
                LifecycleAction(
                    action=LifecycleActionType.PROPOSE_EMERGING,
                    target=cand.surface,
                    reason=f"unresolved surface '{cand.surface}' appeared {cand.mentions} times >= emergence threshold {policy.emerge_min_mentions}",
                    metrics={"mentions": float(cand.mentions)},
                )
            )

    return actions
