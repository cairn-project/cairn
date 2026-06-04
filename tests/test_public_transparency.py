"""Public transparency read-surfaces tests.

Drives the REAL public-read entry points over a REAL Ledger + transparency log.
Offline, deterministic (FixedClock), synthetic benign data only. The redaction
boundary is asserted STRUCTURALLY (the public view dataclasses have no field that
could carry raw content / PII), and tamper-detection is asserted by mutating an
on-disk log entry and re-running the public verify.
"""

from __future__ import annotations

from dataclasses import fields

import pytest

from cairn.cause import CauseRegistry, CauseStatus, five_frame_gate_check
from cairn.cause.model import FRAME_KEYS
from cairn.ledger import FixedClock, Ledger
from cairn.public import (
    FORBIDDEN_PUBLIC_FIELDS,
    PublicCauseView,
    PublicLogEntryView,
    PublicTransparency,
    PublicVettedOutcomeView,
    list_public_log,
    list_published_causes,
    list_vetted_outcomes,
    public_verify_log,
)
from cairn.vetting import AutomatedVerdict, FindingVetQueue

_KEY = b"cairn-public-test-key-not-secret"


def _ledger(tmp_path) -> Ledger:
    return Ledger(tmp_path / "ledger", FixedClock(start=0.0), signing_key=_KEY)


def _draft(name="Benign cause", by="req"):
    return {
        "name": name,
        "description": "a generic, mission-neutral cause",
        "target_conduct": "some publicly-observable conduct",
        "protected_boundary": "no persons profiled/stored/reported",
        "output_schema_ref": "result_v0",
        "partner_of_record_posture": "maintainer is actor-of-record",
        "created_by": by,
        "five_frame": {k: {"frame": k, "claim": f"{k} ok", "passes": True} for k in FRAME_KEYS},
    }


def _complete_gate():
    return five_frame_gate_check(dict.fromkeys(FRAME_KEYS, True))


def _approve(reg: CauseRegistry, name: str) -> str:
    cause = reg.submit_cause_request(_draft(name=name))
    reg.decide_cause(
        cause.cause_id,
        approve=True,
        reason="ok",
        decider="anchor",
        gate_result=_complete_gate(),
    )
    return cause.cause_id


# --- published-causes projection reuses the listing gate -----------


def test_published_causes_reuse_listing_gate_only_approved(tmp_path):
    ledger = _ledger(tmp_path)
    reg = CauseRegistry(ledger)
    approved_id = _approve(reg, "approved-one")
    # second left requested, third rejected
    reg.submit_cause_request(_draft(name="still-requested"))
    rej = reg.submit_cause_request(_draft(name="rejected-one"))
    reg.decide_cause(
        rej.cause_id, approve=False, reason="no", decider="anchor", gate_result=_complete_gate()
    )

    views = list_published_causes(ledger)
    assert [v.cause_id for v in views] == [approved_id]
    assert views[0].status == CauseStatus.APPROVED.value
    assert views[0].name == "approved-one"


# --- public-cause view exposes only the public summary -------------


def test_public_cause_view_omits_internal_provenance_fields(tmp_path):
    ledger = _ledger(tmp_path)
    reg = CauseRegistry(ledger)
    _approve(reg, "summary-check")
    view = list_published_causes(ledger)[0]

    field_names = {f.name for f in fields(PublicCauseView)}
    # public summary present
    assert {
        "cause_id",
        "name",
        "description",
        "status",
        "five_frame",
        "partner_of_record_posture",
    } <= field_names
    # internal decision/requester provenance ABSENT by construction
    assert {"decision_reason", "decided_by", "created_by"} & field_names == set()
    assert view.frames_self_passed == len(FRAME_KEYS)
    assert view.frames_self_total == len(FRAME_KEYS)


# --- vetted-outcomes reuse the finding-vet verdict state -----------


def test_vetted_outcomes_reuse_verdict_state_pending_excluded(tmp_path):
    ledger = _ledger(tmp_path)
    queue = FindingVetQueue(ledger)
    av = AutomatedVerdict(flag_label="flagged", confidence=0.9)

    f_routable = queue.flag(packet_hash="aa" * 32, automated_verdict=av, flagged_by="node-1")
    queue.record_verdict(
        f_routable.finding_hash, routable=True, reason="confirmed", reviewer_id="rev-1"
    )
    f_reject = queue.flag(packet_hash="bb" * 32, automated_verdict=av, flagged_by="node-1")
    queue.record_verdict(
        f_reject.finding_hash, routable=False, reason="benign", reviewer_id="rev-2"
    )
    # third left pending (no verdict)
    queue.flag(packet_hash="cc" * 32, automated_verdict=av, flagged_by="node-1")

    views = list_vetted_outcomes(ledger)
    by_packet = {v.packet_hash: v for v in views}
    assert set(by_packet) == {"aa" * 32, "bb" * 32}  # pending one absent
    assert by_packet["aa" * 32].verdict == "routable"
    assert by_packet["aa" * 32].reviewer_of_record == "rev-1"
    assert by_packet["bb" * 32].verdict == "rejected"


# --- vetted-outcome view is redacted by construction ---------------


