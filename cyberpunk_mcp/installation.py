"""Install only this tool's CET Lua files and preserve local settings."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil

from .config import default_home, read_settings, resolve_path
from .errors import GameplayError
from .files import atomic_json, file_lock
from .library import Library


def install(game, data, config_path):
    game = game.expanduser().resolve()
    config_path = config_path.expanduser().resolve()
    previous = read_settings(config_path) if config_path.exists() else {}
    if data is None:
        data = (
            resolve_path(previous["data_root"], config_path.parent, "data_root")
            if previous.get("data_root")
            else default_home() / "data/library"
        )
    data = data.expanduser().resolve()
    mods = game / "bin/x64/plugins/cyber_engine_tweaks/mods"
    if not mods.is_dir():
        raise GameplayError(f"No CET installation at {mods}")
    destination = mods / "cyberpunk_mcp"
    backup = None
    with file_lock(destination / "runtime/controller.lock"):
        existing = [
            destination / name
            for name in ("init.lua", "engine.lua")
            if (destination / name).exists()
        ]
        if existing:
            backup = (
                game
                / "ghostline-mod-backups"
                / ("cyberpunk-mcp-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
            )
            backup.mkdir(parents=True)
            for path in existing:
                shutil.copy2(path, backup / path.name)
        for name in ("init.lua", "engine.lua"):
            shutil.copy2(Path(__file__).parent / "cet" / name, destination / name)
    config = {
        "schema_version": 1,
        "game_root": str(game),
        "data_root": str(data),
        "runtime": str(destination / "runtime"),
        "competing_locks": [
            str(mods / name / "runtime/controller.lock")
            for name in ("game_scout", "world_location_capture")
        ],
        "bindings": {},
    }
    config["bindings"] = previous.get("bindings", {})
    atomic_json(config_path, config)
    Library(data)
    return {
        "config": str(config_path.resolve()),
        "mod": str(destination),
        "reload_required": True,
        "backup": str(backup) if backup else None,
    }
