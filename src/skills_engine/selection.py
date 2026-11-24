"""Deterministic coreset selection (DataPerf cross-pollination).

Cross-pollinated from harvard-edge/dataperf-speech-example: when a fixed
model must be trained on a budget of examples, pick the subset deliberately
instead of at random, and report per-group coverage so a dominant group
cannot hide a missing tail.
"""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Callable, Iterable

Item = dict


def _group_key(item: Item, group_key: Callable[[Item], object]) -> object:
    return group_key(item)


def select_coreset(
    items: list[Item],
    budget: int,
    *,
    group_key: Callable[[Item], object] = lambda item: item.get("group"),
    seed: int = 0,
) -> list[Item]:
    """Pick ``budget`` items with proportional group coverage.

    Groups are filled round-robin by largest remainder so no group is
    starved; within a group the order is a seeded shuffle, making the
    selection reproducible. ``budget`` may be 0 or len(items)."""
    if budget < 0:
        raise ValueError("budget must be >= 0")
    if budget > len(items):
        raise ValueError("budget cannot exceed len(items)")
    if not items or budget == 0:
        return []
    if budget == len(items):
        return list(items)

    groups: dict[object, list[Item]] = defaultdict(list)
    for item in items:
        groups[group_key(item)].append(item)

    rng = random.Random(seed)
    for members in groups.values():
        rng.shuffle(members)

    # Largest-remainder allocation of the budget across groups.
    total = len(items)
    exact = {g: budget * len(members) / total for g, members in groups.items()}
    counts = {g: int(value) for g, value in exact.items()}
    remainder = budget - sum(counts.values())
    order = sorted(groups, key=lambda g: (-(exact[g] - counts[g]), str(g)))
    for g in order[:remainder]:
        counts[g] += 1

    selected: set[int] = set()
    index = {id(item): i for i, item in enumerate(items)}
    for group, members in groups.items():
        for member in members[: counts[group]]:
            selected.add(index[id(member)])

    return [item for i, item in enumerate(items) if i in selected]


def coreset_report(
    selected: Iterable[Item],
    all_items: Iterable[Item],
    *,
    group_key: Callable[[Item], object] = lambda item: item.get("group"),
) -> dict:
    """Per-group coverage counts for a selected coreset."""
    all_counts: dict[object, int] = defaultdict(int)
    selected_counts: dict[object, int] = defaultdict(int)
    for item in all_items:
        all_counts[group_key(item)] += 1
    for item in selected:
        selected_counts[group_key(item)] += 1
    groups = sorted(all_counts, key=lambda g: str(g))
    return {
        "total": sum(all_counts.values()),
        "selected": sum(selected_counts.values()),
        "groups": {
            str(g): {
                "available": all_counts[g],
                "selected": selected_counts[g],
                "coverage": round(selected_counts[g] / all_counts[g], 4) if all_counts[g] else 0.0,
            }
            for g in groups
        },
    }
