"""Example work-unit fixtures (wave 1).

Three units exercising the spec: a trivial benign-pilot unit, a cause-threaded
unit with a capability_floor, and a unit with a non-trivial acceptance_contract.
``load_fixture`` returns the raw dict; validate it with
``cairn.validate.validate_work_unit``.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

_FIXTURE_NAMES = (
    "benign_pilot",
    "cause_threaded",
    "structured_acceptance",
)


def list_fixtures() -> list[str]:
    """Return the available fixture names (without the .json extension)."""
    return list(_FIXTURE_NAMES)


def load_fixture(name: str) -> dict[str, Any]:
    """Load an example work unit by name (e.g. ``"benign_pilot"``)."""
    if name not in _FIXTURE_NAMES:
        raise KeyError(f"unknown fixture {name!r}; available: {list(_FIXTURE_NAMES)}")
    text = (
        resources.files("cairn.fixtures")
        .joinpath(f"{name}.json")
        .read_text(encoding="utf-8")
    )
    return json.loads(text)
