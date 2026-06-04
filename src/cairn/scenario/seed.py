"""The scenario seed set — inert open-data-feed records + the defect rule.

The value-demo's **detection** step is openly SIMULATED: a curated set of inert
open-data catalogue records (some carrying a planted quality defect — a broken
download link or malformed license metadata), loaded from a bundled fixture. NO
live scraping, NO network, NO people-data: every "subject" is a DATASET RECORD
(a thing), never a person. The records flow through the EXACT same inert-packet
capture path the engine already ships (``StaticDocumentCapturePort`` →
``ExaminationPacket``), so the packet has no fetch/locator surface by
construction.

``classify_defect`` is the deterministic analysis rule (the shared source of
truth for the offline reference node + the honeypot gold answer): it inspects the
captured registration metadata + rendered text and decides whether the record has
a reportable QUALITY defect, with a confidence. ``build_scenario_unit`` renders
one record into a real work unit whose output carries a numeric
``defect_confidence`` the ``ThresholdFlagPolicy`` flags on.

Mission-neutral by construction: a defect is a non-accusatory QUALITY observation
about a public dataset record ("this listed download link returns 404"), never a
claim about a person.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

from ..capture.packet import (
    OBS_REGISTRATION_METADATA,
    OBS_RENDERED_TEXT,
    Observation,
)

#: the scenario cause id (a demonstration cause, never a live cause).
SCENARIO_CAUSE_ID = "scenario.open-data-feed-quality"

#: the bundled inert seed fixture (no network).
_SEED_FIXTURE = "scenario_open_data_feeds.json"

#: the record seeded as the honeypot gold-standard unit (a clear positive).
HONEYPOT_RECORD_ID = "regional-air-quality-hourly"

#: the confidence the flag policy must meet (>= this flags a finding).
DEFECT_FLAG_THRESHOLD = 0.8

#: the generic opaque flag label the resulting finding records.
SCENARIO_FLAG_LABEL = "open-data-feed-quality-defect"

#: the numeric score field the analysis output carries + the policy flags on.
SCORE_FIELD = "defect_confidence"

#: human-readable defect-kind descriptions (for the dumped packet prose).
DEFECT_DESCRIPTIONS: dict[str, str] = {
    "broken_download_link": (
        "the catalogue's listed download link returns HTTP 404 — the dataset is "
        "advertised as available but cannot be downloaded"
    ),
    "malformed_license_metadata": (
        "the catalogue's machine-readable license field is empty or malformed — "
        "the dataset's reuse terms cannot be parsed by an automated consumer"
    ),
    "none": "no reportable quality defect was detected in this record",
}


def load_seed_records() -> list[dict[str, Any]]:
    """Load the bundled inert seed records (no network)."""
    text = resources.files("cairn.fixtures").joinpath(_SEED_FIXTURE).read_text(encoding="utf-8")
    return json.loads(text)


def get_seed_record(record_id: str) -> dict[str, Any]:
    """Return the seed record with this id (raises ``KeyError`` if absent)."""
    for rec in load_seed_records():
        if rec["record_id"] == record_id:
            return rec
    raise KeyError(f"no scenario seed record {record_id!r}")


def record_observations(record: dict[str, Any]) -> tuple[Observation, ...]:
    """Build the inert observations a capture would record for this record.

    Only static, JSON-serializable data: the rendered-text snapshot + the
    registration metadata map (download status + license field). No live locator,
    no fetch surface — these go into the inert ``ExaminationPacket``.
    """
    return (
        Observation.create(OBS_RENDERED_TEXT, {"text": record["rendered_text"]}),
        Observation.create(OBS_REGISTRATION_METADATA, dict(record["registration_metadata"])),
    )


def classify_defect(observations: dict[str, Any]) -> dict[str, Any]:
    """The deterministic defect rule — the shared source of truth.

    ``observations`` is the analysis input: ``{registration_metadata, ...}``. The
    rule inspects the public dataset-record metadata and returns the canonical
    ``{has_defect, defect_kind, defect_confidence}`` answer. An honest node and the
    honeypot gold standard apply this same rule, so they agree by construction.

    The decision is a non-accusatory QUALITY observation about a dataset record:
      * a ``download_status`` of 404 → ``broken_download_link`` (confidence 0.95)
      * an empty/whitespace ``license_field`` → ``malformed_license_metadata``
        (confidence 0.90)
      * otherwise → no defect (confidence 0.0)
    """
    meta = observations.get("registration_metadata", {})
    if not isinstance(meta, dict):
        meta = {}

    status = meta.get("download_status")
    if isinstance(status, int) and status >= 400:
        return {
            "has_defect": True,
            "defect_kind": "broken_download_link",
            "defect_confidence": 0.95,
        }

    license_field = meta.get("license_field")
    if not (isinstance(license_field, str) and license_field.strip()):
        return {
            "has_defect": True,
            "defect_kind": "malformed_license_metadata",
            "defect_confidence": 0.90,
        }

    return {"has_defect": False, "defect_kind": "none", "defect_confidence": 0.0}


def gold_answer(record: dict[str, Any]) -> dict[str, Any]:
    """The correct analysis answer for a seed record (the honeypot gold standard)."""
    return classify_defect({"registration_metadata": dict(record["registration_metadata"])})


def unit_task_id(record_id: str) -> str:
    return f"{SCENARIO_CAUSE_ID}::{record_id}"


def analysis_inputs(record: dict[str, Any]) -> dict[str, Any]:
    """The inputs a node analyzes — the public, inert record metadata only.

    Carries the registration metadata (download status + license field) + the
    dataset title + the steward label. NO person data; only public dataset-record
    facts. This is what the real Claude (or the deterministic reference node) sees.
    """
    return {
        "inline": {
            "dataset_title": record["dataset_title"],
            "steward": record["steward_label"],
            "registration_metadata": dict(record["registration_metadata"]),
        }
    }


def build_scenario_unit(record: dict[str, Any]) -> dict[str, Any]:
    """Build ONE work-unit dict from a seed record.

    The output schema carries a numeric ``defect_confidence`` so the real
    ``ThresholdFlagPolicy`` (``score_field="defect_confidence"``) can flag a
    high-confidence defect into a finding. ``model_diversity`` is 2 so the
    anti-collusion diversity gate is ON and satisfiable by two distinct families
    (the live ``claude`` node + the deterministic ``reference`` node).
    """
    return {
        "schema_version": "1.0.0",
        "task_id": unit_task_id(record["record_id"]),
        "cause_id": SCENARIO_CAUSE_ID,
        "objective": (
            "Inspect this public open-data CATALOGUE RECORD (a dataset listing, "
            "not a person) and decide whether it has a reportable QUALITY defect: "
            "a broken download link (download_status >= 400) or malformed/empty "
            "license metadata. Report has_defect, the defect_kind "
            "('broken_download_link', 'malformed_license_metadata', or 'none'), "
            "and a defect_confidence in [0,1]. This is a non-accusatory quality "
            "observation about a dataset record."
        ),
        "inputs": analysis_inputs(record),
        "output_schema": {
            "type": "object",
            "required": ["has_defect", "defect_kind", "defect_confidence"],
            "properties": {
                "has_defect": {"type": "boolean"},
                "defect_kind": {"type": "string"},
                "defect_confidence": {"type": "number"},
            },
        },
        "acceptance_contract": {
            "predicates": [
                {
                    "kind": "required_fields",
                    "fields": ["has_defect", "defect_kind", "defect_confidence"],
                },
                {"kind": "field_type", "field": "has_defect", "json_type": "boolean"},
                {"kind": "non_empty", "field": "defect_kind"},
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


def build_scenario_units(
    records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build all scenario work-unit dicts (one per seed record)."""
    records = records if records is not None else load_seed_records()
    return [build_scenario_unit(r) for r in records]


def honeypot_record(records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Return the record seeded as the honeypot (gold-standard) unit."""
    records = records if records is not None else load_seed_records()
    for r in records:
        if r["record_id"] == HONEYPOT_RECORD_ID:
            return r
    raise KeyError(f"honeypot record {HONEYPOT_RECORD_ID!r} not in seed set")
