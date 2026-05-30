"""MockAdapter — a deterministic, offline reference adapter.

The wave-2 reference implementation of the ``Adapter`` seam. It makes NO network
call and uses no model: it synthesizes a result by walking the unit's
``output_schema`` and emitting a typed, deterministic canned value per property,
honoring ``enum`` / ``minItems`` / numeric-bound constraints so the produced
output satisfies the unit's own ``acceptance_contract`` for the wave-1 fixtures.

This keeps the entire execute flow testable offline (research 02 A.2 step 4 — the
cheap client-side acceptance filter — exercised end to end without a live model).
Live adapters (Claude Code / OpenAI-compatible / ollama) are a follow-on
increment; they override ``produce`` with a real runtime call but reuse the same
seam, render, and CandidateResult.
"""

from __future__ import annotations

import hashlib
from typing import Any

from ..types import WorkUnit
from .adapter import Adapter
from .capability import Capabilities
from .render import render_payload
from .result import CandidateResult

# Fixed provenance placeholders so output is fully deterministic (no wall clock).
_MOCK_PRODUCED_AT = "1970-01-01T00:00:00Z"
_MOCK_ADAPTER_VERSION = "mock-0.1.0"


class MockAdapter(Adapter):
    """Deterministic schema-shaped echo adapter (no network, no model).

    Pass ``capabilities`` to simulate a node of a given tier (defaults to a
    generously-capable node so it qualifies for the wave-1 fixtures). Pass
    ``corrupt=True`` to deliberately emit acceptance-failing output (for the
    acceptance-fail test path) — it then returns an empty object.
    """

    name = "mock"
    model_family = "mock"
    version = _MOCK_ADAPTER_VERSION

    def __init__(
        self,
        capabilities: Capabilities | None = None,
        corrupt: bool = False,
    ) -> None:
        self._capabilities = capabilities or Capabilities(
            context_window=1_000_000,
            tools=[
                "web_fetch",
                "document_read",
            ],
            modalities=["text", "image"],
            model_family_tier=3,
        )
        self._corrupt = corrupt

    @property
    def capabilities(self) -> Capabilities:
        return self._capabilities

    def produce(self, unit: WorkUnit) -> CandidateResult:
        payload = render_payload(unit)
        if self._corrupt:
            output: dict[str, Any] = {}  # deliberately fails acceptance
        else:
            output = self._synthesize(payload.output_schema, payload.objective)
        return CandidateResult(
            task_id=unit.task_id,
            output=output,
            adapter_name=self.name,
            model_family=self.model_family,
            adapter_version=self.version,
            produced_at=_MOCK_PRODUCED_AT,
            signature=self._mock_signature(unit.task_id, output),
        )

    # --- deterministic schema synthesis --------------------------------------

    def _synthesize(self, schema: dict[str, Any], objective: str) -> Any:
        """Produce a deterministic value matching a JSON-Schema fragment."""
        # enum: pick the first allowed value (deterministic + schema-valid).
        enum = schema.get("enum")
        if enum:
            return enum[0]

        json_type = schema.get("type")
        if json_type == "object":
            props = schema.get("properties", {})
            required = schema.get("required", list(props.keys()))
            obj: dict[str, Any] = {}
            for name in required:
                subschema = props.get(name, {})
                obj[name] = self._synthesize_property(name, subschema, objective)
            return obj
        if json_type == "array":
            items = schema.get("items", {"type": "string"})
            count = max(1, int(schema.get("minItems", 1)))
            return [self._synthesize(items, objective) for _ in range(count)]
        return self._scalar(json_type, schema, field_name="value")

    def _synthesize_property(
        self, name: str, schema: dict[str, Any], objective: str
    ) -> Any:
        enum = schema.get("enum")
        if enum:
            return enum[0]
        json_type = schema.get("type")
        if json_type in ("object", "array"):
            return self._synthesize(schema, objective)
        return self._scalar(json_type, schema, field_name=name)

    def _scalar(
        self, json_type: str | None, schema: dict[str, Any], field_name: str
    ) -> Any:
        if json_type == "boolean":
            return True
        if json_type == "integer":
            return self._bounded_number(schema, integer=True)
        if json_type == "number":
            return self._bounded_number(schema, integer=False)
        if json_type == "null":
            return None
        # default + "string": a short deterministic, non-empty echo. Prefix
        # "https://" so URL-pattern predicates (regex_match ^https?://) pass and
        # the value is recognizably a synthetic mock result.
        digest = hashlib.sha256(field_name.encode("utf-8")).hexdigest()[:8]
        return f"https://mock.cairn.invalid/{field_name}/{digest}"

    @staticmethod
    def _bounded_number(schema: dict[str, Any], integer: bool) -> Any:
        """Pick a value inside [minimum, maximum] if bounded, else a small one."""
        lo = schema.get("minimum")
        hi = schema.get("maximum")
        if lo is not None and hi is not None:
            val = (lo + hi) / 2
        elif lo is not None:
            val = lo
        elif hi is not None:
            val = hi
        else:
            val = 1
        return int(val) if integer else float(val)

    @staticmethod
    def _mock_signature(task_id: str, output: Any) -> str:
        """A placeholder 'signature' — a hash, NOT a real cryptographic sig.

        Real signing is the ledger wave (PLAN §3.6). This only demonstrates the
        provenance field is populated for the future verify layer.
        """
        import json

        payload = json.dumps(
            {"task_id": task_id, "output": output}, sort_keys=True
        ).encode("utf-8")
        return "mock-sig:" + hashlib.sha256(payload).hexdigest()
