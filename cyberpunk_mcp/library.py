"""Persistent gameplay observations, images and action evidence."""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3

from .errors import GameplayError
from .files import identifier, now
from .validation import number


class Library:
    def __init__(self, root: Path):
        root = root.expanduser().resolve()
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "gameplay.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS records(
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, data TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS record_kind ON records(kind);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def put(self, kind, name, data, record_id=None):
        rid = record_id or identifier(kind)
        with self.connect() as db:
            db.execute(
                """INSERT INTO records VALUES(?,?,?,?,?,?) ON CONFLICT(id)
                DO UPDATE SET name=excluded.name,updated_at=excluded.updated_at,data=excluded.data""",
                (rid, kind, name, now(), now(), json.dumps(data, allow_nan=False)),
            )
        return self.get(rid)

    def get(self, rid):
        with self.connect() as db:
            row = db.execute(
                "SELECT id,kind,name,created_at,updated_at,data FROM records WHERE id=?",
                (rid,),
            ).fetchone()
        if row is None:
            raise GameplayError(f"Unknown library ID: {rid}")
        return self._record(row)

    @staticmethod
    def _record(row):
        keys = ("id", "kind", "name", "created_at", "updated_at", "data")
        return dict(zip(keys, (*row[:5], json.loads(row[5]))))

    def list(self, kind=None, query="", limit=50):
        limit = int(number(limit, 1, 200, "limit"))
        with self.connect() as db:
            rows = db.execute(
                """SELECT id,kind,name,created_at,updated_at,data FROM records WHERE (? IS NULL OR kind=?)
                AND (instr(lower(name),lower(?))>0 OR instr(lower(data),lower(?))>0)
                ORDER BY updated_at DESC LIMIT ?""",
                (kind, kind, query, query, limit),
            ).fetchall()
        return [self._record(row) for row in rows]
