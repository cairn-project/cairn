"""ThresholdFlagPolicy — the generic mission-neutral flag bar (BUILD-PLAN §6).

The policy maps a verify ``VerifyVerdict`` to a ``FlagDecision`` using only a
generic confidence threshold over an ACCEPTED verdict's output. It hard-codes no
domain vocabulary — ``flag_label`` is opaque, ``score_field`` is configurable.
"""

from __future__ import annotations

import pytest

from cairn.analysis import FlagDecision, FlagPolicy, ThresholdFlagPolicy
from cairn.verify import verify_unit

from ._verify_helpers import make_result, policy


def _accepted_verdict(output):
    cands = [
        make_result(output, node="n1", family="claude"),
        make_result(output, node="n2", family="gpt"),
    ]
    return verify_unit(cands, policy(target_nresults=2, min_quorum=2, model_diversity=1))


def _not_accepted_verdict():
    # Two disagreeing single-family results → no quorum → not accepted.
    cands = [
        make_result({"label": "a", "confidence": 0.9}, node="n1", family="claude"),
        make_result({"label": "b", "confidence": 0.9}, node="n2", family="gpt"),
    ]
    return verify_unit(cands, policy(target_nresults=2, min_quorum=2, model_diversity=1))


def test_is_a_flagpolicy():
    assert isinstance(ThresholdFlagPolicy("flagged", 0.5), FlagPolicy)


def test_flags_accepted_above_threshold_with_opaque_label():
    v = _accepted_verdict({"label": "cc-by", "confidence": 0.9})
    decision = ThresholdFlagPolicy("flagged", 0.7).decide(v)
    assert decision.flagged
    assert decision.automated_verdict is not None
    assert decision.automated_verdict.flag_label == "flagged"
    assert decision.automated_verdict.confidence == pytest.approx(0.9)


def test_does_not_flag_when_not_accepted():
    v = _not_accepted_verdict()
    assert not v.accepted
    decision = ThresholdFlagPolicy("flagged", 0.1).decide(v)
    assert not decision.flagged
    assert decision.automated_verdict is None
    assert "not accepted" in decision.reason


def test_does_not_flag_when_score_field_absent():
    v = _accepted_verdict({"label": "cc-by"})  # no confidence field
    decision = ThresholdFlagPolicy("flagged", 0.1).decide(v)
    assert not decision.flagged
    assert "confidence" in decision.reason


def test_does_not_flag_when_score_non_numeric():
    v = _accepted_verdict({"label": "cc-by", "confidence": "high"})
    decision = ThresholdFlagPolicy("flagged", 0.1).decide(v)
    assert not decision.flagged
    assert "not numeric" in decision.reason


def test_bool_is_not_treated_as_numeric_score():
    # A bool is an int subtype in Python; the policy must NOT treat it as a score.
    v = _accepted_verdict({"label": "cc-by", "confidence": True})
    decision = ThresholdFlagPolicy("flagged", 0.1).decide(v)
    assert not decision.flagged
    assert "not numeric" in decision.reason


def test_does_not_flag_below_threshold():
    v = _accepted_verdict({"label": "cc-by", "confidence": 0.4})
    decision = ThresholdFlagPolicy("flagged", 0.7).decide(v)
    assert not decision.flagged
    assert "below threshold" in decision.reason


def test_configurable_score_field_is_honoured():
    v = _accepted_verdict({"label": "cc-by", "match_score": 0.8})
    decision = ThresholdFlagPolicy(
        "flagged", 0.5, score_field="match_score"
    ).decide(v)
    assert decision.flagged
    assert decision.automated_verdict.confidence == pytest.approx(0.8)


def test_score_is_clamped_to_unit_interval():
    v = _accepted_verdict({"label": "cc-by", "confidence": 1.7})
    decision = ThresholdFlagPolicy("flagged", 0.5).decide(v)
    assert decision.flagged
    assert decision.automated_verdict.confidence == pytest.approx(1.0)


def test_empty_flag_label_is_rejected():
    with pytest.raises(ValueError):
        ThresholdFlagPolicy("", 0.5)


def test_flagdecision_constructors():
    from cairn.vetting import AutomatedVerdict

    av = AutomatedVerdict(flag_label="x", confidence=0.5)
    yes = FlagDecision.flag(av, "because")
    no = FlagDecision.no_flag("nope")
    assert yes.flagged and yes.automated_verdict is av and yes.reason == "because"
    assert (not no.flagged) and no.automated_verdict is None and no.reason == "nope"
