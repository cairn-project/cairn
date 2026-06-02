"""The inert examination packet — a frozen, content-addressed evidence bundle.

This is the load-bearing safety abstraction. A
gated CAPTURE operator turns a live target into a STATIC, INERT
``ExaminationPacket``; the open analysis layer judges that packet WITHOUT anyone
re-visiting the live target. The packet contains ONLY static, JSON-serializable
observations + capture provenance — nothing executable, and (critically) NO live
locator and NO fetch surface.

Why this STRUCTURALLY forbids "re-visit the live target":
  * An ``Observation`` is a frozen ``(kind, content, content_hash)`` record whose
    ``content`` is plain JSON (a recorded text snapshot, a header map, a metadata
    map, a hash) — never a callable, never a URL.
  * An ``ExaminationPacket`` carries an OPAQUE ``target_ref`` (a fixture id /
    content-address label), NOT a dereferenceable live locator. The schema has no
    ``url`` / ``locator`` / ``endpoint`` field by construction.
  * The analyst-facing ``AnalysisView`` exposes ONLY the frozen observations + the
    opaque provenance fields; it has NO ``fetch`` / ``refetch`` / ``visit`` /
    ``open`` method and no live-locator attribute.
So the only operation an analyst can perform is reading frozen data. "Re-visit the
live target" is not an expressible operation on the analysis path — it is excluded
by the ABSENCE of any locator/fetch surface, not merely by policy.

Content-addressing mirrors the engine: ``content_hash`` /
``packet_hash`` are sha256 of canonical JSON, so identical capture input yields an
identical packet hash (dedup + tamper-evidence). The ``packet_hash`` equals the
blob content key the packet is stored under (``store.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ..ledger.blobstore import canonical_json, content_key

# Observation kinds — a fixed, descriptive vocabulary. None of these is
# executable; each names the STATIC datum a capture recorded.
OBS_RENDERED_TEXT = "RENDERED_TEXT"
OBS_DOM_TEXT = "DOM_TEXT"
OBS_RESPONSE_HEADERS = "RESPONSE_HEADERS"
OBS_REGISTRATION_METADATA = "REGISTRATION_METADATA"
OBS_CONTENT_HASH = "CONTENT_HASH"

OBSERVATION_KINDS: frozenset[str] = frozenset(
    {
        OBS_RENDERED_TEXT,
        OBS_DOM_TEXT,
        OBS_RESPONSE_HEADERS,
        OBS_REGISTRATION_METADATA,
        OBS_CONTENT_HASH,
    }
)


def _is_plain_json(value: Any) -> bool:
    """True iff ``value`` is composed only of JSON primitives + list/dict.

    The inert guarantee: a captured observation's ``content`` must be plain data —
    never a callable or any other non-JSON object. Enforced at construction so a
    packet can NEVER carry executable content.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return True
    if isinstance(value, list):
        return all(_is_plain_json(v) for v in value)
    if isinstance(value, dict):
        return all(
            isinstance(k, str) and _is_plain_json(v) for k, v in value.items()
        )
    return False


