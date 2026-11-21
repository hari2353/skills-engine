from skills_engine.selection import coreset_report, select_coreset


def make_items():
    return [
        {"id": f"a{i}", "group": "A"} for i in range(6)
    ] + [
        {"id": f"b{i}", "group": "B"} for i in range(2)
    ]


def test_budget_zero_returns_empty():
    assert select_coreset(make_items(), 0) == []


def test_budget_all_returns_copy():
    items = make_items()
    assert select_coreset(items, len(items)) == items


def test_budget_cannot_exceed():
    try:
        select_coreset(make_items(), 100)
    except ValueError:
        pass
    else:
        raise AssertionError("oversized budget accepted")


def test_selection_is_deterministic():
    items = make_items()
    first = select_coreset(items, 4, seed=7)
    second = select_coreset(items, 4, seed=7)
    assert [i["id"] for i in first] == [i["id"] for i in second]


def test_minority_group_gets_coverage():
    items = make_items()
    selected = select_coreset(items, 4, seed=1)
    groups = {i["group"] for i in selected}
    assert "B" in groups
    assert len(selected) == 4


def test_coreset_report_counts():
    items = make_items()
    selected = select_coreset(items, 4, seed=1)
    report = coreset_report(selected, items)
    assert report["total"] == 8
    assert report["selected"] == 4
    assert set(report["groups"]) == {"A", "B"}
    assert report["groups"]["A"]["available"] == 6
    assert report["groups"]["B"]["available"] == 2


def test_empty_items():
    assert select_coreset([], 0) == []
    assert coreset_report([], [])["total"] == 0
