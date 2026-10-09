"""PQ-06: durable reference observations and non-auto-closing incidents.

Operator-controlled HMAC keys are external inputs; the local journal does not
establish custody, device transport authenticity, or live service monitoring.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
FIELDS = {"schemaVersion", "eventId", "source", "target", "environment",
          "epoch", "sequence", "domain", "state", "observedAt", "evidenceSha256"}
STATES = {"healthy", "degraded", "failed", "unknown"}
DOMAINS = {"deployment", "health", "migration", "recovery"}


class JournalError(ValueError):
    """Untrusted, stale, contradictory or unauthenticated observation."""


def canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")


def _mac(secret: bytes, body: dict, supplied: str) -> None:
    if type(secret) is not bytes or len(secret) < 32:
        raise JournalError("operator secret unavailable")
    if type(supplied) is not str or SHA.fullmatch(supplied) is None:
        raise JournalError("invalid authentication tag")
    expected = hmac.new(secret, canonical(body), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        raise JournalError("unauthenticated observation")


def _identity(value: object) -> None:
    if type(value) is not str or IDENT.fullmatch(value) is None:
        raise JournalError("invalid observation identity")


def _time(value: object) -> datetime:
    if type(value) is not str or DATE.fullmatch(value) is None:
        raise JournalError("invalid exact UTC observation time")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise JournalError("invalid observation timestamp") from exc


class LiveJournal:
    def __init__(self, path: Path):
        if not path.is_absolute() or path.is_symlink() or not path.parent.is_dir():
            raise JournalError("unsafe incident journal path")
        self.db = sqlite3.connect(path, isolation_level=None, timeout=5)
        try:
            mode = self.db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA busy_timeout=5000")
            if mode.lower() != "wal":
                raise JournalError("WAL unavailable")
            self.db.execute("""CREATE TABLE IF NOT EXISTS observations (
                event_id TEXT PRIMARY KEY, source TEXT NOT NULL,
                target TEXT NOT NULL, domain TEXT NOT NULL,
                sequence INTEGER NOT NULL, epoch INTEGER NOT NULL,
                state TEXT NOT NULL, evidence_sha TEXT NOT NULL,
                UNIQUE(source,target,domain,sequence)
            )""")
            self.db.execute("""CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK (status IN ('OPEN','RESOLVED')),
                recovery_sha TEXT, resolved_by TEXT
            )""")
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

    def observe(self, event: dict, supplied_mac: str, secret: bytes, *,
                expected_source: str, expected_target: str,
                expected_environment: str, now: datetime | None = None,
                max_age_seconds: int = 300) -> dict:
        if type(event) is not dict or set(event) != FIELDS or (
                type(event["schemaVersion"]) is not int
                or event["schemaVersion"] != 1):
            raise JournalError("unsupported observation schema")
        for field in ("eventId", "source", "target", "environment"):
            _identity(event[field])
        if (event["source"] != expected_source
                or event["target"] != expected_target
                or event["environment"] != expected_environment):
            raise JournalError("observation source, target or environment mismatch")
        if event["state"] not in STATES or event["domain"] not in DOMAINS:
            raise JournalError("invalid observation classification")
        if (type(event["sequence"]) is not int or not 1 <= event["sequence"] <= 2**63 - 1
                or type(event["epoch"]) is not int
                or not 1 <= event["epoch"] <= 2**63 - 1):
            raise JournalError("invalid observation epoch or sequence")
        if type(event["evidenceSha256"]) is not str or SHA.fullmatch(event["evidenceSha256"]) is None:
            raise JournalError("invalid evidence digest")
        clock = now or datetime.now(timezone.utc)
        if clock.tzinfo is None or type(max_age_seconds) is not int or not 0 < max_age_seconds <= 3600:
            raise JournalError("invalid observation clock or freshness policy")
        skew = (clock.astimezone(timezone.utc) - _time(event["observedAt"])).total_seconds()
        if skew < -60 or skew > max_age_seconds:
            raise JournalError("stale or future observation")
        _mac(secret, event, supplied_mac)
        with self._tx():
            row = self.db.execute(
                "SELECT MAX(sequence),MAX(epoch) FROM observations "
                "WHERE source=? AND target=? AND domain=?",
                (event["source"], event["target"], event["domain"])).fetchone()
            if row[0] is not None and (
                    event["sequence"] <= row[0] or event["epoch"] < row[1]):
                raise JournalError("replayed or out-of-order observation")
            self.db.execute(
                "INSERT INTO observations VALUES (?,?,?,?,?,?,?,?)",
                (event["eventId"], event["source"], event["target"],
                 event["domain"], event["sequence"], event["epoch"],
                 event["state"], event["evidenceSha256"]))
            if event["state"] != "healthy":
                self.db.execute(
                    "INSERT INTO incidents VALUES (?, 'OPEN', NULL, NULL)",
                    (event["eventId"],))
        return {"eventId": event["eventId"], "recorded": True,
                "incidentOpened": event["state"] != "healthy",
                "liveOperationsQualified": False, "accepted": False}

    def incident(self, incident_id: str) -> dict | None:
        _identity(incident_id)
        row = self.db.execute(
            "SELECT status,recovery_sha,resolved_by FROM incidents WHERE incident_id=?",
            (incident_id,)).fetchone()
        return None if row is None else {
            "incidentId": incident_id, "status": row[0],
            "recoverySha256": row[1], "resolvedBy": row[2],
            "liveOperationsQualified": False,
        }

    def resolve(self, incident_id: str, operator_id: str,
                recovery_sha256: str, operator_mac: str,
                operator_secret: bytes) -> dict:
        """Manual operator-bound decision only; never from healthy observation."""
        _identity(incident_id)
        _identity(operator_id)
        if type(recovery_sha256) is not str or SHA.fullmatch(recovery_sha256) is None:
            raise JournalError("invalid independent recovery evidence")
        record = {"incidentId": incident_id, "operatorId": operator_id,
                  "recoverySha256": recovery_sha256}
        _mac(operator_secret, record, operator_mac)
        with self._tx():
            current = self.incident(incident_id)
            if current is None or current["status"] != "OPEN":
                raise JournalError("missing or already resolved incident")
            self.db.execute(
                "UPDATE incidents SET status='RESOLVED',recovery_sha=?,resolved_by=? "
                "WHERE incident_id=?", (recovery_sha256, operator_id, incident_id))
        return self.incident(incident_id)
