import hashlib
import re

import numpy as np

TOKEN_RE = re.compile(r"[a-z0-9]+")


def _grams(text: str) -> list[str]:
    tokens = TOKEN_RE.findall(text.lower())
    return tokens + [f"{a} {b}" for a, b in zip(tokens, tokens[1:])]


class HashingEmbedder:
    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for gram in _grams(text):
            digest = hashlib.md5(gram.encode("utf-8")).digest()
            head = int.from_bytes(digest[:8], "little")
            sign = 1.0 if digest[8] & 1 else -1.0
            vec[head % self.dim] += sign
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm else vec

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.stack([self.embed(t) for t in texts])


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2") -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def embed(self, text: str) -> np.ndarray:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 384), dtype=np.float32)
        return np.asarray(self.model.encode(texts, normalize_embeddings=True), dtype=np.float32)


def get_embedder(backend: str):
    if backend == "sentence_transformers":
        return SentenceTransformerEmbedder()
    return HashingEmbedder()