def test_vetted_outcome_view_redacted_by_construction(tmp_path):
    field_names = {f.name for f in fields(PublicVettedOutcomeView)}
    assert field_names == {
        "packet_hash",
        "flag_label",
        "verdict",
        "reviewer_of_record",
        "decided_at",
    }
    # no field can carry raw content / observation bytes / analysis / PII
    assert field_names & FORBIDDEN_PUBLIC_FIELDS == set()
    # and the dataclass cannot be constructed with such data — no such parameter
    with pytest.raises(TypeError):
        PublicVettedOutcomeView(  # type: ignore[call-arg]
            packet_hash="aa",
            flag_label="x",
            verdict="routable",
            reviewer_of_record="r",
            decided_at=0.0,
            content="SECRET RAW BODY",
        )


# --- public log verify composes on verify_log ----------------------


def test_public_verify_log_matches_verify_log_ok(tmp_path):
    ledger = _ledger(tmp_path)
    reg = CauseRegistry(ledger)
    _approve(reg, "vl-check")
    result = public_verify_log(ledger)
    assert result.ok is True
    # length equals the number of recorded entries (request + decision = 2 here)
    assert result.length == len(list_public_log(ledger))
    assert result.length == 2


# --- redacted public log view exposes only the chain skeleton ------


def test_public_log_view_is_chain_skeleton_no_payload(tmp_path):
    ledger = _ledger(tmp_path)
    reg = CauseRegistry(ledger)
    _approve(reg, "log-skeleton")

    field_names = {f.name for f in fields(PublicLogEntryView)}
    assert field_names == {"index", "kind", "entry_hash", "prev_hash", "recorded_at"}
    assert "payload" not in field_names
    entries = ledger.translog.entries()
    views = list_public_log(ledger)
    assert len(views) == len(entries) == 2
    assert [v.entry_hash for v in views] == [e.entry_hash for e in entries]


# --- read-only: PublicTransparency exposes no setter ---------------


def test_public_transparency_is_read_only_no_setter(tmp_path):
    public = PublicTransparency(_ledger(tmp_path))
    public_methods = [
        m for m in dir(public) if not m.startswith("_") and callable(getattr(public, m))
    ]
    # every public method is a read (list_* / *_verify_log); none mutates
    assert all(m.startswith("list_") or m.endswith("_verify_log") for m in public_methods), (
        public_methods
    )


# --- OUTCOME-ALTITUDE: end-to-end on a fresh ledger + tamper -------
# outcome-altitude: true


def test_outcome_altitude_public_surfaces_end_to_end_and_tamper(tmp_path):
    """Drive the REAL public-read entry points end-to-end on a FRESH ledger.

    Publish a cause (request -> human-vetted approve) + record a human-vetted
    finding (flag -> ROUTABLE verdict). The public surfaces must show EXACTLY the
    redacted public projection (the published cause; the routable vetted outcome
    with only redacted fields; the redacted log skeleton) and nothing privileged.
    public_verify_log returns ok. THEN tamper an on-disk log entry -> public verify
    reports failure. No pre-arranged in-memory state; only the production entry
    points + the real ledger on disk.
    """
    ledger = _ledger(tmp_path)
    reg = CauseRegistry(ledger)
    queue = FindingVetQueue(ledger)

    # publish a cause through the real gated path
    cause = reg.submit_cause_request(_draft(name="court-grade-cause"))
    reg.decide_cause(
        cause.cause_id,
        approve=True,
        reason="meets all five frames",
        decider="vetter-A",
        gate_result=_complete_gate(),
    )

    # record a human-vetted ROUTABLE finding through the real gate
    av = AutomatedVerdict(flag_label="flagged", confidence=0.97)
    finding = queue.flag(packet_hash="de" * 32, automated_verdict=av, flagged_by="node-7")
    queue.record_verdict(
        finding.finding_hash, routable=True, reason="human-confirmed", reviewer_id="vetter-B"
    )

    # --- public surfaces show exactly the redacted projection ---
    causes = list_published_causes(ledger)
    assert [c.cause_id for c in causes] == [cause.cause_id]
    assert causes[0].name == "court-grade-cause"

    outcomes = list_vetted_outcomes(ledger)
    assert len(outcomes) == 1
    o = outcomes[0]
    assert o.packet_hash == "de" * 32
    assert o.flag_label == "flagged"
    assert o.verdict == "routable"
    assert o.reviewer_of_record == "vetter-B"
    # redacted: the outcome dict carries ONLY the redacted keys (no raw content / PII)
    assert set(o.to_dict()) == {
        "packet_hash",
        "flag_label",
        "verdict",
        "reviewer_of_record",
        "decided_at",
    }

    # redacted log skeleton: no payload key on any public entry
    log_views = list_public_log(ledger)
    assert log_views, "expected log entries"
    for v in log_views:
        assert set(v.to_dict()) == {
            "index",
            "kind",
            "entry_hash",
            "prev_hash",
            "recorded_at",
        }

    # public verify is OK on the untampered ledger
    assert public_verify_log(ledger).ok is True

    # --- tamper one on-disk log entry -> public verify reports failure ---
    log_path = ledger.translog._path  # noqa: SLF001
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 2
    # flip a payload byte in the second entry (the cause decision)
    lines[1] = lines[1].replace("meets all five frames", "meets four frames")
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    tampered = public_verify_log(ledger)
    assert tampered.ok is False
    assert tampered.failed_index == 1
