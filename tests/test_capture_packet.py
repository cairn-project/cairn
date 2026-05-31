"""Inert-by-construction + content-address properties (AC.CAP.1, AC.CAP.2).

The packet/observation/view types are the load-bearing safety abstraction: they
must hold ONLY static JSON data and must expose NO live-fetch surface, so an
analyst can never re-visit the live target.
"""

from __future__ import annotations

import inspect

import pytest

from cairn.capture import (
    OBS_RENDERED_TEXT,
    OBS_RESPONSE_HEADERS,
    AnalysisView,
    ExaminationPacket,
    Observation,
    StaticDocumentCapturePort,
)
from cairn.ledger.blobstore import canonical_json, content_key

# Tokens that would betray a dereferenceable live locator on the analysis path.
_LOCATOR_TOKENS = ("url", "uri", "locator", "endpoint", "href", "address", "host")
# Method-name tokens that would betray a live re-fetch operation.
_FETCH_TOKENS = ("fetch", "refetch", "visit", "open", "download", "request", "get_live")


def _make_packet() -> ExaminationPacket:
    port = StaticDocumentCapturePort()
    return ExaminationPacket.create(
        target_ref=port.target_ref,
        observations=port.capture(),
        captured_at=12.0,
        captured_by="op-1",
        capture_method=port.method,
        cause_id="cause-abc",
    )


def test_observation_create_hashes_and_round_trips():
    obs = Observation.create(OBS_RESPONSE_HEADERS, {"content-type": "text/html"})
    assert obs.content_hash == content_key(canonical_json(obs.content))
    again = Observation.from_dict(obs.to_dict())
    assert again == obs


def test_observation_rejects_unknown_kind_and_non_json():
    with pytest.raises(ValueError):
        Observation.create("EXECUTABLE_PAYLOAD", {"x": 1})  # unknown kind
    with pytest.raises(ValueError):
        # A callable is not plain JSON — the packet must never carry executable
        # content.
        Observation.create(OBS_RENDERED_TEXT, {"text": lambda: "x"})


def test_packet_hash_is_deterministic_content_address():
    p1 = _make_packet()
    p2 = _make_packet()
    # Identical capture input -> identical packet hash (dedup + tamper-evidence).
    assert p1.packet_hash == p2.packet_hash
    assert p1.packet_hash == content_key(
        canonical_json(
            {
                "target_ref": p1.target_ref,
                "cause_id": p1.cause_id,
                "observations": [o.to_dict() for o in p1.observations],
                "captured_at": p1.captured_at,
                "captured_by": p1.captured_by,
                "capture_method": p1.capture_method,
            }
        )
    )


def test_packet_round_trip_detects_tamper():
    p = _make_packet()
    again = ExaminationPacket.from_dict(p.to_dict())
    assert again == p
    tampered = p.to_dict()
    tampered["observations"][0]["content"] = {"text": "SWAPPED"}
    with pytest.raises(ValueError):
        ExaminationPacket.from_dict(tampered)  # content_hash mismatch caught


def test_packet_and_view_expose_no_live_locator_field():
    # AC.CAP.2: no public attribute of the packet OR the analyst view names a
    # dereferenceable live locator. target_ref is opaque (not a url/* field).
    p = _make_packet()
    view = AnalysisView.of(p)
    for obj in (p, view):
        for name in vars(obj):
            assert name == "target_ref" or not any(
                tok in name.lower() for tok in _LOCATOR_TOKENS
            ), f"{type(obj).__name__}.{name} looks like a live locator"


def test_view_exposes_no_fetch_method():
    # AC.CAP.2: no public method of the view (or packet) fetches/visits a live
    # target — "re-visit the live target" is not expressible.
    p = _make_packet()
    view = AnalysisView.of(p)
    for obj in (p, view):
        for name, member in inspect.getmembers(obj):
            if name.startswith("_"):
                continue
            if callable(member):
                assert not any(
                    tok in name.lower() for tok in _FETCH_TOKENS
                ), f"{type(obj).__name__}.{name} looks like a live-fetch method"


def test_target_ref_is_opaque_not_a_url():
    # The static-document port writes a fixture id into target_ref, never a URL.
    p = _make_packet()
    assert "://" not in p.target_ref  # no scheme -> not a dereferenceable URL
    assert not p.target_ref.lower().startswith(("http", "ftp", "file:"))


def test_view_rendered_text_reads_frozen_observation():
    p = _make_packet()
    view = AnalysisView.of(p)
    text = view.rendered_text()
    assert text is not None and "Catalogue" in text
    assert len(view.observations_of_kind(OBS_RENDERED_TEXT)) == 1
