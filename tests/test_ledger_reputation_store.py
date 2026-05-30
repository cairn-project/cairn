"""Ledger-backed reputation persistence tests (BUILD-PLAN §25.6, PLAN §3.5 L3).

LedgerReputation persists wave-3 deltas and replays them to identical scores;
its math matches the wave-3 in-memory store on the same delta sequence.
"""

from __future__ import annotations

from cairn.ledger import LedgerReputation
from cairn.verify import (
    EVENT_AGREE,
    EVENT_DISAGREE,
    EVENT_HONEYPOT_FAIL,
    EVENT_HONEYPOT_PASS,
    InMemoryReputation,
    ReputationDelta,
    family_subject,
)

_DELTAS = [
    ReputationDelta("node-A", EVENT_AGREE),
    ReputationDelta(family_subject("claude"), EVENT_AGREE),
    ReputationDelta("node-B", EVENT_DISAGREE),
    ReputationDelta("node-A", EVENT_HONEYPOT_PASS),
    ReputationDelta("node-B", EVENT_HONEYPOT_FAIL),
]


def test_persists_and_replays_to_same_scores(tmp_path):
    path = tmp_path / "reputation.jsonl"
    rep = LedgerReputation(path)
    rep.apply_all(_DELTAS)

    scores_before = {s: rep.score(s) for s in rep.known_subjects()}
    assert scores_before  # non-empty

    # A FRESH instance over the same file replays to identical scores.
    rep2 = LedgerReputation(path)
    scores_after = {s: rep2.score(s) for s in rep2.known_subjects()}
    assert scores_after == scores_before


def test_matches_in_memory_wave3_math(tmp_path):
    path = tmp_path / "reputation.jsonl"
    ledger_rep = LedgerReputation(path)
    mem_rep = InMemoryReputation()

    ledger_rep.apply_all(_DELTAS)
    mem_rep.apply_all(_DELTAS)

    subjects = set(ledger_rep.known_subjects()) | set(mem_rep.known_subjects())
    for s in subjects:
        assert ledger_rep.score(s) == mem_rep.score(s)


def test_unknown_subject_neutral_prior_persisted(tmp_path):
    path = tmp_path / "reputation.jsonl"
    rep = LedgerReputation(path)
    rep.apply(ReputationDelta("node-A", EVENT_AGREE))
    # Never-seen subject still reports the neutral prior after persistence.
    rep2 = LedgerReputation(path)
    from cairn.verify import NEUTRAL_PRIOR

    assert rep2.score("never-seen") == NEUTRAL_PRIOR
