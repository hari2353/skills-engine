import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from .market import ArbeitnowProvider, postings_to_events

MARKET_COLUMNS = ["skill_ref", "demand", "content_coverage"]


def append_events(data_dir: Path, events: list[dict]) -> Path:
    usage_path = data_dir / "usage_log.jsonl"
    usage_path.parent.mkdir(parents=True, exist_ok=True)
    with usage_path.open("a", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")
    return usage_path


def update_market_csv(data_dir: Path, resolved_counts: Counter) -> tuple[Path, dict[str, float]]:
    market_path = data_dir / "market_signals.csv"
    existing: dict[str, dict[str, float]] = {}
    if market_path.exists():
        with market_path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                existing[row["skill_ref"]] = {
                    "demand": float(row.get("demand", 0) or 0),
                    "coverage": float(row.get("content_coverage", 0) or 0),
                }
    total = sum(resolved_counts.values()) or 1
    new_demand = {ref: round(count / total, 4) for ref, count in resolved_counts.items()}
    merged: dict[str, dict[str, float]] = {}
    for ref, values in existing.items():
        merged[ref] = dict(values)
    for ref, demand in new_demand.items():
        current = merged.setdefault(ref, {"demand": 0.0, "coverage": 0.0})
        current["demand"] = round(max(current["demand"], demand), 4)

    market_path.parent.mkdir(parents=True, exist_ok=True)
    with market_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MARKET_COLUMNS)
        writer.writeheader()
        for ref in sorted(merged):
            writer.writerow(
                {
                    "skill_ref": ref,
                    "demand": merged[ref]["demand"],
                    "content_coverage": merged[ref]["coverage"],
                }
            )
    return market_path, new_demand


def run(provider, engine, data_dir: Path, pages: int = 1) -> dict:
    postings = provider.fetch_postings(pages=pages)
    events = postings_to_events(engine, postings, source=provider.name)
    append_events(data_dir, events)
    resolved_counts = Counter(e["skill_id"] for e in events if e["type"] == "resolved")
    unresolved_count = sum(1 for e in events if e["type"] == "unresolved")
    market_path, new_demand = update_market_csv(data_dir, resolved_counts)
    return {
        "provider": provider.name,
        "postings": len(postings),
        "resolved_events": int(sum(resolved_counts.values())),
        "unresolved_events": unresolved_count,
        "distinct_skills": len(resolved_counts),
        "new_demand_updates": new_demand,
        "usage_log": str(data_dir / "usage_log.jsonl"),
        "market_csv": str(market_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest labor-market postings into skills signals")
    parser.add_argument("--provider", choices=["arbeitnow"], default="arbeitnow")
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    from skills_engine.config import Settings
    from skills_engine.engine import SkillsEngine

    data_dir = args.data_dir or Settings().data_dir
    engine = SkillsEngine(Settings(data_dir=data_dir), enable_ranker=False)
    provider = ArbeitnowProvider()
    print(json.dumps(run(provider, engine, data_dir, pages=args.pages), indent=2))


if __name__ == "__main__":
    main()
