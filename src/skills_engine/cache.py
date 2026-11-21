"""Tenant-isolated query cache + per-tenant budget kill-switch."""

from __future__ import annotations

import re
import time
from collections import OrderedDict
from typing import Callable

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE = re.compile(r"\s+")


def normalize_key(text: str) -> str:
    """Lowercase, strip punctuation, sort unique tokens.

    Tradeoff: token order stops mattering ("risk model" hits "model risk"),
    so paraphrase-level hits stay predictable without a model. Different
    tokens still miss by design.
    """
    tokens = sorted(set(_SPACE.sub(" ", _PUNCT.sub(" ", text.lower())).split()))
    return " ".join(tokens)


class SemanticCache:
    def __init__(self, max_entries: int = 256, ttl_seconds: float = 3600,
                 clock: Callable[[], float] = time.time) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self._entries: OrderedDict[tuple[str, str], tuple[float, object]] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def get(self, tenant: str, text: str):
        key = (tenant, normalize_key(text))
        entry = self._entries.get(key)
        if entry is None:
            self.misses += 1
            return None
        stored_at, value = entry
        if self.clock() - stored_at >= self.ttl_seconds:
            del self._entries[key]
            self.misses += 1
            return None
        self._entries.move_to_end(key)
        self.hits += 1
        return value

    def put(self, tenant: str, text: str, value) -> None:
        key = (tenant, normalize_key(text))
        self._entries[key] = (self.clock(), value)
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)
            self.evictions += 1

    def get_or_compute(self, tenant: str, text: str, compute: Callable[[], object]):
        hit = self.get(tenant, text)
        if hit is not None:
            return hit
        value = compute()  # exceptions are never cached
        self.put(tenant, text, value)
        return value

    def stats(self) -> dict:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "size": len(self._entries),
        }


class BudgetedRouter:
    def __init__(self, per_tenant_limit: int = 100) -> None:
        if per_tenant_limit < 0:
            raise ValueError("per_tenant_limit must be >= 0")
        self.per_tenant_limit = per_tenant_limit
        self._used: dict[str, int] = {}

    def call(self, tenant: str, fn: Callable[[], object], fallback=None):
        used = self._used.get(tenant, 0)
        if used >= self.per_tenant_limit:
            return fallback() if callable(fallback) else fallback
        self._used[tenant] = used + 1
        return fn()

    def remaining(self, tenant: str) -> int:
        return max(self.per_tenant_limit - self._used.get(tenant, 0), 0)

    def reset(self, tenant: str) -> None:
        self._used.pop(tenant, None)
