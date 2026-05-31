"""Public transparency read-surfaces — the externally-legible, read-only projection.

The "court-grade / auditable / maximally transparent" frame (REQUIREMENTS Frame 4)
made concrete: anyone (a recruit, journalist, partner institution, skeptic) can see
what Cairn is doing and independently verify its integrity WITHOUT privileged
access. This module is a pure PROJECTION over already-public state — it adds NO
write path, NO mutation, and NO new trust surface.

It composes, reimplementing nothing:
  * Published causes reuse the EXISTING listing gate
    ``CauseRegistry.list_causes(status_filter=None)`` (approved/live only — a
    requested/rejected/paused cause never appears).
  * Vetted outcomes reuse the finding-vetting verdict state
    (``FindingVetQueue.list_reviewed`` / ``finding_state``) — only human-verified
    ROUTABLE/REJECTED findings.
  * Public log verify reuses the EXISTING independent ``verify_log`` verbatim, plus
    a redacted skeleton view over ``TransparencyLog.entries``.

REDACTION BY CONSTRUCTION (safety-load-bearing): the public projection dataclasses
HAVE NO FIELD that can carry raw captured content, observation bytes, analysis
text, or PII. The safety comes from the projection's SHAPE — a view simply cannot
be constructed with such data because no parameter accepts it — not from a
filtering step that could be bypassed. See BUILD-PLAN-public-transparency.md §3.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from ..cause import CauseRegistry
from ..ledger import Ledger, LogVerification, TransparencyLog, verify_log
from ..vetting import FindingVetQueue


# --- public projection views (redaction by construction) ---------------------


@dataclass(frozen=True)
class PublicCauseView:
    """A published cause as the public sees it — the public summary ONLY.

    Exposes the cause's public-facing fields. Deliberately OMITS the internal
    decision/requester provenance (``decision_reason`` / ``decided_by`` /
    ``created_by``): the public surface is the cause itself, not who decided it or
    requested it. There is simply no field here to carry that — the projection's
    shape is the boundary.
    """

    cause_id: str
    name: str
    description: str
    status: str
    target_conduct: str
    protected_boundary: str
    partner_of_record_posture: str
    five_frame: dict[str, Any]
    frames_self_passed: int
    frames_self_total: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "cause_id": self.cause_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "target_conduct": self.target_conduct,
            "protected_boundary": self.protected_boundary,
            "partner_of_record_posture": self.partner_of_record_posture,
            "five_frame": self.five_frame,
            "frames_self_passed": self.frames_self_passed,
            "frames_self_total": self.frames_self_total,
        }


@dataclass(frozen=True)
class PublicVettedOutcomeView:
    """A human-verified finding outcome as the public sees it — REDACTED metadata ONLY.

    Carries the ``packet_hash`` REFERENCE (a sha256 content address — opaque, reveals
    no content), the opaque generic ``flag_label`` (the finding layer hard-codes no
    domain vocabulary), the human ``verdict`` (routable/rejected), the
    ``reviewer_of_record`` id, and the verdict timestamp. There is NO field for the
    packet's content, the observation bytes, the analysis text, the captured target,
    or any requester/subject PII — the view cannot be constructed with such data
    because no parameter accepts it. THIS IS THE REDACTION BOUNDARY.
    """

    packet_hash: str
    flag_label: str
    verdict: str
    reviewer_of_record: str
    decided_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_hash": self.packet_hash,
            "flag_label": self.flag_label,
            "verdict": self.verdict,
            "reviewer_of_record": self.reviewer_of_record,
            "decided_at": self.decided_at,
        }


@dataclass(frozen=True)
class PublicLogEntryView:
    """One transparency-log entry as the public sees it — the chain SKELETON ONLY.

    Carries ``index`` / ``kind`` / ``entry_hash`` / ``prev_hash`` / ``recorded_at``
    — the hash-chain linkage + timing that lets a human eyeball the log. There is NO
    ``payload`` field, so the (potentially identifying) entry payloads are not
    exposed. The chain is still INDEPENDENTLY verifiable because ``verify_log`` reads
    the FULL on-disk bytes itself (``public_verify_log``); this view is for human
    inspection of the skeleton, the verify is the integrity proof.
    """

    index: int
    kind: str
    entry_hash: str
    prev_hash: str
    recorded_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "kind": self.kind,
            "entry_hash": self.entry_hash,
            "prev_hash": self.prev_hash,
            "recorded_at": self.recorded_at,
        }


# Field names that MUST NOT appear on any public view (raw content / PII). Asserted
# structurally in the tests — the projection's shape is the redaction boundary.
FORBIDDEN_PUBLIC_FIELDS: frozenset[str] = frozenset(
    {
        "content",
        "observation",
        "observations",
        "analysis",
        "analysis_text",
        "raw",
        "raw_content",
        "payload",
        "pii",
        "subject",
        "target",
        "locator",
        "url",
        "decision_reason",
        "decided_by",
        "created_by",
        "reason",
    }
)


def _public_view_field_names(view_cls: type) -> set[str]:
    """The declared field names of a public view dataclass (for the structural assert)."""
    return {f.name for f in fields(view_cls)}


# --- the read-only public surface --------------------------------------------


class PublicTransparency:
    """Read-only public projection over a Cairn ledger.

    Holds read-only handles to the registries already built over the ledger and
    calls ONLY their read methods. Constructs nothing on the log, mutates no cause
    or finding. This whole class is read-only by construction — it exposes no setter.
    """

    def __init__(self, ledger: Ledger) -> None:
        self._ledger = ledger
        self._causes = CauseRegistry(ledger)
        self._findings = FindingVetQueue(ledger)

    # --- 1. published causes (AC.PUB.1 / AC.PUB.2) ---------------------------

    def list_published_causes(self) -> list[PublicCauseView]:
        """Public cause list — reuse the EXISTING listing gate (approved/live only).

        Delegates the gating to ``CauseRegistry.list_causes(status_filter=None)``,
        which returns only causes where ``Cause.is_publicly_listable`` is true. This
        module NEVER re-derives listability; a requested/rejected/paused cause is not
        returned by the gate, so it cannot appear here.
        """
        out: list[PublicCauseView] = []
        for cause in self._causes.list_causes(status_filter=None):
            verdicts = cause.five_frame.verdicts
            out.append(
                PublicCauseView(
                    cause_id=cause.cause_id,
                    name=cause.name,
                    description=cause.description,
                    status=cause.status.value,
                    target_conduct=cause.target_conduct,
                    protected_boundary=cause.protected_boundary,
                    partner_of_record_posture=cause.partner_of_record_posture,
                    five_frame=cause.five_frame.to_dict(),
                    frames_self_passed=sum(1 for v in verdicts.values() if v.passes),
                    frames_self_total=len(verdicts),
                )
            )
        return out

    # --- 2. vetted outcomes (AC.PUB.3 / AC.PUB.4) ----------------------------

    def list_vetted_outcomes(self) -> list[PublicVettedOutcomeView]:
        """Public vetted-outcome list — reuse the finding-vetting verdict state.

        One view per human-reviewed finding (``FindingVetQueue.list_reviewed``), with
        ``verdict`` reflecting ``finding_state`` (routable/rejected). A pending
        (un-reviewed) finding has no recorded verdict and never appears. The view
        carries only redacted metadata — the packet_hash REFERENCE, the opaque flag
        label, the verdict, the reviewer of record, and the timestamp.
        """
        out: list[PublicVettedOutcomeView] = []
        for item in self._findings.list_reviewed():
            verdict = item.verdict
            if verdict is None:  # pragma: no cover - list_reviewed guarantees a verdict
                continue
            finding = self._findings.load_finding(item.finding_hash)
            state = self._findings.finding_state(item.finding_hash)
            out.append(
                PublicVettedOutcomeView(
                    packet_hash=finding.packet_hash,
                    flag_label=finding.automated_verdict.flag_label,
                    verdict=state.value,
                    reviewer_of_record=verdict.reviewer_id,
                    decided_at=verdict.recorded_at,
                )
            )
        return out

    # --- 3. public log verification (AC.PUB.5 / AC.PUB.6) --------------------

    def public_verify_log(self) -> LogVerification:
        """Public independent log verify — reuse the EXISTING ``verify_log`` verbatim.

        Returns the SAME ``LogVerification`` (ok / length / head_hash / failed_index /
        reason) the engine's monitor returns, re-derived from the raw on-disk bytes
        with no trust in the stored hashes. No new verification logic is added; this
        is the existing guarantee exposed publicly.
        """
        return verify_log(self._translog_path())

    def list_public_log(self) -> list[PublicLogEntryView]:
        """Redacted append-only public log view — the chain SKELETON only.

        Per entry: index / kind / entry_hash / prev_hash / recorded_at — NOT the
        payload. The chain is still independently verifiable via ``public_verify_log``
        (which reads the full bytes); this redacted view is for human inspection.
        """
        log = TransparencyLog(self._translog_path(), self._ledger._clock)  # noqa: SLF001
        return [
            PublicLogEntryView(
                index=e.index,
                kind=e.kind,
                entry_hash=e.entry_hash,
                prev_hash=e.prev_hash,
                recorded_at=e.recorded_at,
            )
            for e in log.entries()
        ]

    # --- helpers -------------------------------------------------------------

    def _translog_path(self) -> Any:
        return self._ledger.translog._path  # noqa: SLF001


# --- module-level convenience entry points (the public-read API) -------------


def list_published_causes(ledger: Ledger) -> list[PublicCauseView]:
    """Public cause list over ``ledger`` (approved/live only — reuses the gate)."""
    return PublicTransparency(ledger).list_published_causes()


def list_vetted_outcomes(ledger: Ledger) -> list[PublicVettedOutcomeView]:
    """Public human-verified vetted-outcome list over ``ledger`` (redacted metadata)."""
    return PublicTransparency(ledger).list_vetted_outcomes()


def public_verify_log(ledger: Ledger) -> LogVerification:
    """Public independent log verify over ``ledger`` (reuses ``verify_log``)."""
    return PublicTransparency(ledger).public_verify_log()


def list_public_log(ledger: Ledger) -> list[PublicLogEntryView]:
    """Redacted public log skeleton view over ``ledger`` (no payloads)."""
    return PublicTransparency(ledger).list_public_log()
