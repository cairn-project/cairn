"""cairn.scenario — the value-demo scenario (dump-for-review, NEVER send).

Drives the REAL engine end-to-end over a benign, public, NON-PERSON topic
(stale/broken open-data feed records) and DUMPS a human-review packet per finding
instead of sending anything. It closes the pilot-vs-claims credibility gap: the
pilot exercises only the verify backbone and SKIPS the human gate; this scenario
shows the full value loop (detect → AI-analyze → find the real reporting org →
build evidence → REAL human gate) and dumps for review with NO egress.

Composition (reuse, fork nothing):
  seed.py          inert open-data seed records + the deterministic defect rule +
                   the work-unit builder (output carries a numeric defect score)
  node.py          ScenarioReferenceNode — deterministic offline analysis node
  org_finder.py    ReportingOrgFinder — REAL public org lookup; fails closed
  packet_builder.py + dump.py   banner-labeled review-dump artefacts + writer
  runner.py        run_scenario / review_scenario / list_scenario — the
                   orchestrator over the REAL adapter / verify / bridge / Gate-2
                   / ledger, terminating at "human-vetted + dumped", never "sent".

SAFETY (structural): no egress code path; public-info-only read-only org lookups;
the subject is always a dataset record (a thing), never a person; every dumped
artefact carries the FOR REVIEW — NOT SENT banner; the finder fails closed on an
unresolvable contact.
"""

from __future__ import annotations

from .org_finder import ReportingOrgFinder, ResolvedOrg
from .packet_builder import REVIEW_BANNER, ReviewArtefacts, build_review_artefacts
from .runner import (
    ScenarioFindingResult,
    ScenarioListing,
    ScenarioReviewResult,
    ScenarioRunSummary,
    list_scenario,
    review_scenario,
    run_scenario,
)
from .seed import (
    SCENARIO_CAUSE_ID,
    SCENARIO_FLAG_LABEL,
    build_scenario_unit,
    build_scenario_units,
    classify_defect,
    load_seed_records,
)

__all__ = [
    "SCENARIO_CAUSE_ID",
    "SCENARIO_FLAG_LABEL",
    "REVIEW_BANNER",
    "load_seed_records",
    "classify_defect",
    "build_scenario_unit",
    "build_scenario_units",
    "ReportingOrgFinder",
    "ResolvedOrg",
    "build_review_artefacts",
    "ReviewArtefacts",
    "run_scenario",
    "review_scenario",
    "list_scenario",
    "ScenarioRunSummary",
    "ScenarioFindingResult",
    "ScenarioReviewResult",
    "ScenarioListing",
]
