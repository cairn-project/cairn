"""Cause-layer tests: the five-frame gate-check STRUCTURE enforcer (PLAN §3.9 + §6)."""

from __future__ import annotations

from cairn.cause.gate import five_frame_gate_check
from cairn.cause.model import FRAME_KEYS


def test_all_five_frames_addressed_is_complete():
    result = five_frame_gate_check({k: True for k in FRAME_KEYS})
    assert result.complete is True
    assert result.all_frames_present is True
    assert result.all_passed is True
    assert set(result.frames_passed) == set(FRAME_KEYS)
    assert result.frames_failed == []
    assert result.missing_frames == []


def test_omitting_a_frame_is_incomplete():
    # Skip one frame → structure NOT satisfied (the decider can't silently skip).
    verdicts = {k: True for k in list(FRAME_KEYS)[:-1]}
    result = five_frame_gate_check(verdicts)
    assert result.complete is False
    assert result.all_frames_present is False
    assert FRAME_KEYS[-1] in result.missing_frames


def test_passed_failed_partition():
    verdicts = {k: (i % 2 == 0) for i, k in enumerate(FRAME_KEYS)}
    result = five_frame_gate_check(verdicts)
    assert result.complete is True  # all five addressed
    assert result.all_passed is False  # but not all passed
    assert set(result.frames_passed) | set(result.frames_failed) == set(FRAME_KEYS)
    assert set(result.frames_passed) & set(result.frames_failed) == set()


def test_unknown_frame_keys_are_ignored_for_completeness():
    # An extra non-frame key cannot substitute for a missing real frame.
    verdicts = {k: True for k in list(FRAME_KEYS)[:-1]}
    verdicts["not_a_frame"] = True
    result = five_frame_gate_check(verdicts)
    assert result.complete is False
    assert FRAME_KEYS[-1] in result.missing_frames
