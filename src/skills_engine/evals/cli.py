import argparse
import json
import sys
from pathlib import Path

from .runner import run_extraction_eval, run_resolution_eval, write_report


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    from skills_engine.config import Settings
    from skills_engine.engine import SkillsEngine

    parser = argparse.ArgumentParser(description="Run golden-baseline evaluation and gate on F1")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--min-f1", type=float, default=0.8)
    parser.add_argument("--min-accuracy", type=float, default=0.9)
    args = parser.parse_args()

    data_dir = args.data_dir or Settings().data_dir
    engine = SkillsEngine(Settings(data_dir=data_dir))
    extraction = run_extraction_eval(engine, data_dir / "evals" / "golden_baseline.csv")
    resolution = run_resolution_eval(engine, data_dir / "evals" / "resolution_golden.csv")
    write_report(data_dir / "evals" / "reports", extraction, resolution)

    print(
        json.dumps(
            {
                "extraction_f1": extraction["f1"],
                "extraction_precision": extraction["precision"],
                "extraction_recall": extraction["recall"],
                "resolution_accuracy": resolution["accuracy"],
                "gate_min_f1": args.min_f1,
                "gate_min_accuracy": args.min_accuracy,
            },
            indent=2,
        )
    )
    failed = extraction["f1"] < args.min_f1 or resolution["accuracy"] < args.min_accuracy
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
