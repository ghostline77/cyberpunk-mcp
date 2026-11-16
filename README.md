# Cyberpunk MCP: normal gameplay

An independent MCP server for playing Cyberpunk 2077 with **FreeFly disabled**.
Uses ordinary Windows keyboard scan-code and relative mouse input, plus a small
read-only CET telemetry mod. It does not import or modify `game_scout`, enable
flight, teleport, change facts, hide the HUD or grant player protections.

## Installation

From this project directory (Windows, Python 3.12+ and CET required):

```powershell
.\setup.ps1 -InstallMod -GameRoot 'C:\path\to\Cyberpunk 2077' -RegisterCodex
```

This creates `.venv`, installs the separate CET mod
`mods/cyberpunk_mcp`, writes `.local/cyberpunk-mcp.json`, and optionally registers
the separate Codex MCP entry `cyberpunk_mcp`. Reinstallation backs up only this
mod's Lua files and preserves binding overrides. Installation does not reload
CET, focus the game, end another controller's session or change FreeFly.

When other capture/control work has finished, reload CET mods or restart the
game. Load a free-roam save, disable FreeFly, close CET and menus, and unpause.
Start a new Codex chat/reconnect MCP if the new server is not yet listed.

```powershell
.\.venv\Scripts\python.exe cyberpunk_mcp.py doctor
```

`doctor` reads telemetry only. `connected` means the CET heartbeat is present;
`gameplay_ready` additionally checks player attachment, loading, pause/menu,
CET overlay and FreeFly state. Foreground focus is checked by the input worker
when executing an action. Readiness cannot prove that an interaction or route
will succeed. Optional telemetry failures are reported where possible; missing
essential APIs fail readiness closed.

The server starts from any working directory:

```powershell
.\.venv\Scripts\python.exe .\cyberpunk_mcp.py serve
```

Use `--config <absolute-path>` before `serve`, `doctor` or `install` for another
installation. Game and MCP must run at the same privilege level for SendInput.
No virtual-controller driver is required. There is no gamepad backend in this
milestone.

## Agent control loop

1. `capabilities()` reads bindings and limits; `state()` reads live telemetry.
2. `observe()` captures a fresh game-window image and player/camera state.
3. Focus the game, then `begin_session()` acquires exclusive control. The agent
   never steals desktop focus. FreeFly must stay disabled.
4. `walk(forward=1, seconds=0.4)` moves forward on foot. `right=-1` strafes left.
   Optional `sprint=true` holds the sprint binding. Axes range from -1 to 1.
5. `look(mouse_dx=120, mouse_dy=0)` turns right. These are mouse counts, **not
   degrees**; measure the resulting yaw/pitch and calibrate to game sensitivity.
   `walk` also accepts mouse deltas for simultaneous movement and turning.
6. Face a door or vehicle and `interact(seconds=0.15)`. Use a longer hold if the
   visible prompt requires one. Inspect the returned image and `state.mode`;
   inputs do not select targets by entity ID or guarantee successful interaction.
7. Once `state.mode` is `vehicle`, `drive(throttle=0.3, steer=0, seconds=0.4)`
   accelerates. Negative steer goes left. Negative throttle presses brake/reverse:
   the game determines whether it brakes or reverses at the current speed.
8. Brake deliberately: e.g. `drive(throttle=-1, seconds=0.4)` or use
   `handbrake=true`. `throttle=0` releases acceleration and **coasts**.
9. `press_action(action="exit_vehicle", seconds=1)` holds the exit binding.
   `jump` and `crouch` are also supported; default crouch is a toggle.
10. `end_session()` releases ownership. If an action is still running it requests
    interruption and reports busy; retry once that action finishes.

All actions last 0.05–2 seconds. Fractional movement, throttle and steering use
200 ms keyboard duty cycles, not native analog axes. Short actions below one
cycle are correspondingly coarse; start slowly and correct from observations.
Every completed action releases its inputs and returns a fresh screenshot plus
before/after telemetry. `completed_input` means the input finished, not that a
door opened or a destination was reached. Driving requires a mounted vehicle;
the current milestone does not distinguish the driver's seat from a passenger
seat. Judge actual vehicle response from observations.

## Interruption and evidence

- `stop()` interrupts the action and ends the session. It releases agent keys;
  it does not brake a moving vehicle. Brake before ending normal driving.
- Hold **F8** during an action to interrupt directly in the input worker.
  A separate bindable CET hotkey, “Cyberpunk MCP: emergency stop”, also ends
  the runtime session. F8 has no effect when no action is running.
- Every action has a separate process that checks foreground executable,
  controller-process liveness, cancellation, runtime session/boot, heartbeat,
  readiness and expected on-foot/vehicle mode about every 20 ms. CET state is
  published about every 50 ms. File polling and OS scheduling add latency.
