"""Portable writable defaults and validated, configuration-relative paths."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .errors import GameplayError


def default_home():
    override = os.environ.get("CYBERPUNK_MCP_HOME")
    if override:
        return Path(override).expanduser().resolve()
    project = Path(__file__).resolve().parents[1]
    if (project / "pyproject.toml").is_file():
        return project
    # A wheel must never write libraries or settings into site-packages.
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share"))
    return base / "Ghostline" / "cyberpunk-mcp"


def resolve_path(value, base, name):
    if not isinstance(value, str) or not value.strip():
        raise GameplayError(f"{name} must be a nonempty path string")
    path = Path(value).expanduser()
    return (path if path.is_absolute() else base / path).resolve()


def read_settings(path):
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        raise GameplayError("Configuration must be a JSON object")
    if type(config.get("schema_version")) is not int or config["schema_version"] != 1:
        raise GameplayError("Unsupported configuration schema_version; expected 1")
    if not isinstance(config.get("bindings", {}), dict):
        raise GameplayError("bindings must be an object")
    return config


def load_config(path):
    path = path.expanduser().resolve()
    config = read_settings(path)
    for name in ("runtime", "data_root"):
        config[name] = str(resolve_path(config.get(name), path.parent, name))
    locks = config.get("competing_locks", [])
    if not isinstance(locks, list):
        raise GameplayError("competing_locks must be an array of paths")
    config["competing_locks"] = [
        str(resolve_path(lock, path.parent, "competing_locks")) for lock in locks
    ]
    return config
