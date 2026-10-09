"""PQ-05: isolated local reference target with *destination-side* durable CAS.

No network, credentials, migrations, health probe or production deployment.
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")


class ReferenceTargetError(ValueError):
    """Stale generation, contradictory idempotency or unsafe target input."""


def _id(value):
    if type(value) is not str or IDENT.fullmatch(value) is None:
        raise ReferenceTargetError("invalid operation ID")


def _digest(value, *, optional=False):
    if optional and value is None:
        return
    if type(value) is not str or HASH.fullmatch(value) is None:
        raise ReferenceTargetError("invalid artifact digest")


class ReferenceTarget:
    """An isolated SQLite marker target, not a live application deployment."""

    def __init__(self, path: Path):
        if not path.is_absolute() or path.is_symlink() or not path.parent.is_dir():
            raise ReferenceTargetError("unsafe reference-target path")
        self.db = sqlite3.connect(path, timeout=5, isolation_level=None)
        try:
            mode = self.db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA busy_timeout=5000")
            if mode.lower() != "wal":
                raise ReferenceTargetError("reference WAL unavailable")
            self.db.execute("""CREATE TABLE IF NOT EXISTS target (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                generation INTEGER NOT NULL,
                artifact_sha TEXT
            )""")
            self.db.execute("""CREATE TABLE IF NOT EXISTS receipts (
                operation_id TEXT PRIMARY KEY,
                generation INTEGER NOT NULL,
                requested_sha TEXT NOT NULL,
                previous_sha TEXT,
                status TEXT NOT NULL
            )""")
            self.db.execute("INSERT OR IGNORE INTO target VALUES (1,0,NULL)")
        except Exception:
            self.db.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.db.close()

    @contextmanager
    def _tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def status(self, operation_id: str) -> dict | None:
        _id(operation_id)
        row = self.db.execute(
            "SELECT generation,requested_sha,previous_sha,status FROM receipts "
            "WHERE operation_id=?", (operation_id,)).fetchone()
        if row is None:
            return None
        return {"operationId": operation_id, "generation": row[0],
                "artifactSha256": row[1], "previousSha256": row[2],
                "state": row[3], "authenticatedChannelVerified": False}

    def apply(self, operation_id: str, generation: int,
              artifact_sha256: str, expected_previous_sha256: str | None) -> dict:
        """Atomically enforce operation identity, target generation and prior SHA.

        Caller must externally authenticate and authorize this effect. In this
        reference it changes only one durable SQLite artifact marker.
        """
        _id(operation_id)
        _digest(artifact_sha256)
        _digest(expected_previous_sha256, optional=True)
        if type(generation) is not int or not 1 <= generation <= 2**63 - 1:
            raise ReferenceTargetError("invalid requested generation")
        with self._tx():
            prior = self.status(operation_id)
            if prior is not None:
                if (prior["generation"] != generation
                        or prior["artifactSha256"] != artifact_sha256
                        or prior["previousSha256"] != expected_previous_sha256):
                    raise ReferenceTargetError("operation ID reused with conflicting effects")
                return prior
            current_gen, current_sha = self.db.execute(
                "SELECT generation,artifact_sha FROM target WHERE singleton=1").fetchone()
            if generation <= current_gen:
                raise ReferenceTargetError("stale target generation")
            if current_sha != expected_previous_sha256:
                raise ReferenceTargetError("target compare-and-swap mismatch")
            self.db.execute(
                "UPDATE target SET generation=?,artifact_sha=? WHERE singleton=1",
                (generation, artifact_sha256))
            self.db.execute(
                "INSERT INTO receipts VALUES (?, ?, ?, ?, 'APPLIED')",
                (operation_id, generation, artifact_sha256, expected_previous_sha256))
        return self.status(operation_id)

    def snapshot(self) -> dict:
        gen, sha = self.db.execute(
            "SELECT generation, artifact_sha FROM target WHERE singleton=1").fetchone()
        return {"generation": gen, "artifactSha256": sha,
                "productionDeploymentQualified": False}
