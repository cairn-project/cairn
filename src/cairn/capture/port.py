"""The capture port seam + the deterministic offline static-document port.

A ``CapturePort`` is the seam by which a capture turns a target into a tuple of
inert ``Observation``s. This release ships ONLY a deterministic, OFFLINE port that
reads a bundled local fixture (a synthetic static document) and emits inert
observations — NO real browser, NO real URL fetched, NO network egress.

The real headless-browser / IP-masked capture port is a DELIBERATELY DEFERRED,
separately security-reviewed later phase. That phase implements this
same ``CapturePort`` protocol; nothing about the inert-packet design changes.

A port exposes ``target_ref`` (the OPAQUE label of what was captured — a fixture
id here, NOT a live URL) and ``method`` (a provenance label for HOW it captured).
``capture()`` returns the frozen observations; it performs no network I/O.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Protocol, runtime_checkable

from .packet import (
    OBS_DOM_TEXT,
    OBS_REGISTRATION_METADATA,
    OBS_RENDERED_TEXT,
    OBS_RESPONSE_HEADERS,
    Observation,
)

# The provenance method label for the only port shipped in this release.
METHOD_STATIC_DOCUMENT_FIXTURE = "static-document-fixture"

_DEFAULT_FIXTURE = "capture_target_benign.json"


@runtime_checkable
class CapturePort(Protocol):
    """A source of inert observations for a single capture target.

    Implementations turn a target into STATIC observations. ``target_ref`` is an
    opaque label (NOT a dereferenceable live locator); ``method`` is a provenance
    label. ``capture()`` returns the frozen observations and performs no live
    re-fetch on the analysis side (capture happens once, here).
    """

    target_ref: str
    method: str

    def capture(self) -> tuple[Observation, ...]:
        """Return the inert observations for this target (no network)."""
        ...


class StaticDocumentCapturePort:
    """Deterministic, offline capture of a synthetic LOCAL document fixture.

    Reads a bundled JSON fixture describing a synthetic static document (rendered
    text, DOM text, synthetic response headers, synthetic registration metadata)
    and emits the corresponding inert ``Observation``s. No network, no browser; the
    same fixture always yields the same observations (deterministic).

    Mission-NEUTRAL: the fixture is a benign synthetic open-data catalogue entry.
    """

    def __init__(self, fixture_name: str = _DEFAULT_FIXTURE) -> None:
        text = (
            resources.files("cairn.fixtures")
            .joinpath(fixture_name)
            .read_text(encoding="utf-8")
        )
        self._doc = json.loads(text)
        # The OPAQUE target reference — a fixture-scoped id, NEVER a live URL.
        self.target_ref: str = self._doc["target_ref"]
        self.method: str = METHOD_STATIC_DOCUMENT_FIXTURE

    def capture(self) -> tuple[Observation, ...]:
        """Emit the inert observations recorded for the synthetic document."""
        observations: list[Observation] = [
            Observation.create(
                OBS_RENDERED_TEXT, {"text": self._doc["rendered_text"]}
            ),
            Observation.create(OBS_DOM_TEXT, {"text": self._doc["dom_text"]}),
            Observation.create(
                OBS_RESPONSE_HEADERS, dict(self._doc["response_headers"])
            ),
            Observation.create(
                OBS_REGISTRATION_METADATA,
                dict(self._doc["registration_metadata"]),
            ),
        ]
        return tuple(observations)
