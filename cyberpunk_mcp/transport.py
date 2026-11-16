"""CET file protocol, session leases, cancellation and ownership locks."""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
import threading
import time

from .errors import GameplayError
from .files import atomic_json, file_lock, identifier, read_json


class Bridge:
    def __init__(self, runtime: Path, competing_locks: list[Path] | None = None):
        self.root, self.competing_locks = runtime, competing_locks
        self.session = None
        self.stack = None
        self._cancel = threading.Event()
        self._closed = threading.Event()
        self._requests = threading.Lock()
        self._lifecycle = threading.RLock()
        self._pulse = threading.Thread(target=self._heartbeat, daemon=True)
        self._pulse.start()

    def state(self):
        state = read_json(self.root / "state.json")
        if state.get("protocol") != 1 or time.time() - state.get("timestamp", 0) > 4:
            raise GameplayError(
                "Cyberpunk MCP heartbeat is stale or incompatible; reload its CET mod"
            )
        return state

    def _heartbeat(self):
        while not self._closed.wait(0.5):
            if self.session and not self._cancel.is_set():
                try:
                    atomic_json(
                        self.root / "lease.json",
                        {"session": self.session, "timestamp": time.time()},
                    )
                except OSError:
                    pass

    def begin(self):
        if self.session:
            state = self.state()
            if state.get("session") == self.session and not self._cancel.is_set():
                return state
            if state.get("session") == self.session:
                raise GameplayError(
                    "Stop is being processed; wait for the runtime to release control"
                )
            self.release()
        stack = ExitStack()
        try:
            stack.enter_context(file_lock(self.root / "controller.lock"))
            for path in self.competing_locks or []:
                stack.enter_context(file_lock(path))
            state = self.state()
            if state.get("session"):
                # Owning the OS locks proves no live controller owns this
                # leftover game session. Release it before taking a new lease.
                atomic_json(
                    self.root / "stop.json",
                    {"session": state["session"], "id": identifier("stop")},
                )
                deadline = time.monotonic() + 1.5
                while self.state().get("session") and time.monotonic() < deadline:
                    time.sleep(0.025)
                if self.state().get("session"):
                    raise GameplayError(
                        "Waiting for an abandoned game session to release control"
                    )
            self.session = identifier("session")
            self._cancel.clear()
            atomic_json(
                self.root / "lease.json",
                {"session": self.session, "timestamp": time.time()},
            )
            self.stack = stack
            return self.command("begin")
        except BaseException:
            self.session = None
            self.stack = None
            stack.close()
            raise

    def command(self, kind, timeout=40, **arguments):
        if not self.session:
            raise GameplayError("Begin a gameplay session first")
        with self._requests:
            if self._cancel.is_set() and kind != "end":
                raise GameplayError("Operation stopped")
            state = self.state()
            request = {
                "id": identifier("command"),
                "boot": state["boot"],
                "session": self.session,
                "kind": kind,
                "arguments": arguments,
                "expires": time.time() + timeout,
            }
            atomic_json(self.root / "command.json", request)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self._cancel.is_set() and kind != "end":
                    raise GameplayError("Operation stopped")
                try:
                    response = read_json(self.root / "response.json")
                except GameplayError:
                    response = {}
                if response.get("id") == request["id"]:
                    if (
                        response.get("session") != self.session
                        or response.get("boot") != request["boot"]
                    ):
                        raise GameplayError("Stale command response")
                    if not response.get("ok"):
                        raise GameplayError(
                            response.get("error", "Game command failed")
                        )
                    return response["result"]
                current = self.state()
                if current["boot"] != request["boot"]:
                    raise GameplayError("CET restarted during the operation")
                time.sleep(0.025)
            self.stop()
            raise GameplayError(f"{kind} timed out; stop requested")

    def stop(self, release_when_stopped=True):
        self._cancel.set()
        if self.session:
            session = self.session
            try:
                atomic_json(
                    self.root / "stop.json",
                    {"session": session, "id": identifier("stop")},
                )
            except OSError:
                # Stop renewing the lease even if Windows refuses the stop file.
                # The game-side watchdog then releases gameplay ownership within 5 s.
                pass

            def release_after_stop():
                deadline = time.monotonic() + 6
                while self.session == session and time.monotonic() < deadline:
                    try:
                        if self.state().get("session") != session:
                            break
                    except GameplayError:
                        pass
                    time.sleep(0.05)
                with self._lifecycle:
                    if self.session == session:
                        self.release()

            if release_when_stopped:
                threading.Thread(target=release_after_stop, daemon=True).start()

    def release(self):
        with self._lifecycle:
            self.session = None
            if self.stack:
                self.stack.close()
                self.stack = None

    def end(self):
        try:
            if self.session and self.state().get("session") != self.session:
                return {"released": True}
            return self.command("end") if self.session else {"session": None}
        finally:
            self.release()

    def close(self):
        self.stop()
        self._closed.set()
        self._pulse.join(timeout=1)
        deadline = time.monotonic() + 1
        while self.session and time.monotonic() < deadline:
            try:
                if self.state().get("session") != self.session:
                    break
            except GameplayError:
                break
            time.sleep(0.025)
        self.release()
