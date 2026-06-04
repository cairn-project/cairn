"""capture_packet (gated) + load_packet_for_analysis (open)."""

from __future__ import annotations

import pytest

from cairn.capture import (
    CaptureGate,
    CaptureRefused,
    PacketNotFound,
    StaticDocumentCapturePort,
    capture_packet,
    load_packet_for_analysis,
)
from cairn.ledger import FixedClock, Ledger, verify_log
from cairn.ledger.translog import KIND_PACKET_CAPTURED

_KEY = b"capture-test-key-not-secret"


def _ledger(tmp_path) -> Ledger:
    return Ledger(tmp_path / "ledger", FixedClock(start=0.0), signing_key=_KEY)


def _granted(ledger) -> CaptureGate:
    gate = CaptureGate(ledger)
    gate.grant("op-1", granted_by="anchor", scope_summary="benign synthetic docs")
    return gate


def test_capture_refused_for_ungranted_node(tmp_path):
    ledger = _ledger(tmp_path)
    gate = CaptureGate(ledger)  # no grant
    with pytest.raises(CaptureRefused):
        capture_packet(
            StaticDocumentCapturePort(),
            gate=gate,
            ledger=ledger,
            node_id="op-1",
        )
    # Fail-closed: nothing was captured/logged.
    kinds = [e.kind for e in ledger.translog.entries()]
    assert KIND_PACKET_CAPTURED not in kinds


def test_capture_composes_on_ledger_and_translog(tmp_path):
    #: packet content-addressed at packet_hash; PACKET_CAPTURED logged.
    ledger = _ledger(tmp_path)
    gate = _granted(ledger)
    packet = capture_packet(
        StaticDocumentCapturePort(),
        gate=gate,
        ledger=ledger,
        node_id="op-1",
        cause_id="cause-abc",
    )
    # Blob present, keyed by its content address == packet_hash.
    assert ledger.blobs.has(packet.packet_hash)
    # PACKET_CAPTURED on the same transparency log; log verifies.
    kinds = [e.kind for e in ledger.translog.entries()]
    assert kinds.count(KIND_PACKET_CAPTURED) == 1
    assert verify_log(ledger.translog._path).ok  # noqa: SLF001


def test_revoke_then_capture_re_refuses(tmp_path):
    ledger = _ledger(tmp_path)
    gate = _granted(ledger)
    gate.revoke("op-1")
    with pytest.raises(CaptureRefused):
        capture_packet(StaticDocumentCapturePort(), gate=gate, ledger=ledger, node_id="op-1")


def test_load_for_analysis_is_open_and_returns_view(tmp_path):
    #: loading a packet needs NO gate; returns an AnalysisView the
    # analyst can read + judge from alone.
    ledger = _ledger(tmp_path)
    gate = _granted(ledger)
    packet = capture_packet(StaticDocumentCapturePort(), gate=gate, ledger=ledger, node_id="op-1")

    # No gate is passed here — analysis is open.
    view = load_packet_for_analysis(packet.packet_hash, ledger=ledger)
    assert view.packet_hash == packet.packet_hash

    # A deterministic example judge reaches a verdict from the VIEW ALONE.
    text = view.rendered_text() or ""
    is_open_licence = "cc-by" in text.lower()
    assert is_open_licence is True


def test_load_unknown_packet_raises(tmp_path):
    ledger = _ledger(tmp_path)
    with pytest.raises(PacketNotFound):
        load_packet_for_analysis("0" * 64, ledger=ledger)
