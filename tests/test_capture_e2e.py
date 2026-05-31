"""OUTCOME-ALTITUDE e2e (AC.CAP.6) — real entry points, fresh ledger, no state.

Drives the REAL ``capture_packet`` + ``load_packet_for_analysis`` entry points end
to end on a fresh ledger with NO pre-arranged state:

  grant the capture role -> capture (inert bundle persisted + PACKET_CAPTURED
  logged) -> a SECOND actor handed ONLY the packet_hash + the ledger blob store
  (no port, no target_ref-as-URL, no live handle) loads ONLY the bundle and judges
  it -> verify_log over the produced log is ok.

This proves the load-bearing safety guarantee operationally: the analyst path
receives the inert bundle and nothing else; it cannot re-visit the live target
because no live-target surface is handed to it (and the view exposes none).
"""

from __future__ import annotations

from cairn.capture import (
    CaptureGate,
    StaticDocumentCapturePort,
    capture_packet,
    load_packet_for_analysis,
)
from cairn.ledger import FixedClock, Ledger, verify_log
from cairn.ledger.translog import KIND_PACKET_CAPTURED

_KEY = b"capture-e2e-key-not-secret"


def _analyst_judges(packet_hash: str, *, ledger: Ledger) -> dict:
    """The analyst path — handed ONLY the packet_hash + the ledger blob store.

    It is given NO capture port, NO live locator, NO live handle. It can only load
    the inert bundle and read its frozen observations. It returns a verdict derived
    solely from the bundle.
    """
    view = load_packet_for_analysis(packet_hash, ledger=ledger)
    text = (view.rendered_text() or "").lower()
    return {
        "packet_hash": view.packet_hash,
        "judged_open_licence": "cc-by" in text,
        "observation_count": len(view.observations),
    }


def test_capture_to_open_analysis_end_to_end(tmp_path):
    # Fresh ledger, no pre-arranged state.
    ledger = Ledger(tmp_path / "ledger", FixedClock(start=0.0), signing_key=_KEY)

    # 1. trust-gated capture role granted to the operator.
    gate = CaptureGate(ledger)
    gate.grant("operator-1", granted_by="anchor", scope_summary="benign fixtures")

    # 2. the gated operator captures ONCE into an inert, content-addressed bundle.
    packet = capture_packet(
        StaticDocumentCapturePort(),
        gate=gate,
        ledger=ledger,
        node_id="operator-1",
        cause_id="link-rot-audit",
    )

    # The bundle is persisted + the capture is on the transparency log.
    assert ledger.blobs.has(packet.packet_hash)
    kinds = [e.kind for e in ledger.translog.entries()]
    assert kinds.count(KIND_PACKET_CAPTURED) == 1

    # 3. a SECOND actor, handed ONLY the packet_hash + the ledger, judges the
    #    bundle from the bundle alone (no live re-visit possible / available).
    verdict = _analyst_judges(packet.packet_hash, ledger=ledger)
    assert verdict["packet_hash"] == packet.packet_hash
    assert verdict["judged_open_licence"] is True
    assert verdict["observation_count"] == len(packet.observations)

    # 4. the produced transparency log independently verifies.
    assert verify_log(ledger.translog._path).ok  # noqa: SLF001
