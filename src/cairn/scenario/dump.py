"""Review-dump writer — pure file I/O, no network, no egress.

Writes the banner-labeled review-dump directory for one finding:
``<review_dir>/<finding-short-hash>/{packet.md, packet.json, provenance.txt}``.
This is the scenario's terminal artefact — a human opens it with ``open`` / ``bat``
/ ``less``. There is NO send: writing local files is the only output.
"""

from __future__ import annotations

import json
from pathlib import Path

from .packet_builder import ReviewArtefacts

#: how many chars of the finding hash name the per-finding subdir.
_SHORT_HASH = 12


def finding_dir(review_dir: Path, finding_hash: str) -> Path:
    """The per-finding subdir path (short-hash named) under ``review_dir``."""
    return review_dir / finding_hash[:_SHORT_HASH]


def write_review_dump(review_dir: Path, artefacts: ReviewArtefacts) -> Path:
    """Write the three artefacts into ``<review_dir>/<short-hash>/`` and return it.

    Pure local file I/O. The dir is created if missing. Returns the per-finding
    subdir path so the caller can report it.
    """
    out = finding_dir(review_dir, artefacts.finding_hash)
    out.mkdir(parents=True, exist_ok=True)
    (out / "packet.md").write_text(artefacts.packet_md, encoding="utf-8")
    (out / "packet.json").write_text(
        json.dumps(artefacts.packet_json, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "provenance.txt").write_text(artefacts.provenance_txt, encoding="utf-8")
    return out
