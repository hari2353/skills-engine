import csv
import json
from pathlib import Path

from ..inference.contexts import ContextType
from ..text import fold


def load_golden(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _fold_index(engine) -> tuple[dict[str, str], dict[str, set[str]]]:
    """fold(surface) -> owning skill_id (names + aliases), and
    fold(canonical name) -> {skill_id} for cross-tier name classes."""
    by_surface: dict[str, str] = {}
    by_name: dict[str, set[str]] = {}
    for s in engine.store.skills.values():
        fname = fold(s.name)
        by_surface.setdefault(fname, s.skill_id)
        by_name.setdefault(fname, set()).add(s.skill_id)
        for a in s.aliases:
            by_surface.setdefault(fold(a), s.skill_id)
    return by_surface, by_name


def run_extraction_eval(engine, golden_path: Path) -> dict:
    tp = fp = fn = 0
    ltp = lfp = lfn = 0
    per_row: list[dict] = []
    by_surface, by_name = _fold_index(engine)
    for row in load_golden(golden_path):
        expected = {e.strip() for e in row["expected_canonical"].split("|") if e.strip()}
        result = engine.infer(row["text"], ContextType(row["context_type"]))
        predicted = {s["canonical_name"] for s in result["skills"] if s.get("canonical_name")}
        tp += len(predicted & expected)
        fp += len(predicted - expected)
        fn += len(expected - predicted)
        # lenient scoring: an expected name matches when a predicted skill is
        # the same canonical skill under any name or alias (cross-tier
        # duplicates of the same canonical name count as one)
        pred_names = [fold(s["canonical_name"]) for s in result["skills"] if s.get("canonical_name")]
        exp_classes = []
        for e in expected:
            fe = fold(e)
            ids = set()
            if fe in by_surface:
                ids.add(by_surface[fe])
            ids |= by_name.get(fe, set())
            cls = {fold(engine.store.skills[i].name) for i in ids} or {fe}
            exp_classes.append(cls)
        row_tp = sum(1 for cls in exp_classes if any(pn in cls for pn in pred_names))
        ltp += row_tp
        lfn += len(exp_classes) - row_tp
        lfp += sum(1 for pn in pred_names if not any(pn in cls for cls in exp_classes))
        per_row.append(
            {
                "text": row["text"],
                "context_type": row["context_type"],
                "expected": sorted(expected),
                "predicted": sorted(predicted),
                "match": predicted == expected,
                "lenient_match": row_tp > 0,
            }
        )
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    l_precision = ltp / (ltp + lfp) if (ltp + lfp) else 0.0
    l_recall = ltp / (ltp + lfn) if (ltp + lfn) else 0.0
    l_f1 = 2 * l_precision * l_recall / (l_precision + l_recall) if (l_precision + l_recall) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "lenient_precision": round(l_precision, 4),
        "lenient_recall": round(l_recall, 4),
        "lenient_f1": round(l_f1, 4),
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
