"""PQ-07C: read-only cross-store process crash reconciliation.

These SQLite receipts are reference-local, NOT authenticated remote effects.
No ambiguous state authorizes an unattended retry.
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{64}\Z")
IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}\Z")


class RecoveryAssessmentError(ValueError):
    """Invalid local reconciliation request or contradictory reference receipt."""


def assess_local_recovery(
    ledger_path: Path, target_path: Path, operation_id: str,
    expected_intent_sha256: str, expected_artifact_sha256: str,
) -> dict:
    if type(operation_id) is not str or not IDENT.fullmatch(operation_id):
        raise RecoveryAssessmentError("invalid operation identity")
    for value in (expected_intent_sha256, expected_artifact_sha256):
        if type(value) is not str or not SHA.fullmatch(value):
            raise RecoveryAssessmentError("invalid expected immutable digest")
    # Do not instantiate missing stores: constructors create local databases.
    for path in (ledger_path, target_path):
        if (not path.is_absolute() or path.is_symlink()
                or not path.is_file()):
            raise RecoveryAssessmentError("missing or unsafe existing local store")
    # SQLite mode=ro avoids opening the normal ledger/target constructors,
    # whose WAL/schema initialization would mutate the evidence being inspected.
    try:
        with closing(sqlite3.connect(ledger_path.as_uri() + "?mode=ro", uri=True, timeout=2)) as db:
            row = db.execute(
                "SELECT intent_sha, generation, state FROM operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
        with closing(sqlite3.connect(target_path.as_uri() + "?mode=ro", uri=True, timeout=2)) as db:
            target_row = db.execute(
                "SELECT generation, requested_sha, status FROM receipts WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
    except sqlite3.Error as exc:
        raise RecoveryAssessmentError("unavailable or malformed local reference evidence") from exc
    intent = None if row is None else {
        "intentSha256": row[0], "generation": row[1], "state": row[2],
    }
    receipt = None if target_row is None else {
        "generation": target_row[0], "artifactSha256": target_row[1], "state": target_row[2],
    }
    if intent is None:
        raise RecoveryAssessmentError("no durable immutable intent")
    if intent["intentSha256"] != expected_intent_sha256:
        raise RecoveryAssessmentError("immutable operation intent disagrees with caller")
    if receipt is not None and (
            receipt["artifactSha256"] != expected_artifact_sha256
            or receipt["generation"] != intent["generation"]):
        outcome = "CONTRADICTORY"
    elif receipt is not None:
        outcome = "REFERENCE_EFFECT_PRESENT_UNVERIFIED"
    elif intent["state"] == "PREPARED":
        outcome = "INTENT_ONLY"
    else:
        outcome = "UNKNOWN_EFFECT"
    return {
        "schemaVersion": 1,
        "kind": "sf-pq07c-recovery-assessment",
        "operationId": operation_id,
        "intentState": intent["state"],
        "targetReceiptState": None if receipt is None else receipt["state"],
        "localClassification": outcome,
        "targetReceiptAuthenticated": False,
        "remoteFenceQualified": False,
        "retryAuthorized": False,
        "manualReconciliationRequired": True,
        "productionQualified": False,
    }
