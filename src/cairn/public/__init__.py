"""cairn.public — the public transparency READ-surfaces (READ-ONLY projection).

The "court-grade / auditable / maximally transparent" frame (REQUIREMENTS Frame 4)
made concrete: anyone can see what Cairn is doing and independently verify its
integrity WITHOUT privileged access. A pure projection over already-public state —
NO write path, NO mutation, NO new trust surface. Composes on the existing listing
gate (``CauseRegistry.list_causes``), the finding-vetting verdict state
(``FindingVetQueue``), and the independent ``verify_log``; reimplements nothing.

  read.py  the projection views (redaction by construction) + ``PublicTransparency``
           read facade + the module-level read entry points.

REDACTION BY CONSTRUCTION: the public view dataclasses have NO FIELD that can carry
raw captured content / observation bytes / analysis text / PII — the safety is the
projection's SHAPE, not a filtering step.

DEFERRED: a served web/HTTP read API + HTML rendering of these surfaces, pagination
for very large logs, and (unchanged upstream) onward routing of routable findings.
"""

from __future__ import annotations

from .read import (
    FORBIDDEN_PUBLIC_FIELDS,
    PublicCauseView,
    PublicLogEntryView,
    PublicTransparency,
    PublicVettedOutcomeView,
    list_published_causes,
    list_public_log,
    list_vetted_outcomes,
    public_verify_log,
)

__all__ = [
    "PublicTransparency",
    "PublicCauseView",
    "PublicVettedOutcomeView",
    "PublicLogEntryView",
    "FORBIDDEN_PUBLIC_FIELDS",
    "list_published_causes",
    "list_vetted_outcomes",
    "public_verify_log",
    "list_public_log",
]
