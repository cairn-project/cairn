"""Wave-5 tests: the benign pilot cause is well-formed (BUILD-PLAN §35).

Every pilot unit validates against the wave-1 schema; each unit's gold answer
passes that unit's OWN acceptance contract; the honest adapter produces the gold
answer and the wrong adapter diverges (but stays schema-valid).
"""

from __future__ import annotations

from cairn import evaluate_acceptance, validate_work_unit
from cairn.pilot import (
    PILOT_CAUSE_ID,
    PilotNodeAdapter,
    build_pilot_units,
    gold_answer,
    load_snippets,
)
from cairn.types import WorkUnit


def test_pilot_units_validate_against_wave1_schema():
    units = build_pilot_units()
    assert len(units) >= 3
    for unit in units:
        result = validate_work_unit(unit)
        assert result.valid, (unit["task_id"], result)
        assert unit["cause_id"] == PILOT_CAUSE_ID
        # Diversity gate explicitly ON (>= 2) so the anti-collusion primitive runs.
        assert unit["redundancy_policy"]["model_diversity"] >= 2


def test_gold_answer_passes_unit_acceptance_contract():
    snippets = load_snippets()
    units = build_pilot_units(snippets)
    for unit, snippet in zip(units, snippets):
        gold = gold_answer(snippet)
        acc = evaluate_acceptance(gold, unit["acceptance_contract"])
        assert acc.passed, (unit["task_id"], gold, acc)


def test_honest_adapter_produces_gold_answer():
    snippets = load_snippets()
    units = build_pilot_units(snippets)
    adapter = PilotNodeAdapter(model_family="claude")
    for unit_dict, snippet in zip(units, snippets):
        unit = WorkUnit.from_dict(unit_dict)
        cand = adapter.produce(unit)
        assert cand.output == gold_answer(snippet)


def test_wrong_adapter_diverges_but_stays_schema_valid():
    snippets = load_snippets()
    units = build_pilot_units(snippets)
    bad = PilotNodeAdapter(model_family="gpt", wrong=True)
    for unit_dict, snippet in zip(units, snippets):
        unit = WorkUnit.from_dict(unit_dict)
        cand = bad.produce(unit)
        # diverges from the gold standard...
        assert cand.output != gold_answer(snippet)
        # ...but the output still satisfies the schema-shape acceptance contract
        # (a wrong answer is not a malformed one — that's the honeypot's job).
        acc = evaluate_acceptance(cand.output, unit_dict["acceptance_contract"])
        assert acc.passed
