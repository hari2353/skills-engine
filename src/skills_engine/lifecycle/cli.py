import argparse
import json
from datetime import date
from pathlib import Path

from .models import LifecyclePolicy
from .runner import LifecycleRunner


def main() -> None:
    parser = argparse.ArgumentParser(description="Skills lifecycle governance job")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--today", type=str, default=None)
    parser.add_argument("--apply", action="store_true", help="apply actions and write a snapshot")
    parser.add_argument(
        "--export-skills",
        type=Path,
        default=None,
        metavar="OUT_DIR",
        help="write one bounded SKILL.md per taxonomy tier (agent registries)",
    )
    args = parser.parse_args()

    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    from skills_engine.config import Settings
    from skills_engine.engine import SkillsEngine

    data_dir = args.data_dir or Settings().data_dir
    engine = SkillsEngine(Settings(data_dir=data_dir))
    if args.export_skills:
        n = engine.export_skill_md(args.export_skills)
        print(json.dumps({"exported": n, "dir": str(args.export_skills)}, indent=2))
        return
    runner = LifecycleRunner(engine.store, engine.normalizer, data_dir)
    today = date.fromisoformat(args.today) if args.today else date.today()
    policy = LifecyclePolicy()
    actions = runner.report(policy, today)

    if not args.apply:
        print(
            json.dumps({"today": today.isoformat(), "actions": [a.model_dump(mode="json") for a in actions]}, indent=2)
        )
        return

    snapshot_dir = runner.apply(actions, policy, today)
    print(
        json.dumps({"today": today.isoformat(), "applied": len(actions), "snapshot_dir": str(snapshot_dir)}, indent=2)
    )


if __name__ == "__main__":
    main()
