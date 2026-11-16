"""Install, diagnose or serve the standalone Cyberpunk gameplay MCP."""

from __future__ import annotations

import argparse
from contextlib import closing
import importlib
import json
import os
from pathlib import Path
import sys

from .config import default_home, load_config
from .errors import GameplayError
from .installation import install as install
from .library import Library
from .transport import Bridge


def make_bridge(config):
    return Bridge(
        Path(config["runtime"]), [Path(p) for p in config.get("competing_locks", [])]
    )


def serve(config):
    # Initialize native capture on the main thread before starting heartbeat or
    # operation threads. Keep doctor independent of the image dependencies.
    importlib.import_module("windows_capture")
    from .controller import Gameplay
    from .images import CameraImages
    from .server import make_server

    with closing(make_bridge(config)) as bridge:
        library = Library(Path(config["data_root"]))
        controller = Gameplay(
            bridge, library, CameraImages(library), config.get("bindings")
        )
        try:
            make_server(controller).run(transport="stdio")
        finally:
            controller.stop()


def main(argv=None):
    home = default_home()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=home / ".local/cyberpunk-mcp.json"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    installer = commands.add_parser("install")
    installer.add_argument(
        "--game-root",
        type=Path,
        default=os.environ.get("CYBERPUNK_GAME_ROOT"),
        required=not os.environ.get("CYBERPUNK_GAME_ROOT"),
    )
    installer.add_argument(
        "--data-root",
        type=Path,
        help="Library directory; preserves the configured path on reinstall",
    )
    commands.add_parser("doctor")
    commands.add_parser("serve")
    args = parser.parse_args(argv)
    try:
        if args.command == "install":
            print(
                json.dumps(
                    install(args.game_root, args.data_root, args.config), indent=2
                )
            )
            return 0
        config = load_config(args.config)
        if args.command == "doctor":
            with closing(make_bridge(config)) as bridge:
                state = bridge.state()
                if state.get("product") != "cyberpunk_mcp":
                    raise GameplayError("Configuration points to a different CET mod")
                report = {
                    "connected": True,
                    "gameplay_ready": state.get("ready", False),
                    "state": state,
                }
                print(json.dumps(report, indent=2))
            return 0
        serve(config)
        return 0
    except (GameplayError, OSError, ValueError, KeyError, ImportError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
