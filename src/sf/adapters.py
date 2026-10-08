"""Read-only adapters mapping declared project checks to component order.

Adapter hints are not authoritative build commands. No subprocess, filesystem or
network operations occur here; SF-09 will qualify any execution implementation.
"""
from __future__ import annotations

from .profile import ProfileError, component_order, validate_profile

STACK_HINTS = {
    "python": (("test", ("python", "-m", "unittest", "discover")),),
    "node": (("test", ("npm", "test")),),
    "rust": (("test", ("cargo", "test")),),
    "go": (("test", ("go", "test", "./...")),),
    "custom": (),
}


def adapter_hints(stack: str) -> list[dict]:
    """Example command vectors only; they must never become implicit authority."""
    if type(stack) is not str or stack not in STACK_HINTS:
        raise ProfileError("unknown stack hint; use custom")
    return [
        {"purpose": purpose, "argv": list(argv), "authoritative": False, "executed": False}
        for purpose, argv in STACK_HINTS[stack]
    ]


def declared_check_plan(profile: dict) -> dict:
    """Plan explicit command references without executing them."""
    validate_profile(profile)
    by_id = {component["id"]: component for component in profile.get("components", [])}
    ordered: list[dict] = []
    for name in component_order(profile):
        component = by_id[name]
        ordered.append({
            "id": name,
            "path": component["path"],
            "stack": component["stack"],
            "dependsOn": sorted(component.get("dependsOn", [])),
            "checks": [
                {"id": check, "argv": list(profile["commands"][check]["argv"]),
                 "cwd": profile["commands"][check]["cwd"],
                 "risk": profile["commands"][check].get("risk", "build"),
                 "network": profile["commands"][check].get("network", False)}
                for check in component.get("checks", [])
            ],
        })
    return {
        "schemaVersion": 1,
        "projectId": profile["project"]["id"],
        "orderedComponents": ordered,
        "commandsExecuted": [],
        "executionAuthorized": False,
        "releaseQualified": False,
    }
