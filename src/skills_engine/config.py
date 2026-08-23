import os
from pathlib import Path


class Settings:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or Path(__file__).resolve().parents[2] / "data"
        self.llm_base_url = os.getenv("SKILLS_LLM_BASE_URL")
        self.llm_api_key = os.getenv("SKILLS_LLM_API_KEY", "")
        self.llm_model = os.getenv("SKILLS_LLM_MODEL", "gpt-4o-mini")
        self.embedding_backend = os.getenv("SKILLS_EMBEDDING_BACKEND", "hashing")
        self.fuzzy_threshold = float(os.getenv("SKILLS_FUZZY_THRESHOLD", "0.65"))
        self.rerank_backend = os.getenv("SKILLS_RERANK_BACKEND", "lexical")
        self.rerank_candidates = int(os.getenv("SKILLS_RERANK_CANDIDATES", "8"))
        self.rerank_vec_weight = float(os.getenv("SKILLS_RERANK_VEC_WEIGHT", "0.5"))
        self.rerank_soft_threshold = float(os.getenv("SKILLS_RERANK_SOFT_THRESHOLD", "0.45"))
