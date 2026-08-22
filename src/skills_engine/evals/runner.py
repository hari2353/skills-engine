import csv
import json
from pathlib import Path

from ..inference.contexts import ContextType


def load_golden(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def run_extraction_eval(engine, golden_path: Path) -> dict:
    tp = fp = fn = 0
    per_row: list[dict] = []
    for row in load_golden(golden_path):
        expected = {e.strip() for e in row["expected_canonical"].split("|") if e.strip()}
        result = engine.infer(row["text"], ContextType(row["context_type"]))
        predicted = {s["canonical_name"] for s in result["skills"] if s.get("canonical_name")}
        tp += len(predicted & expected)
        fp += len(predicted - expected)
        fn += len(expected - predicted)
        per_row.append(
            {
                "text": row["text"],
                "context_type": row["context_type"],
                "expected": sorted(expected),
                "predicted": sorted(predicted),
                "match": predicted == expected,
            }
        )
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "rows": per_row,
    }


def run_resolution_eval(engine, golden_path: Path) -> dict:
    rows = load_golden(golden_path)
    correct = 0
    misses: list[dict] = []
    for row in rows:
        result = engine.normalize(row["input_name"])
        ok = result["skill_id"] == row["expected_skill_id"]
        correct += ok
        if not ok:
            misses.append(
                {
                    "input": row["input_name"],
                    "expected_skill_id": row["expected_skill_id"],
                    "got_skill_id": result["skill_id"],
                    "method": result["method"],
                }
            )
    total = len(rows)
    accuracy = correct / total if total else 0.0
    return {"accuracy": round(accuracy, 4), "correct": correct, "total": total, "misses": misses}


def write_report(reports_dir: Path, extraction: dict, resolution: dict) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "latest.json"
    payload = {"extraction": extraction, "resolution": resolution}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
