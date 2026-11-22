from skills_engine.manifest import parse_manifest


def test_parses_minimal_manifest():
    out = parse_manifest({"name": "summarize", "description": "Summarize text.", "version": "1.2.3"})
    assert out["name"] == "summarize"
    assert out["version"] == "1.2.3"
    assert out["inputs"] == []
    assert out["tools"] == []


def test_parses_full_manifest():
    raw = {
        "name": "extract",
        "description": "Extract entities.",
        "version": "0.1.0",
        "inputs": ["text"],
        "outputs": ["entities"],
        "tools": ["read_file"],
        "entrypoint": "run",
    }
    out = parse_manifest(raw)
    assert out["inputs"] == ["text"]
    assert out["outputs"] == ["entities"]
    assert out["tools"] == ["read_file"]
    assert out["entrypoint"] == "run"


def test_rejects_missing_required():
    for field in ("name", "description", "version"):
        raw = {"name": "x", "description": "y", "version": "1.0.0"}
        del raw[field]
        try:
            parse_manifest(raw)
        except ValueError:
            continue
        raise AssertionError(f"missing {field} accepted")


def test_rejects_bad_version():
    try:
        parse_manifest({"name": "x", "description": "y", "version": "1.0"})
    except ValueError:
        pass
    else:
        raise AssertionError("bad version accepted")


def test_rejects_bad_lists():
    try:
        parse_manifest({"name": "x", "description": "y", "version": "1.0.0", "tools": "read_file"})
    except ValueError:
        pass
    else:
        raise AssertionError("string tools accepted")
    try:
        parse_manifest({"name": "x", "description": "y", "version": "1.0.0", "tools": [1]})
    except ValueError:
        pass
    else:
        raise AssertionError("non-string tools accepted")


def test_rejects_non_dict():
    try:
        parse_manifest("nope")
    except TypeError:
        pass
    else:
        raise AssertionError("non-dict accepted")
