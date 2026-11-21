"""Tenant-isolated normalized cache + per-tenant budget kill-switch."""

from __future__ import annotations

import pytest

from skills_engine.cache import BudgetedRouter, SemanticCache, normalize_key


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_hit_and_miss() -> None:
    cache = SemanticCache()
    assert cache.get("acme", "risk model") is None
    cache.put("acme", "risk model", {"answer": 1})
    assert cache.get("acme", "risk model") == {"answer": 1}
    assert cache.stats() == {"hits": 1, "misses": 1, "evictions": 0, "size": 1}


def test_token_order_and_punctuation_are_normalized() -> None:
    cache = SemanticCache()
    cache.put("acme", "Model risk!", "v")
    assert cache.get("acme", "risk   model") == "v"
    assert normalize_key("Risk, model!") == "model risk"


def test_tenant_isolation() -> None:
    cache = SemanticCache()
    cache.put("acme", "q", "acme-answer")
    assert cache.get("other", "q") is None


def test_ttl_uses_injected_clock() -> None:
    clock = Clock()
    cache = SemanticCache(ttl_seconds=10, clock=clock)
    cache.put("acme", "q", "v")
    clock.now += 9.9
    assert cache.get("acme", "q") == "v"
    clock.now += 0.1
    assert cache.get("acme", "q") is None
    assert cache.stats()["size"] == 0


def test_lru_eviction() -> None:
    cache = SemanticCache(max_entries=2)
    cache.put("acme", "a", 1)
    cache.put("acme", "b", 2)
    cache.get("acme", "a")  # refresh a
    cache.put("acme", "c", 3)
    assert cache.get("acme", "b") is None
    assert cache.get("acme", "a") == 1
    assert cache.stats()["evictions"] == 1


def test_exceptions_are_not_cached() -> None:
    cache = SemanticCache()
    calls = []

    def boom():
        calls.append(1)
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError):
        cache.get_or_compute("acme", "q", boom)
    with pytest.raises(RuntimeError):
        cache.get_or_compute("acme", "q", boom)
    assert len(calls) == 2
    assert cache.stats()["size"] == 0


def test_budget_exhaustion_uses_fallback_without_calling_fn() -> None:
    router = BudgetedRouter(per_tenant_limit=1)
    calls = []
    assert router.call("acme", lambda: calls.append(1) or "real") == "real"
    assert router.call("acme", lambda: calls.append(1) or "real", fallback="cheap") == "cheap"
    assert calls == [1]
    assert router.remaining("acme") == 0
    assert router.remaining("other") == 1


def test_budget_reset_is_per_tenant() -> None:
    router = BudgetedRouter(per_tenant_limit=1)
    router.call("acme", lambda: 1)
    router.call("other", lambda: 2)
    router.reset("acme")
    assert router.remaining("acme") == 1
    assert router.remaining("other") == 0
