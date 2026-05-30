"""Reputation accumulator tests (BUILD-PLAN §18.5, PLAN §3.5 L3).

Earned, never self-asserted: rises on AGREE + HONEYPOT_PASS, falls on DISAGREE,
falls hardest on HONEYPOT_FAIL. Per-node and per-family tracked independently;
bounded to [0, 1]; unknown subject ⇒ neutral prior.
"""

from __future__ import annotations

from cairn.verify import (
    EVENT_AGREE,
    EVENT_DISAGREE,
    EVENT_HONEYPOT_FAIL,
    EVENT_HONEYPOT_PASS,
    NEUTRAL_PRIOR,
    InMemoryReputation,
    ReputationDelta,
    family_subject,
)


def test_unknown_subject_is_neutral_prior():
    rep = InMemoryReputation()
    assert rep.score("never-seen") == NEUTRAL_PRIOR


def test_agree_raises_disagree_lowers():
    rep = InMemoryReputation()
    rep.apply(ReputationDelta("n", EVENT_AGREE))
    assert rep.score("n") > NEUTRAL_PRIOR
    rep2 = InMemoryReputation()
    rep2.apply(ReputationDelta("n", EVENT_DISAGREE))
    assert rep2.score("n") < NEUTRAL_PRIOR


def test_honeypot_pass_raises_fail_lowers_hardest():
    rep = InMemoryReputation()
    rep.apply(ReputationDelta("n", EVENT_HONEYPOT_PASS))
    assert rep.score("n") > NEUTRAL_PRIOR

    # Honeypot-fail must be a harsher penalty than a single disagree (L4 > L1).
    fail_rep = InMemoryReputation()
    fail_rep.apply(ReputationDelta("n", EVENT_HONEYPOT_FAIL))
    disagree_rep = InMemoryReputation()
    disagree_rep.apply(ReputationDelta("n", EVENT_DISAGREE))
    assert fail_rep.score("n") < disagree_rep.score("n")


def test_per_node_and_per_family_independent():
    rep = InMemoryReputation()
    rep.apply(ReputationDelta("node-a", EVENT_AGREE))
    rep.apply(ReputationDelta(family_subject("anthropic"), EVENT_HONEYPOT_FAIL))
    assert rep.score("node-a") > NEUTRAL_PRIOR
    assert rep.score(family_subject("anthropic")) < NEUTRAL_PRIOR
    # Independent keys.
    assert rep.score("node-a") != rep.score(family_subject("anthropic"))


def test_bounded_to_unit_interval():
    rep = InMemoryReputation()
    for _ in range(100):
        rep.apply(ReputationDelta("up", EVENT_HONEYPOT_PASS))
        rep.apply(ReputationDelta("down", EVENT_HONEYPOT_FAIL))
    assert rep.score("up") == 1.0
    assert rep.score("down") == 0.0
