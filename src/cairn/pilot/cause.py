"""The benign pilot cause — open-source-license classification.

A concrete, NON-SENSITIVE distributed-analysis task expressed as REAL work
units: for each bundled benign text snippet (a dataset license blurb), a node must
emit ``{is_open_license: bool, license_id: string}``. The answer is
deterministically derivable from the snippet text, so it is machine-checkable
(acceptance contract), gives a meaningful GOLD STANDARD for the honeypot layer,
and is satisfiable by N distinct-family nodes that AGREE (diversity quorum).

The cause reuses the EXACT shape of ``fixtures/benign_pilot.json`` (schema 1.0.0,
the ``{is_open_license, license_id}`` output schema, the same acceptance
predicates). It does NOT introduce a new spec — it instantiates the one.

Inputs are bundled (``fixtures/pilot_license_snippets.json``) — no network.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

PILOT_CAUSE_ID = "pilot.oss-license-classification"

# Which unit is the gold-standard SEED whose Honeypot scores every node against
# the known answer. Any snippet works; we seed a clear positive.
HONEYPOT_SNIPPET_ID = "bike-counts"

_SNIPPETS_FIXTURE = "pilot_license_snippets.json"

# Deterministic keyword -> (is_open, license_id) rule table. Ordered: the first
# matching keyword wins. This is the SAME rule the honest adapter and the gold
# answer both apply, so an honest node necessarily matches the gold standard.
_LICENSE_RULES: list[tuple[str, bool, str]] = [
    ("all rights reserved", False, "PROPRIETARY"),
    ("proprietary", False, "PROPRIETARY"),
    ("apache license", True, "Apache-2.0"),
    ("gnu general public license", True, "GPL-3.0"),
    ("gpl-3.0", True, "GPL-3.0"),
    ("mit license", True, "MIT"),
    ("bsd", True, "BSD-3-Clause"),
]


def load_snippets() -> list[dict[str, Any]]:
    """Load the bundled benign input snippets (no network)."""
    text = (
        resources.files("cairn.fixtures")
        .joinpath(_SNIPPETS_FIXTURE)
        .read_text(encoding="utf-8")
    )
    return json.loads(text)


def classify_license(license_text: str) -> dict[str, Any]:
    """Apply the deterministic rule table to a license blurb.

    Returns the canonical ``{is_open_license, license_id}`` answer. This is the
    single source of truth shared by ``gold_answer`` and ``PilotNodeAdapter`` —
    an honest node and the gold standard agree by construction.
    """
    lowered = license_text.lower()
    for keyword, is_open, license_id in _LICENSE_RULES:
        if keyword in lowered:
            return {"is_open_license": is_open, "license_id": license_id}
    # Unknown license text: conservative default — not provably open, unknown id.
    return {"is_open_license": False, "license_id": "UNKNOWN"}


def gold_answer(snippet: dict[str, Any]) -> dict[str, Any]:
    """The correct output for a snippet (its ``expected_*`` fields).

    Used to (a) seed the honeypot for the gold unit and (b) check, in tests, that
    the gold answer passes the unit's own acceptance contract (well-formedness).
    """
    return {
        "is_open_license": bool(snippet["expected_is_open"]),
        "license_id": str(snippet["expected_license_id"]),
    }


def unit_task_id(snippet_id: str) -> str:
    return f"{PILOT_CAUSE_ID}::{snippet_id}"


def build_unit(snippet: dict[str, Any]) -> dict[str, Any]:
    """Build ONE work-unit dict from a snippet (reusing benign_pilot shape).

    ``model_diversity`` is set explicitly to 2 so the anti-collusion diversity
    gate is ON and satisfiable by two distinct model families.
    """
    return {
        "schema_version": "1.0.0",
        "task_id": unit_task_id(snippet["snippet_id"]),
        "cause_id": PILOT_CAUSE_ID,
        "objective": (
            "Classify whether the dataset listing's stated license is an "
            "OSI-approved open-source license, and extract the license identifier."
        ),
        "inputs": {
            "inline": {
                "dataset_title": snippet["dataset_title"],
                "license_text": snippet["license_text"],
                "source_url": snippet["source_url"],
            }
        },
        "output_schema": {
            "type": "object",
            "required": ["is_open_license", "license_id"],
            "properties": {
                "is_open_license": {"type": "boolean"},
                "license_id": {"type": "string"},
            },
        },
        "acceptance_contract": {
            "predicates": [
                {
                    "kind": "required_fields",
                    "fields": ["is_open_license", "license_id"],
                },
                {
                    "kind": "field_type",
                    "field": "is_open_license",
                    "json_type": "boolean",
                },
                {"kind": "non_empty", "field": "license_id"},
            ]
        },
        "capability_floor": {
            "context_window": 4096,
            "tools": [],
            "modalities": ["text"],
        },
        "redundancy_policy": {
            "target_nresults": 2,
            "min_quorum": 2,
            "model_diversity": 2,
        },
        "provenance_requirements": {
            "model_family": True,
            "signed_result": False,
            "trace": False,
        },
    }


def build_pilot_units(
    snippets: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build all pilot work-unit dicts (one per bundled snippet)."""
    snippets = snippets if snippets is not None else load_snippets()
    return [build_unit(s) for s in snippets]


def honeypot_snippet(snippets: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Return the snippet seeded as the honeypot (gold-standard) unit."""
    snippets = snippets if snippets is not None else load_snippets()
    for s in snippets:
        if s["snippet_id"] == HONEYPOT_SNIPPET_ID:
            return s
    raise KeyError(f"honeypot snippet {HONEYPOT_SNIPPET_ID!r} not in snippet set")
