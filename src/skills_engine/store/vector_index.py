import numpy as np


class VectorIndex:
    def __init__(self, embedder) -> None:
        self.embedder = embedder
        self.keys: list[tuple[str, str]] = []
        self.matrix: np.ndarray | None = None

    def build(self, items: list[tuple[str, str]]) -> None:
        self.keys = items
        self.matrix = self.embedder.embed_batch([surface for _, surface in items])

    def search(self, query: str, k: int = 5) -> list[tuple[str, str, float]]:
        if self.matrix is None or len(self.keys) == 0:
            return []
        q = self.embedder.embed(query)
        sims = self.matrix @ q
        n = len(sims)
        k_eff = min(k, n)
        if k_eff < n:
            top = np.argpartition(-sims, k_eff - 1)[:k_eff]
        else:
            top = np.arange(n)
        ordered = top[np.argsort(-sims[top])]
        return [(self.keys[i][0], self.keys[i][1], float(sims[i])) for i in ordered]
