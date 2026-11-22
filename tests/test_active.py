from skills_engine.active import entropy, margin_sample, uncertainty_sample


def test_entropy_uniform_is_max():
    assert entropy([0.25, 0.25, 0.25, 0.25]) > entropy([0.9, 0.1])


def test_entropy_rejects_bad():
    try:
        entropy([])
    except ValueError:
        pass
    else:
        raise AssertionError("empty accepted")
    try:
        entropy([0.0, 0.0])
    except ValueError:
        pass
    else:
        raise AssertionError("zero-sum accepted")
    try:
        entropy([-1.0, 2.0])
    except ValueError:
        pass
    else:
        raise AssertionError("negative accepted")


def test_uncertainty_sample_picks_top_k():
    items = [
        {"id": "a", "uncertainty": 0.9},
        {"id": "b", "uncertainty": 0.1},
        {"id": "c", "uncertainty": 0.5},
    ]
    out = uncertainty_sample(items, k=2)
    assert [item["id"] for item in out] == ["a", "c"]


def test_uncertainty_sample_from_probabilities():
    items = [
        {"id": "a", "probabilities": [0.9, 0.1]},
        {"id": "b", "probabilities": [0.5, 0.5]},
    ]
    out = uncertainty_sample(items, k=1)
    assert out[0]["id"] == "b"


def test_uncertainty_sample_bounds_k():
    items = [{"id": "a", "uncertainty": 0.5}]
    assert uncertainty_sample(items, k=0) == []
    assert uncertainty_sample(items, k=5) == items
    try:
        uncertainty_sample(items, k=-1)
    except ValueError:
        pass
    else:
        raise AssertionError("negative k accepted")


def test_margin_sample():
    items = [
        {"id": "a", "probabilities": [0.9, 0.1]},
        {"id": "b", "probabilities": [0.55, 0.45]},
    ]
    out = margin_sample(items, k=1)
    assert out[0]["id"] == "b"
