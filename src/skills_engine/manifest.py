"""Agent skill manifest parsing (cross-pollinated from databricks/databricks-agent-skills).

A skill manifest declares a reusable agent skill: name, description, version,
inputs, outputs and the tools it may call. This module validates and
normalizes such manifests with no YAML/JSON dependency beyond the standard
library.
"""

from __future__ import annotations

import re

_REQUIRED = ("name", "description", "version")
_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def parse_manifest(raw: dict) -> dict:
    """Validate and normalize a skill manifest dict."""
    if not isinstance(raw, dict):
        raise TypeError("manifest must be a dict")
    for field in _REQUIRED:
        if field not in raw or not str(raw[field]).strip():
            raise ValueError(f"missing required field: {field}")
    version = str(raw["version"]).strip()
    if not _SEMVER.match(version):
        raise ValueError(f"version must be semver (x.y.z), got {version!r}")

    def _list_of_str(value, field_name):
        if value is None:
            return []
        if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
            raise ValueError(f"{field_name} must be a list of strings")
        return [x.strip() for x in value if x.strip()]

    manifest = {
        "name": str(raw["name"]).strip(),
        "description": str(raw["description"]).strip(),
        "version": version,
        "inputs": _list_of_str(raw.get("inputs"), "inputs"),
        "outputs": _list_of_str(raw.get("outputs"), "outputs"),
        "tools": _list_of_str(raw.get("tools"), "tools"),
    }
    if "entrypoint" in raw and raw["entrypoint"] is not None:
        if not isinstance(raw["entrypoint"], str) or not raw["entrypoint"].strip():
            raise ValueError("entrypoint must be a non-empty string")
        manifest["entrypoint"] = raw["entrypoint"].strip()
    return manifest
