"""Content-addressed blob store tests (BUILD-PLAN §25.1, PLAN §3.6).

Round-trip + content-addressing (same content => same key, dedup).
"""

from __future__ import annotations

from cairn.ledger import BlobStore, content_key


def test_put_get_round_trip(tmp_path):
    store = BlobStore(tmp_path)
    data = b"some result bytes \x00\x01\x02"
    key = store.put(data)
    assert store.get(key) == data
    assert store.has(key)


def test_key_is_content_address_and_dedups(tmp_path):
    store = BlobStore(tmp_path)
    data = b"identical content"
    k1 = store.put(data)
    k2 = store.put(data)  # same content
    assert k1 == k2 == content_key(data)
    # Different content => different key.
    k3 = store.put(b"different content")
    assert k3 != k1


def test_missing_key_raises(tmp_path):
    store = BlobStore(tmp_path)
    import pytest

    with pytest.raises(KeyError):
        store.get("0" * 64)


def test_json_round_trip_and_canonical(tmp_path):
    store = BlobStore(tmp_path)
    obj = {"b": 2, "a": 1, "nested": {"y": [3, 2, 1], "x": True}}
    key = store.put_json(obj)
    assert store.get_json(key) == obj
    # Canonical: key-order-independent dicts content-address identically.
    other = {"nested": {"x": True, "y": [3, 2, 1]}, "a": 1, "b": 2}
    assert store.put_json(other) == key
