"""Content-addressed blob store (content-addressed task+result blobs).

A commodity, write-once object store keyed by the sha256 of the content. Same
content always yields the same key (dedup for free), which is exactly the
git/IPFS content-addressing property leans on. Stored as plain
files under ``<root>/objects/<2-char-prefix>/<rest-of-hash>`` so the whole store
is a directory tree that is trivially mirrorable (copy = mirror).

No truth-deciding here — this only stores + addresses bytes.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def canonical_json(obj: Any) -> bytes:
    """Deterministic JSON bytes (sorted keys, no extra whitespace).

    Used everywhere a dict must hash stably (blobs, attestations, log payloads).
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def content_key(data: bytes) -> str:
    """The content address of ``data`` — its sha256 hex digest."""
    return hashlib.sha256(data).hexdigest()


class BlobStore:
    """Sha256-keyed, write-once content-addressed blob store."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self._objects = Path(root) / "objects"
        self._objects.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        return self._objects / key[:2] / key[2:]

    def put(self, data: bytes) -> str:
        """Store ``data``; return its content key. Idempotent (write-once).

        Same content ⇒ same key ⇒ no rewrite. The write is atomic via a temp
        file + ``os.replace`` so a concurrent reader never sees a partial blob.
        """
        key = content_key(data)
        dest = self._path_for(key)
        if dest.exists():
            return key  # already stored; content-addressing guarantees identity
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.parent / (dest.name + ".tmp")
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, dest)
        return key

    def get(self, key: str) -> bytes:
        """Read the blob at ``key``; raise ``KeyError`` if absent."""
        path = self._path_for(key)
        if not path.exists():
            raise KeyError(key)
        return path.read_bytes()

    def has(self, key: str) -> bool:
        return self._path_for(key).exists()

    def put_json(self, obj: Any) -> str:
        """Store a JSON-serializable object as a canonical-JSON blob."""
        return self.put(canonical_json(obj))

    def get_json(self, key: str) -> Any:
        return json.loads(self.get(key).decode("utf-8"))
