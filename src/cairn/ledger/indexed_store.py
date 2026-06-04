"""Shared index-over-blobstore persistence base for the small registries.

Several registries (cause, capture-grants, consents, and the two human-vetting
queues) follow the same storage shape: a per-item index file under
``ledger.root/<subdir>/<key>`` whose contents are a content-addressed blob key,
with the blob itself living in ``ledger.blobs``. Each had its own near-identical
``_persist`` / ``_load`` / ``_read`` / ``_all`` trio.

``IndexedBlobStore`` factors that shape into one place. A registry composes it
(``self._store = IndexedBlobStore(ledger, "causes", Cause.from_dict)``) and keeps
its own domain methods; only the storage mechanics are shared. The item KEY is
supplied by the caller per write (registries derive it from their own id
field(s)), so composite keys (e.g. ``node_id|cause_id``) need no special base
support.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Generic, TypeVar

from .ledger import Ledger

T = TypeVar("T")


class IndexedBlobStore(Generic[T]):
    """A per-item index dir over ``ledger.blobs``: key -> blob-key -> object."""

    def __init__(
        self,
        ledger: Ledger,
        subdir: str,
        from_dict: Callable[[dict[str, Any]], T],
    ) -> None:
        self._ledger = ledger
        self._from_dict = from_dict
        self._index_dir = ledger.root / subdir
        self._index_dir.mkdir(parents=True, exist_ok=True)

    @property
    def index_dir(self) -> Path:
        """The directory holding the per-item index refs (read-only)."""
        return self._index_dir

    def persist(self, key: str, payload: dict[str, Any]) -> str:
        """Content-address ``payload`` and index it under ``key``; return the blob key."""
        blob_key = self._ledger.blobs.put_json(payload)
        (self._index_dir / key).write_text(blob_key)
        return blob_key

    def read(self, ref: Path) -> T:
        """Materialise the object an index ref points at."""
        blob_key = ref.read_text().strip()
        return self._from_dict(self._ledger.blobs.get_json(blob_key))

    def load(self, key: str) -> T | None:
        """Load the object indexed under ``key``, or ``None`` if absent."""
        ref = self._index_dir / key
        if not ref.exists():
            return None
        return self.read(ref)

    def all(self) -> list[T]:
        """All stored objects, ordered by index-ref filename."""
        return [self.read(p) for p in sorted(self._index_dir.iterdir()) if p.is_file()]
