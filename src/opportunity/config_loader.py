import os
from typing import Any

import yaml


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))


def _config_dir() -> str:
    return os.path.join(_repo_root(), "config", "opportunity")


def load_yaml(name: str) -> dict[str, Any]:
    path = os.path.join(_config_dir(), name)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return {}
    return data


def load_sources() -> list[dict[str, Any]]:
    data = load_yaml("sources.yaml")
    sources = data.get("sources") or []
    if not isinstance(sources, list):
        return []
    out: list[dict[str, Any]] = []
    for s in sources:
        if not isinstance(s, dict):
            continue
        out.append(
            {
                "id": s.get("id") or s.get("name") or s.get("url"),
                "name": s.get("name") or s.get("id") or "source",
                "url": s.get("url"),
                "parser": (s.get("parser") or "rss").lower(),
                "enabled": bool(s.get("enabled", True)),
                "rateLimitSeconds": float(s.get("rateLimitSeconds", 0.0)),
                "tags": s.get("tags") or [],
                "params": s.get("params") or {},
            }
        )
    return out


def load_keywords() -> dict[str, Any]:
    return load_yaml("keywords.yaml")


def load_scoring() -> dict[str, Any]:
    return load_yaml("scoring.yaml")