- The worker releases keys in `finally`, including focus loss, cancellation,
  parent exit, stale telemetry, pause/loading and FreeFly activation. Hard OS
  termination or blocked input injection cannot guarantee key-up delivery.
- Do not manually hold movement keys while an agent acts. Requested keys that
  are already down are rejected, rather than released on the user's behalf.
- Session locks exclude the existing `game_scout` and world-location capture
  controllers without modifying their files or taking over their sessions.
- Images, sidecars and action records live in
  `data/library`; `get_record(record_id)` reads saved evidence.
  Interrupted actions retain their plan, pre-action state and failure reason.

Bindings use the standard game's W/A/S/D, F, Shift, Space and C defaults.
Override `bindings` in `.local/cyberpunk-mcp.json` with integer PC scan codes if
controls were rebound; `capabilities` returns the effective mapping. Supported
codes are non-extended scan codes 1–127. Mouse sensitivity remains game-owned.

## Verification and live milestone

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_cyberpunk_mcp.py -v
```

Offline coverage exercises key release, focus/cancel/state changes, bounded
timing, duty cycles, mode gates, evidence persistence, installation isolation,
competing locks, native INPUT layout, MCP tools and the actual Lua entrypoint
with a simulated game/transport. It never synthesizes live input.

The live acceptance route is: with FreeFly off, walk to a door, interact and
visually confirm it opens; approach a vehicle and interact, confirm vehicle
mode; drive a short clear route, brake, confirm a stationary position, exit and
end the session. Save returned action IDs and screenshots as evidence. This
route needs an idle game session and has **not yet been run** for this standalone copy.

Input backend reference: [Microsoft SendInput documentation](https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-sendinput).

## Standalone layout and migration

`setup.ps1` alone prepares `.venv` without installing a game mod. Use `-InstallMod`
when the game is idle and `-RegisterCodex` to switch the existing MCP entry to this
copy. `-Python` selects a Python 3.12+ executable. Dependencies are declared in
`pyproject.toml`; CET Lua files are included as package data.
The launch wrapper works from any working directory. You can also run
`python -m cyberpunk_mcp` or the installed `cyberpunk-mcp` console command.
In a source checkout, configuration defaults to `.local/cyberpunk-mcp.json`
and new libraries to `data/library`, relative to this project. Wheel installs
use `%LOCALAPPDATA%/Ghostline/cyberpunk-mcp` (or `~/.local/share/Ghostline/cyberpunk-mcp`
on other platforms), so nothing is written into site-packages. Set `CYBERPUNK_MCP_HOME`
to override the writable home directory. Paths stored as relative strings in
configuration resolve beside that configuration file. Use `--config` before the subcommand
and `install --data-root` to override paths. Local configuration, libraries,
environments and caches are ignored by Git.

The source was copied from `H:/projects/Ghostline`, including local Lua edits.
The originals, live CET mods and MCP registration were left intact.
Existing capture libraries are not part of this source copy. To reuse one,
copy its configuration to `.local/cyberpunk-mcp.json` and retain its original
absolute `data_root` until deliberately migrating the library and image paths.
Do not copy an active SQLite database with an ordinary file copy.

Use `setup.ps1 -Development` to include test dependencies, then run offline verification:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Lua harness tests require `lua` on PATH. Offline tests do not verify live game
behavior. CET installation and MCP registration remain explicit steps.

## Code ownership

`cli.py` routes commands and owns server startup/shutdown. `config.py` validates
configuration and resolves writable paths; `installation.py` owns scoped CET
installation, backups and preserved library settings. `files.py` provides atomic
JSON and OS locks, while `transport.py` owns protocol requests, leases and stop
handling. `library.py` owns SQLite records. `images.py` handles window capture,
`controller.py` coordinates operations, and `server.py` exposes the MCP interface.
`core.py` preserves the original imports for external scripts; internal modules
import each implementation from its owner.

`validation.py` validates bounded numbers. `inputs.py` owns Windows input and its
isolated action worker. Gameplay persistence contains observations and action
evidence; geometry, scouting coverage and scout exports belong to Game Scout.
Existing databases keep their records and any old unused tables on reopen.

Reinstalling without `--data-root` retains the configured library instead of
creating a new empty one. Configuration errors are rejected before runtime
threads start. Startup failures and normal shutdown close the bridge and join
its heartbeat thread. Each tool remains independently installable.

```powershell
ruff check cyberpunk_mcp
ruff format --check cyberpunk_mcp
.\.venv\Scripts\python.exe -m pip wheel --no-deps . --wheel-dir dist
```
