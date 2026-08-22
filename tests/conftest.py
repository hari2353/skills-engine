import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "src"))

REPO_DATA = ROOT.parent / "data"


@pytest.fixture()
def client(tmp_path):
    from fastapi.testclient import TestClient

    from skills_engine.api.app import create_app

    data_dir = tmp_path / "data"
    shutil.copytree(REPO_DATA, data_dir)
    return TestClient(create_app(data_dir=data_dir))


@pytest.fixture(scope="session")
def engine_fixture():
    from skills_engine.config import Settings
    from skills_engine.engine import SkillsEngine

    return SkillsEngine(Settings(data_dir=REPO_DATA), enable_ranker=False)
