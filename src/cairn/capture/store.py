"""capture + load flow — the gated produce + the OPEN analysis load.

``capture_packet`` is the trust-gated, fail-closed producer: only a node with an
ACTIVE capture-role grant may freeze a target into an inert ``ExaminationPacket``,
which is content-addressed in ``ledger.blobs`` (its blob key == ``packet_hash``)
and recorded with a ``PACKET_CAPTURED`` entry on the SAME transparency log.

``load_packet_for_analysis`` is the OPEN consumer: anyone may load a captured
packet BY ITS CONTENT KEY and receive an ``AnalysisView`` — the only thing the
analysis layer ever sees. The analyst is handed the packet, never a live target;
the view has no live-locator/fetch surface (``packet.py`` §3), so "re-visit the
live target" is not expressible. Capture happens once (gated); analysis consumes
the frozen artifact (open).

Composes on the engine (``ledger.blobs`` content-addressing + ``TransparencyLog``)
and reuses the cause layer (a packet may carry a ``cause_id``). Forks nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..ledger.ledger import Ledger
from ..ledger.translog import KIND_PACKET_CAPTURED
from .gate import CaptureGate
from .packet import AnalysisView, ExaminationPacket
from .port import CapturePort


class CaptureError(Exception):
    """Base error for an invalid capture/load operation."""


class CaptureRefused(CaptureError):
    """Raised when capture is refused — the node lacks the CAPTURE role (fail closed)."""


class PacketNotFound(CaptureError):
    """Raised when a packet content key is absent from the blob store."""


def capture_packet(
    port: CapturePort,
    *,
    gate: CaptureGate,
    ledger: Ledger,
    node_id: str,
    cause_id: Optional[str] = None,
) -> ExaminationPacket:
    """Freeze a target into an inert packet — GATED, fail-closed (BUILD-PLAN §5).

    Args:
      port: the capture port (the deterministic offline ``StaticDocumentCapturePort``
        in this wave) that yields the inert observations.
      gate: the ``CaptureGate`` deciding whether ``node_id`` holds the CAPTURE role.
      ledger: the real ``Ledger`` (carries its injected clock + blob store + log).
      node_id: the capturing operator's node id (must hold an ACTIVE grant).
      cause_id: the cause this packet belongs to, if any (reuse the cause layer).

    Raises ``CaptureRefused`` if the node is not granted the capture role. Returns
    the produced ``ExaminationPacket``.
    """
    # --- fail-closed trust gate (producing a packet is privileged) ----------
    if not gate.is_granted(node_id):
        raise CaptureRefused(
            f"node {node_id!r} is not granted the CAPTURE role; producing an "
            "examination packet is a privileged operation (fail-closed gate). "
            "Analysis of an existing packet is open."
        )

    observations = port.capture()  # deterministic, offline; no network, no browser
    packet = ExaminationPacket.create(
        target_ref=port.target_ref,
        observations=observations,
        captured_at=ledger._clock.now(),  # noqa: SLF001
        captured_by=node_id,
        capture_method=port.method,
        cause_id=cause_id,
    )

    # Content-address the inert packet in the ledger blob store; the blob key
    # equals packet_hash by construction (the stored material is exactly what the
    # packet hash commits to — see ``ExaminationPacket.material_dict``).
    blob_key = ledger.blobs.put_json(packet.material_dict())
    assert blob_key == packet.packet_hash  # content-address invariant

    # Index the packet under packets/<packet_hash> for discovery.
    packets_dir = Path(ledger._root) / "packets"  # noqa: SLF001
    packets_dir.mkdir(parents=True, exist_ok=True)
    (packets_dir / packet.packet_hash).write_text(blob_key)

    # Audit-log the capture on the SAME append-only transparency log.
    ledger.translog.append(
        KIND_PACKET_CAPTURED,
        {
            "packet_hash": packet.packet_hash,
            "target_ref": packet.target_ref,
            "cause_id": cause_id,
            "captured_by": node_id,
            "capture_method": packet.capture_method,
            "observation_count": len(observations),
        },
    )
    return packet


def load_packet_for_analysis(
    packet_hash: str, *, ledger: Ledger
) -> AnalysisView:
    """Load a captured packet BY ITS CONTENT KEY and return an ``AnalysisView``.

    OPEN — no gate. This is the ONLY thing the analysis layer consumes: a frozen,
    inert view of the captured observations. The analyst never touches a live
    target (the view has no live-locator/fetch surface). Raises ``PacketNotFound``
    if the content key is absent.
    """
    if not ledger.blobs.has(packet_hash):
        raise PacketNotFound(f"no examination packet at content key: {packet_hash}")
    packet = ExaminationPacket.from_dict(ledger.blobs.get_json(packet_hash))
    return AnalysisView.of(packet)
