"""PQ-04: fail-closed, single-host SQLite durable operation intent ledger.

State tracks local coordinator intent only. A numeric generation is NOT remote
fencing unless a separately qualified destination enforces it atomically.
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

HEX = re.compile(r"[0-9a-f]{64}\Z")
IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}\Z")


class LedgerError(ValueError):
    """Uncertain, stale or unsafe coordinator operation."""


def _id(value: str) -> None:
    if type(value) is not str or not IDENT.fullmatch(value):
        raise LedgerError("invalid operation key")


def _sha(value: str) -> None:
    if type(value) is not str or not HEX.fullmatch(value):
        raise LedgerError("invalid immutable intent digest")


class DurableLedger:
    """Local-disk WAL, one SQLite writer transaction per transition."""

    def __init__(self, path: Path):
        if not path.is_absolute() or path.is_symlink() or not path.parent.is_dir():
            raise LedgerError("ledger requires a local operator-owned path")
        self.db = sqlite3.connect(path, isolation_level=None, timeout=5.0)
        try:
            mode = self.db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA busy_timeout=5000")
            if mode.lower() != "wal":
                raise LedgerError("SQLite WAL unavailable")
            self.db.execute("""CREATE TABLE IF NOT EXISTS operations (
                operation_id TEXT PRIMARY KEY,
                intent_sha TEXT NOT NULL,
                generation INTEGER NOT NULL,
                state TEXT NOT NULL CHECK (state IN
                  ('PREPARED','RESERVED','UNKNOWN','CONFIRMED','BLOCKED'))
            )""")
        except Exception:
            self.db.close()
            raise

    def close(self) -> None:
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def _tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def get(self, operation_id: str) -> dict | None:
        _id(operation_id)
        row = self.db.execute(
            "SELECT intent_sha,generation,state FROM operations WHERE operation_id=?",
            (operation_id,)).fetchone()
        return None if row is None else {
            "operationId": operation_id, "intentSha256": row[0],
            "generation": row[1], "state": row[2],
            "remoteFenceVerified": False, "outcomeAuthoritative": False,
        }

    def prepare(self, operation_id: str, intent_sha256: str) -> dict:
        _id(operation_id)
        _sha(intent_sha256)
        with self._tx():
            row = self.get(operation_id)
            if row is None:
                self.db.execute(
                    "INSERT INTO operations VALUES (?, ?, 0, 'PREPARED')",
                    (operation_id, intent_sha256))
            elif row["intentSha256"] != intent_sha256:
                raise LedgerError("operation key already bound to a different intent")
        return self.get(operation_id)

    def reserve(self, operation_id: str, intent_sha256: str, *,
                minimum_generation: int = 0) -> dict:
        """Only a PREPARED immutable intent may reserve its first dispatch."""
        _id(operation_id)
        _sha(intent_sha256)
        if type(minimum_generation) is not int or minimum_generation < 0:
            raise LedgerError("invalid operator epoch floor")
        with self._tx():
            row = self.get(operation_id)
            if row is None or row["intentSha256"] != intent_sha256:
                raise LedgerError("missing or changed durable intent")
            if row["state"] != "PREPARED":
                raise LedgerError("operation is reserved, uncertain or settled")
            generation = max(row["generation"], minimum_generation) + 1
            if generation > 2**63 - 1:
                raise LedgerError("generation overflow")
            self.db.execute(
                "UPDATE operations SET generation=?, state='RESERVED' WHERE operation_id=?",
                (generation, operation_id))
        return self.get(operation_id)

    def possible_send(self, operation_id: str, generation: int) -> dict:
        """Commit uncertainty *before* caller attempts the target send."""
        _id(operation_id)
        if type(generation) is not int or generation < 1:
            raise LedgerError("invalid generation")
        with self._tx():
            row = self.get(operation_id)
            if row is None or row["state"] != "RESERVED" or row["generation"] != generation:
                raise LedgerError("stale fence or unsafe send transition")
            self.db.execute(
                "UPDATE operations SET state='UNKNOWN' WHERE operation_id=?",
                (operation_id,))
        return self.get(operation_id)

    def hold_for_reconciliation(self, operation_id: str, generation: int) -> dict:
        """Record a manual block only; does not assert target status."""
        _id(operation_id)
        with self._tx():
            row = self.get(operation_id)
            if (row is None or type(generation) is not int
                    or row["generation"] != generation
                    or row["state"] not in ("RESERVED", "UNKNOWN", "BLOCKED")):
                raise LedgerError("stale or settled reconciliation attempt")
            self.db.execute(
                "UPDATE operations SET state='BLOCKED' WHERE operation_id=?",
                (operation_id,))
        return self.get(operation_id)
