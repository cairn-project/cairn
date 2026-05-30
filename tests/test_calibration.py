"""Calibration-probe stub tests (BUILD-PLAN §12.4).

research 01 §5.4 — self-declared capability is untrusted; the trivial probe
checks well-formedness only (necessary, not sufficient). Real adversarial
probing is deferred.
"""

from __future__ import annotations

from cairn.execute import Capabilities, TrivialCalibrationProbe


def test_well_formed_capabilities_pass():
    caps = Capabilities(
        context_window=8192,
        tools=["web_fetch"],
        modalities=["text", "image"],
        model_family_tier=2,
    )
    result = TrivialCalibrationProbe().verify(caps)
    assert result.passed
    assert result.reasons == []


def test_negative_context_window_fails():
    caps = Capabilities(context_window=-1)
    result = TrivialCalibrationProbe().verify(caps)
    assert not result.passed
    assert any("context_window" in r for r in result.reasons)


def test_unknown_modality_fails():
    caps = Capabilities(context_window=1024, modalities=["telepathy"])
    result = TrivialCalibrationProbe().verify(caps)
    assert not result.passed
    assert any("telepathy" in r for r in result.reasons)


def test_negative_tier_fails():
    caps = Capabilities(context_window=1024, model_family_tier=-3)
    result = TrivialCalibrationProbe().verify(caps)
    assert not result.passed
    assert any("model_family_tier" in r for r in result.reasons)
