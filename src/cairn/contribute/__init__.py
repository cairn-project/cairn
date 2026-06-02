"""cairn.contribute — the contributor opt-in + cause-scoped run loop.

The DEMAND side of the engine: how a contributor consents to put their AI capacity
toward a SPECIFIC approved cause, and how that cause's bound work units then run
end-to-end over the real engine. Composes on the cause layer (CauseRegistry +
WorkUnitRegistry) + the execute/verify/ledger engine — it forks nothing.

  model.py   ConsentRecord — the durable, revocable informed-consent record
  optin.py   OptInRegistry — gated opt-in (REFUSES a non-listable cause) + revoke
  run.py     run_cause(...) -> CauseRunSummary — the gated, opted-in run loop

DEFERRED (later phases): real-model contribute adapters (only the offline pilot
mock here), capture/detection logic, vetting UI, distribution ramps, the
escalation/action engine, network transport.
"""

from __future__ import annotations

from .model import ConsentRecord
from .optin import OptInError, OptInRefused, OptInRegistry
from .run import CauseRunError, CauseRunRefused, CauseRunSummary, run_cause

__all__ = [
    "ConsentRecord",
    "OptInRegistry",
    "OptInError",
    "OptInRefused",
    "run_cause",
    "CauseRunSummary",
    "CauseRunError",
    "CauseRunRefused",
]
