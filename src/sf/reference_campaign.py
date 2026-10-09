"""PQ-07Q: repeatable local process-death and SQLite target CAS test.

Uses its own temporary files only; NOT a deployed service or remote fence.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .reference_target import ReferenceTarget, ReferenceTargetError


class ReferenceCampaignError(ValueError):
    """Local reference process-death or recovery invariant failed."""


_CHILD = """
import os
import sys
from pathlib import Path
from sf.reference_target import ReferenceTarget

with ReferenceTarget(Path(sys.argv[1])) as target:
    target.apply("op1", 1, "a" * 64, None)
os._exit(17)
"""


def exercise_local_reference() -> dict:
    """Force an independent Python process to exit after a committed marker.

    Process exit proves only a local SQLite COMMIT/reopen, not power loss,
    distributed fencing, remote transport authenticity or deployment health.
    """
    with tempfile.TemporaryDirectory(prefix="sf-pq07q-local-") as directory:
        marker = Path(directory) / "target.db"
        env = {
            "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PATH": os.environ.get("SystemRoot", "") if os.name == "nt" else "/usr/bin:/bin",
        }
        if os.name == "nt":
            env["SystemRoot"] = os.environ.get("SystemRoot", "")
        try:
            child = subprocess.run(
                [sys.executable, "-c", _CHILD, str(marker)],
                env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=12, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ReferenceCampaignError("isolated reference child unavailable") from exc
        if child.returncode != 17:
            raise ReferenceCampaignError("isolated child did not exit after committed effect")
        with ReferenceTarget(marker) as target:
            before = target.snapshot()
            receipt = target.status("op1")
            if (before != {"generation": 1, "artifactSha256": "a" * 64,
                           "productionDeploymentQualified": False}
                    or receipt is None or receipt["state"] != "APPLIED"
                    or receipt["authenticatedChannelVerified"] is not False):
                raise ReferenceCampaignError("committed child effect not recoverable")
            replay = target.apply("op1", 1, "a" * 64, None)
            if replay != receipt:
                raise ReferenceCampaignError("same idempotency key changed result")
            for operation, gen, digest, previous in (
                ("stale", 1, "b" * 64, "a" * 64),
                ("op1", 1, "b" * 64, None),
                ("wrong-prior", 2, "b" * 64, None),
            ):
                try:
                    target.apply(operation, gen, digest, previous)
                except ReferenceTargetError:
                    continue
                raise ReferenceCampaignError("stale/conflicting local effect accepted")
            target.apply("op2", 2, "b" * 64, "a" * 64)
            after = target.snapshot()
            if after["generation"] != 2 or after["artifactSha256"] != "b" * 64:
                raise ReferenceCampaignError("valid post-restart CAS failed")
    return {
        "schemaVersion": 1, "kind": "sf-pq07q-local-reference-process-death",
        "localProcessExitObserved": True,
        "localReceiptRecovered": True,
        "localStaleAndConflictingEffectsRejected": True,
        "realRemoteFenceQualified": False, "authenticatedChannelVerified": False,
        "realServiceDeployed": False, "liveOperationsVerified": False,
        "recoveryForPowerLossQualified": False, "productionQualified": False,
        "status": "BLOCKED-external-qualification",
    }