@dataclass(frozen=True)
class Observation:
    """One static datum a capture recorded (inert; JSON-serializable).

    ``content`` is plain JSON (a text snapshot, a header map, a metadata map, a
    hash) — validated non-executable at construction. ``content_hash`` is the
    sha256 of the canonical JSON of ``content`` (self-attesting integrity).
    """

    kind: str
    content: Any
    content_hash: str

    @staticmethod
    def create(kind: str, content: Any) -> "Observation":
        """Build an observation, computing its content hash and enforcing inertness.

        Raises ``ValueError`` on an unknown kind or non-JSON (potentially
        executable) content — the packet can never carry executable content.
        """
        if kind not in OBSERVATION_KINDS:
            raise ValueError(
                f"unknown observation kind {kind!r}; "
                f"valid: {sorted(OBSERVATION_KINDS)}"
            )
        if not _is_plain_json(content):
            raise ValueError(
                "observation content must be plain JSON data (no callables / "
                "non-JSON objects); the packet must stay inert"
            )
        return Observation(
            kind=kind,
            content=content,
            content_hash=content_key(canonical_json(content)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "content": self.content,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Observation":
        # Reconstruct AND re-verify the content hash from the stored content, so a
        # tampered observation is caught on load (content-addressing integrity).
        recomputed = content_key(canonical_json(d["content"]))
        if recomputed != d["content_hash"]:
            raise ValueError(
                "observation content_hash mismatch (tampered observation)"
            )
        if not _is_plain_json(d["content"]):
            raise ValueError("observation content is not plain JSON (not inert)")
        return cls(
            kind=d["kind"], content=d["content"], content_hash=d["content_hash"]
        )


def _packet_material(
    *,
    target_ref: str,
    cause_id: Optional[str],
    observations: tuple[Observation, ...],
    captured_at: float,
    captured_by: str,
    capture_method: str,
) -> dict[str, Any]:
    """The immutable fields the packet hash commits to (deterministic ordering)."""
    return {
        "target_ref": target_ref,
        "cause_id": cause_id,
        "observations": [o.to_dict() for o in observations],
        "captured_at": captured_at,
        "captured_by": captured_by,
        "capture_method": capture_method,
    }


@dataclass(frozen=True)
class ExaminationPacket:
    """A frozen, content-addressed, INERT evidence bundle.

    Every field is static recorded data. ``target_ref`` is an OPAQUE label (a
    fixture id / content-address), NOT a dereferenceable live locator — there is no
    ``url`` / ``endpoint`` field anywhere on the packet. ``packet_hash`` is the
    sha256 of the immutable fields' canonical JSON; it is the bundle's content
    address and equals the blob key the packet is stored under.
    """

    target_ref: str
    cause_id: Optional[str]
    observations: tuple[Observation, ...]
    captured_at: float
    captured_by: str
    capture_method: str
    packet_hash: str

    @staticmethod
    def create(
        *,
        target_ref: str,
        observations: tuple[Observation, ...],
        captured_at: float,
        captured_by: str,
        capture_method: str,
        cause_id: Optional[str] = None,
    ) -> "ExaminationPacket":
        """Build a packet, computing its content-address ``packet_hash``."""
        material = _packet_material(
            target_ref=target_ref,
            cause_id=cause_id,
            observations=observations,
            captured_at=captured_at,
            captured_by=captured_by,
            capture_method=capture_method,
        )
        return ExaminationPacket(
            target_ref=target_ref,
            cause_id=cause_id,
            observations=observations,
            captured_at=captured_at,
            captured_by=captured_by,
            capture_method=capture_method,
            packet_hash=content_key(canonical_json(material)),
        )

    def to_dict(self) -> dict[str, Any]:
        d = _packet_material(
            target_ref=self.target_ref,
            cause_id=self.cause_id,
            observations=self.observations,
            captured_at=self.captured_at,
            captured_by=self.captured_by,
            capture_method=self.capture_method,
        )
        d["packet_hash"] = self.packet_hash
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ExaminationPacket":
        """Reconstruct a packet, RE-DERIVING ``packet_hash`` from its material.

        Accepts either the stored MATERIAL form (no ``packet_hash`` key — the form
        the blob store holds, so the blob content key == packet_hash) or the full
        ``to_dict`` form (with ``packet_hash``). In both cases packet_hash is
        recomputed from the immutable material; a provided packet_hash that does
        not match is rejected (tamper-evidence).
        """
        observations = tuple(Observation.from_dict(o) for o in d["observations"])
        material = _packet_material(
            target_ref=d["target_ref"],
            cause_id=d.get("cause_id"),
            observations=observations,
            captured_at=d["captured_at"],
            captured_by=d["captured_by"],
            capture_method=d["capture_method"],
        )
        packet_hash = content_key(canonical_json(material))
        if "packet_hash" in d and d["packet_hash"] != packet_hash:
            raise ValueError("packet_hash mismatch (tampered packet)")
        return cls(
            target_ref=d["target_ref"],
            cause_id=d.get("cause_id"),
            observations=observations,
            captured_at=d["captured_at"],
            captured_by=d["captured_by"],
            capture_method=d["capture_method"],
            packet_hash=packet_hash,
        )

    def material_dict(self) -> dict[str, Any]:
        """The immutable material the ``packet_hash`` commits to (no packet_hash).

        This is the form stored in the content-addressed blob store, so the blob's
        content key equals ``packet_hash`` by construction.
        """
        return _packet_material(
            target_ref=self.target_ref,
            cause_id=self.cause_id,
            observations=self.observations,
            captured_at=self.captured_at,
            captured_by=self.captured_by,
            capture_method=self.capture_method,
        )


@dataclass(frozen=True)
class AnalysisView:
    """The analyst-facing projection of a packet (read-only, no live surface).

    This is the ONLY thing the open analysis layer consumes. It exposes the frozen
    observations + the opaque provenance fields and provides read-only conveniences
    for reading captured content. It deliberately has NO live-locator attribute and
    NO ``fetch`` / ``refetch`` / ``visit`` / ``open`` method — "re-visit the live
    target" is not expressible from a view.
    """

    packet_hash: str
    target_ref: str
    cause_id: Optional[str]
    captured_at: float
    captured_by: str
    capture_method: str
    observations: tuple[Observation, ...]

    @classmethod
    def of(cls, packet: ExaminationPacket) -> "AnalysisView":
        return cls(
            packet_hash=packet.packet_hash,
            target_ref=packet.target_ref,
            cause_id=packet.cause_id,
            captured_at=packet.captured_at,
            captured_by=packet.captured_by,
            capture_method=packet.capture_method,
            observations=packet.observations,
        )

    def observations_of_kind(self, kind: str) -> tuple[Observation, ...]:
        """All frozen observations of a given kind (read-only)."""
        return tuple(o for o in self.observations if o.kind == kind)

    def rendered_text(self) -> Optional[str]:
        """The captured rendered-text snapshot, if one was recorded (read-only)."""
        for obs in self.observations_of_kind(OBS_RENDERED_TEXT):
            content = obs.content
            if isinstance(content, dict) and "text" in content:
                return content["text"]
            if isinstance(content, str):
                return content
        return None
