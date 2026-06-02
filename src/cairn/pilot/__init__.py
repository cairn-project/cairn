"""cairn.pilot — the benign pilot cause + end-to-end runner.

Makes the engine backbone RUNNABLE as a system over a concrete, benign,
deterministic cause: open-source-license classification over a handful of bundled
public-domain-style text snippets (no network, no PII). It adds NO new trust or
ledger primitive — it WIRES the real backbone end-to-end:

  cause.py    the benign cause: snippet fixtures -> work-unit dicts + the
              per-unit gold answers + the deterministic classification rule
  adapter.py  PilotNodeAdapter — a deterministic offline node (the designated
              model stand-in via the Adapter seam; honest + wrong modes)
  runner.py   run_pilot(...) -> PilotRunSummary, driving the REAL ledger / execute
              / verify / transparency-log layers
  live_smoke.py  live_smoke(...) -> PilotRunSummary, the SAME backbone but with one
              node driven by the live ``ClaudeCliAdapter`` (real Claude)

DEFERRED (later phases): other live-model adapters, distribution storefronts,
cause-discovery/vetting governance, the escalation/action engine, network
transport.
"""

from __future__ import annotations

from .adapter import PilotNodeAdapter
from .cause import (
    HONEYPOT_SNIPPET_ID,
    PILOT_CAUSE_ID,
    build_pilot_units,
    build_unit,
    classify_license,
    gold_answer,
    honeypot_snippet,
    load_snippets,
    unit_task_id,
)
from .live_smoke import LIVE_FAMILY, REFERENCE_FAMILY, live_smoke
from .runner import PilotRunSummary, UnitRunResult, run_pilot

__all__ = [
    # cause
    "PILOT_CAUSE_ID",
    "HONEYPOT_SNIPPET_ID",
    "load_snippets",
    "build_pilot_units",
    "build_unit",
    "classify_license",
    "gold_answer",
    "honeypot_snippet",
    "unit_task_id",
    # adapter
    "PilotNodeAdapter",
    # runner
    "run_pilot",
    "PilotRunSummary",
    "UnitRunResult",
    # live smoke
    "live_smoke",
    "LIVE_FAMILY",
    "REFERENCE_FAMILY",
]
