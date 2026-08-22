from pathlib import Path

from skills_engine.config import Settings
from skills_engine.engine import SkillsEngine
from skills_engine.evals.runner import run_extraction_eval, run_resolution_eval, write_report

DATA = Path(__file__).resolve().parents[1] / "data"


def make_engine():
    return SkillsEngine(Settings(data_dir=DATA), enable_ranker=False)


def test_extraction_golden_baseline_passes_gate(tmp_path):
    engine = make_engine()
    result = run_extraction_eval(engine, DATA / "evals" / "golden_baseline.csv")
    write_report(tmp_path, result, {"accuracy": 1.0})
    assert (tmp_path / "latest.json").exists()
    assert result["f1"] >= 0.99, result


def test_resolution_golden_accuracy():
    result = run_resolution_eval(make_engine(), DATA / "evals" / "resolution_golden.csv")
    assert result["accuracy"] >= 0.9, result["misses"]
