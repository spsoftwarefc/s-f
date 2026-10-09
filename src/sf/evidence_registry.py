"""PQ-07E: single-host local evidence log with hash-chain integrity, not trust.

Candidate-origin bytes, including negative-case results, are not authenticated
provider observations. A hash chain without an independent anchor is rewritable.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .production_dossier import REQUIRED_CLAIMS

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}\Z")
MAX_EVENT = 1024 * 1024
MAX_ROWS = 512
GENESIS = "0" * 64


class EvidenceRegistryError(ValueError):
    """Invalid candidate identity, altered event or local chain discrepancy."""


def _canonical(data):
    return (json.dumps(data, sort_keys=True, separators=(",", ":"),
                       allow_nan=False, ensure_ascii=True) + "\n").encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _identity(value, pattern, label):
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise EvidenceRegistryError("invalid " + label)


def _metadata(event_id, claim, evidence_kind, case_id,
              source_commit, artifact_sha256, body_sha256, prev_sha256):
    return {
        "eventId": event_id, "claim": claim, "evidenceKind": evidence_kind,
        "caseId": case_id, "sourceCommit": source_commit,
        "artifactSha256": artifact_sha256, "bodySha256": body_sha256,
        "previousSha256": prev_sha256,
    }


class EvidenceRegistry:
    """Source-bound append-only API on local SQLite, no external provider writes."""

    def __init__(self, path: Path):
        if not path.is_absolute() or path.is_symlink() or not path.parent.is_dir():
            raise EvidenceRegistryError("unsafe local evidence database")
        self.db = sqlite3.connect(path, isolation_level=None, timeout=5)
        try:
            if self.db.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() != "wal":
                raise EvidenceRegistryError("local WAL unavailable")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA busy_timeout=5000")
            self.db.execute("""CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE, claim TEXT NOT NULL,
                evidence_kind TEXT NOT NULL, case_id TEXT NOT NULL,
                source_commit TEXT NOT NULL, artifact_sha TEXT NOT NULL,
                body BLOB NOT NULL, body_sha TEXT NOT NULL,
                previous_sha TEXT NOT NULL, chain_sha TEXT NOT NULL
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

    def _verify_locked(self) -> tuple[int, str]:
        rows = self.db.execute(
            "SELECT event_id,claim,evidence_kind,case_id,source_commit,artifact_sha,"
            "body,body_sha,previous_sha,chain_sha FROM events ORDER BY sequence"
        ).fetchall()
        if len(rows) > MAX_ROWS:
            raise EvidenceRegistryError("bounded evidence history exceeded")
        previous = GENESIS
        for eid, claim, kind, case, source, artifact, body, body_sha, prior, digest in rows:
            if (type(body) is not bytes or len(body) > MAX_EVENT
                    or _sha(body) != body_sha or prior != previous):
                raise EvidenceRegistryError("local evidence history was altered")
            metadata = _metadata(eid, claim, kind, case, source, artifact, body_sha, prior)
            check = _sha(_canonical(metadata) + body)
            if check != digest:
                raise EvidenceRegistryError("local evidence chain mismatch")
            previous = digest
        return len(rows), previous

    def verify_chain(self) -> dict:
        total, head = self._verify_locked()
        return {"total": total, "localChainSha256": head,
                "independentAnchorVerified": False, "productionQualified": False}

    def append(self, event_id: str, claim: str, evidence_kind: str,
               case_id: str, source_commit: str,
               artifact_sha256: str, body: bytes) -> dict:
        for name, value in (("event ID", event_id), ("case ID", case_id)):
            _identity(value, IDENT, name)
        _identity(source_commit, SHA40, "candidate source")
        _identity(artifact_sha256, SHA64, "candidate artifact")
        if claim not in REQUIRED_CLAIMS or type(claim) is not str:
            raise EvidenceRegistryError("unknown evidence claim")
        if evidence_kind not in ("positive", "negative") or type(evidence_kind) is not str:
            raise EvidenceRegistryError("invalid evidence kind")
        if type(body) is not bytes or not 0 < len(body) <= MAX_EVENT:
            raise EvidenceRegistryError("empty, oversized or unsafe raw evidence")
        digest = _sha(body)
        with self._tx():
            count, previous = self._verify_locked()
            old = self.db.execute(
                "SELECT claim,evidence_kind,case_id,source_commit,artifact_sha,body_sha "
                "FROM events WHERE event_id=?", (event_id,)
            ).fetchone()
            if old is not None:
                if old != (claim, evidence_kind, case_id, source_commit,
                           artifact_sha256, digest):
                    raise EvidenceRegistryError("conflicting immutable evidence event ID")
                return {"status": "already-recorded", "bodySha256": digest,
                        "accepted": False, "productionQualified": False}
            if count >= MAX_ROWS:
                raise EvidenceRegistryError("evidence retention limit exceeded")
            metadata = _metadata(event_id, claim, evidence_kind, case_id,
                                 source_commit, artifact_sha256, digest, previous)
            chain_sha = _sha(_canonical(metadata) + body)
            self.db.execute(
                "INSERT INTO events (event_id,claim,evidence_kind,case_id,source_commit,"
                "artifact_sha,body,body_sha,previous_sha,chain_sha)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (event_id, claim, evidence_kind, case_id, source_commit,
                 artifact_sha256, body, digest, previous, chain_sha)
            )
        return {"status": "recorded-locally", "bodySha256": digest,
                "chainSha256": chain_sha, "accepted": False, "productionQualified": False}

    def coverage(self, source_commit: str, artifact_sha256: str) -> dict:
        _identity(source_commit, SHA40, "candidate source")
        _identity(artifact_sha256, SHA64, "candidate artifact")
        evidence = self.verify_chain()
        seen = self.db.execute(
            "SELECT claim,evidence_kind FROM events WHERE source_commit=? AND artifact_sha=?",
            (source_commit, artifact_sha256)
        ).fetchall()
        kinds = {claim: set() for claim in REQUIRED_CLAIMS}
        for claim, kind in seen:
            kinds[claim].add(kind)
        return {
            "schemaVersion": 1, "kind": "sf-pq07e-local-evidence-coverage",
            "sourceCommit": source_commit, "artifactSha256": artifact_sha256,
            "localChainSha256": evidence["localChainSha256"],
            "claimStates": [
                {"claim": claim, "state": "present-unverified"
                 if {"positive", "negative"} <= kinds[claim] else "missing"}
                for claim in REQUIRED_CLAIMS
            ],
            "independentAnchorVerified": False,
            "producerAuthenticityVerified": False,
            "accepted": False, "productionQualified": False,
        }
