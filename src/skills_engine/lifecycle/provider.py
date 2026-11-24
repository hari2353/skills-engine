import csv
import json
from datetime import date
from pathlib import Path

from .models import Candidate, SkillSignals


def load_usage_signals(usage_log: Path) -> tuple[dict[str, SkillSignals], dict[str, Candidate]]:
    by_skill: dict[str, SkillSignals] = {}
    candidates: dict[str, Candidate] = {}
    if not usage_log.exists():
        return by_skill, candidates
    with usage_log.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            day = _parse_date(event.get("ts"))
            if event.get("type") == "resolved":
                sid = event["skill_id"]
                sig = by_skill.setdefault(sid, SkillSignals())
                sig.mentions += 1
                if day and (sig.last_seen is None or day > sig.last_seen):
                    sig.last_seen = day
            elif event.get("type") == "unresolved":
                raw = str(event.get("raw", "")).strip()
                if not raw:
                    continue
                cand = candidates.setdefault(raw.lower(), Candidate(surface=raw))
                cand.mentions += 1
                if day and (cand.last_seen is None or day > cand.last_seen):
                    cand.last_seen = day
    return by_skill, candidates


def load_skill_events(usage_log: Path, skill_id: str) -> list[date]:
    """Resolved-event dates for one skill, for capped-window trend analysis."""
    events: list[date] = []
    if not usage_log.exists():
        return events
    with usage_log.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "resolved" and event.get("skill_id") == skill_id:
                day = _parse_date(event.get("ts"))
                if day:
                    events.append(day)
    return events


def load_feedback_signals(path: Path) -> dict[str, SkillSignals]:
    """Human accept/reject events from the bandit log, per resolved skill_id."""
    by_skill: dict[str, SkillSignals] = {}
    if not path.exists():
        return by_skill
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            sid = event.get("skill_id")
            if not sid:
                continue
            sig = by_skill.setdefault(sid, SkillSignals())
            if event.get("accepted"):
                sig.acceptances += 1
            else:
                sig.rejections += 1
    return by_skill


def load_market_signals(market_csv: Path) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    if not market_csv.exists():
        return out
    with market_csv.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            ref = row.get("skill_ref", "").strip()
            if not ref:
                continue
            out[ref] = {
                "demand": float(row.get("demand", 0) or 0),
                "coverage": float(row.get("content_coverage", 0) or 0),
            }
    return out


def merge_signals(
    skill_signals: dict[str, SkillSignals], market: dict[str, dict[str, float]], store
) -> dict[str, SkillSignals]:
    merged = dict(skill_signals)
    id_to_key = {}
    for s in store.skills.values():
        id_to_key[s.skill_id] = s.skill_id
        id_to_key[s.name.lower()] = s.skill_id
    for ref, values in market.items():
        sid = id_to_key.get(ref) or id_to_key.get(ref.lower())
        if sid is None:
            continue
        sig = merged.setdefault(sid, SkillSignals())
        sig.market_demand = values["demand"]
        sig.content_coverage = values["coverage"]
    return merged


def _parse_date(value):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None
