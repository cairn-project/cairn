"""cairn.capture — the inert evidence-bundle (examination-packet) capture seam.

The trust-gated CAPTURE operator freezes a live target into a STATIC, INERT
``ExaminationPacket``; the OPEN analysis layer judges that packet WITHOUT anyone
re-visiting the live target. Capture happens once (gated, fail-closed); analysis
consumes the frozen content-addressed artifact (open). The load-bearing safety
principle — the analyst (and their AI) only ever sees the inert bundle — is
STRUCTURALLY enforced: the packet/view carry only static JSON observations + an
opaque ``target_ref``, with NO live locator and NO fetch surface, so "re-visit the
live target" is not an expressible operation on the analysis path.

  packet.py  Observation + ExaminationPacket + AnalysisView — the inert artifact +
             the read-only analyst-facing projection.
  port.py    CapturePort protocol + StaticDocumentCapturePort (deterministic,
             OFFLINE; reads a synthetic LOCAL document fixture; no browser/network).
  gate.py    CaptureGate + CaptureGrant — the trust-gated, fail-closed CAPTURE role.
  store.py   capture_packet(...) (gated produce) + load_packet_for_analysis(...)
             (open load -> AnalysisView).

Composes on the engine (ledger blob store + transparency log) + the cause layer
(a packet may carry a cause_id) + the contribute layer's gating POSTURE. Forks
nothing.

DEFERRED (later, separately-security-reviewed waves): the real headless-browser /
IP-masked capture port (this wave ships only the deterministic offline fixture
port behind the same CapturePort seam), a ``cairn capture`` CLI, real rendered-pixel
screenshots, retention/redaction policy, and any sensitive capture target.
"""

from __future__ import annotations

from .gate import CaptureGate, CaptureGateError, CaptureGrant
from .packet import (
    OBS_CONTENT_HASH,
    OBS_DOM_TEXT,
    OBS_REGISTRATION_METADATA,
    OBS_RENDERED_TEXT,
    OBS_RESPONSE_HEADERS,
    OBSERVATION_KINDS,
    AnalysisView,
    ExaminationPacket,
    Observation,
)
from .port import (
    METHOD_STATIC_DOCUMENT_FIXTURE,
    CapturePort,
    StaticDocumentCapturePort,
)
from .store import (
    CaptureError,
    CaptureRefused,
    PacketNotFound,
    capture_packet,
    load_packet_for_analysis,
)

__all__ = [
    # packet
    "Observation",
    "ExaminationPacket",
    "AnalysisView",
    "OBSERVATION_KINDS",
    "OBS_RENDERED_TEXT",
    "OBS_DOM_TEXT",
    "OBS_RESPONSE_HEADERS",
    "OBS_REGISTRATION_METADATA",
    "OBS_CONTENT_HASH",
    # port
    "CapturePort",
    "StaticDocumentCapturePort",
    "METHOD_STATIC_DOCUMENT_FIXTURE",
    # gate
    "CaptureGate",
    "CaptureGrant",
    "CaptureGateError",
    # store flow
    "capture_packet",
    "load_packet_for_analysis",
    "CaptureError",
    "CaptureRefused",
    "PacketNotFound",
]
