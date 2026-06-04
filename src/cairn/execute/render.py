"""Portable-payload render — the runtime-neutral surface an adapter consumes.

``objective`` + ``inputs`` + ``output_schema`` +
``acceptance_contract`` is **the entire portable payload**. Everything
model-specific (the actual prompt template, system prompt, tool wiring) is
synthesized *locally by the adapter*. This module produces that neutral surface;
adapters build their native call from it.

The render is deliberately vendor-free: no Claude/OpenAI/ollama-specific text. A
live adapter overrides the neutral ``prompt`` with its own template; the four
declarative fields are the stable boundary.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..types import AcceptanceContract, WorkUnit


@dataclass(frozen=True)
class RenderedPayload:
    """The portable payload, plus a neutral textual prompt rendering.

    Only the four declarative fields cross this boundary — nothing
    model-specific and no other work-unit field (task_id, capability_floor,
    redundancy_policy, provenance, deadline/lease all stay out). ``prompt`` is a
    convenience textual rendering a thin adapter MAY use directly or override.
    """

    objective: str
    inputs: dict[str, Any]
    output_schema: dict[str, Any]
    acceptance_contract: dict[str, Any]
    prompt: str


def _contract_to_dict(contract: Any) -> dict[str, Any]:
    """Normalize an AcceptanceContract dataclass or dict to dict form."""
    if isinstance(contract, AcceptanceContract):
        out_preds = []
        for p in contract.predicates:
            d = {"kind": p.kind}
            d.update(p.params)
            out_preds.append(d)
        return {"predicates": out_preds}
    if isinstance(contract, dict):
        return contract
    raise TypeError(
        f"acceptance_contract must be a dict or AcceptanceContract, got {type(contract).__name__}"
    )


def _neutral_prompt(objective: str, inputs: dict[str, Any], output_schema: dict[str, Any]) -> str:
    """A vendor-neutral textual rendering of the task.

    Mentions the objective, the inputs, and the required output shape. A live
    adapter is free to discard this and template its own; the MockAdapter does
    not need it (it walks the schema directly).
    """
    return (
        "OBJECTIVE:\n"
        f"{objective}\n\n"
        "INPUTS:\n"
        f"{json.dumps(inputs, indent=2, sort_keys=True)}\n\n"
        "RETURN a JSON object matching this schema:\n"
        f"{json.dumps(output_schema, indent=2, sort_keys=True)}\n"
    )


def render_payload(unit: WorkUnit) -> RenderedPayload:
    """Render a validated WorkUnit into its portable payload.

    Pulls ONLY the four declarative fields off the unit; everything else stays
    behind the adapter seam. Pure + runtime-neutral — no network, no vendor
    template.
    """
    contract = _contract_to_dict(unit.acceptance_contract)
    return RenderedPayload(
        objective=unit.objective,
        inputs=unit.inputs,
        output_schema=unit.output_schema,
        acceptance_contract=contract,
        prompt=_neutral_prompt(unit.objective, unit.inputs, unit.output_schema),
    )
