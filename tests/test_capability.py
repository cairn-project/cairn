"""Capability self-selection floor tests (BUILD-PLAN §12.2).

PLAN §3.3 F2 — a node runs a unit only if it meets every floor dimension.
"""

from __future__ import annotations

from cairn.execute import Capabilities, meets_floor
from cairn.types import CapabilityFloor

_FLOOR = CapabilityFloor(
    context_window=8192,
    tools=["web_fetch"],
    modalities=["text"],
)


def test_node_meeting_all_dimensions_qualifies():
    caps = Capabilities(
        context_window=32768,
        tools=["web_fetch", "document_read"],
        modalities=["text", "image"],
        model_family_tier=2,
    )
    check = meets_floor(caps, _FLOOR)
    assert check.qualifies
    assert check.reasons == []


def test_short_context_window_rejected():
    caps = Capabilities(
        context_window=4096, tools=["web_fetch"], modalities=["text"]
    )
    check = meets_floor(caps, _FLOOR)
    assert not check.qualifies
    assert any("context_window" in r for r in check.reasons)


def test_missing_tool_rejected():
    caps = Capabilities(
        context_window=32768, tools=[], modalities=["text"]
    )
    check = meets_floor(caps, _FLOOR)
    assert not check.qualifies
    assert any("web_fetch" in r for r in check.reasons)


def test_missing_modality_rejected():
    caps = Capabilities(
        context_window=32768, tools=["web_fetch"], modalities=["image"]
    )
    check = meets_floor(caps, _FLOOR)
    assert not check.qualifies
    assert any("text" in r for r in check.reasons)


def test_floor_with_no_context_window_does_not_gate_on_it():
    floor = CapabilityFloor(tools=[], modalities=[])
    caps = Capabilities(context_window=0, tools=[], modalities=[])
    assert meets_floor(caps, floor).qualifies


def test_multiple_failures_each_named():
    caps = Capabilities(context_window=10, tools=[], modalities=[])
    check = meets_floor(caps, _FLOOR)
    assert not check.qualifies
    assert len(check.reasons) == 3
