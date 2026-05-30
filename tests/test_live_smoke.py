"""Wave-6 tests: live_smoke over the REAL backbone with a mocked live node (§43).

OUTCOME-ALTITUDE: invokes the real ``live_smoke`` on a FRESH ledger with no
pre-arranged state. The live ``ClaudeCliAdapter`` node's subprocess is mocked via
an injected ``transcript_fn`` returning the correct license JSON, so the suite is
deterministic and NEVER spawns a real model. Asserts the run flows through the
real verify / ledger / transparency-log and reaches ACCEPTED, with the live
``claude`` family in the quorum.
"""

from __future__ import annotations

import json

from cairn.ledger import FixedClock, Ledger, verify_log
from cairn.pilot import LIVE_FAMILY, live_smoke
from cairn.pilot.cause import classify_license

_KEY = b"live-smoke-test-key"
_FIXED_TS = "2026-01-01T00:00:00+00:00"


def _fresh_ledger(tmp_path):
    return Ledger(tmp_path, FixedClock(start=0.0), signing_key=_KEY)


def _fake_claude(prompt: str) -> str:
    """An honest fake Claude: reads the license_text out of the prompt and returns
    the correct classification as bare JSON (the model stand-in for the offline
    live-smoke test). The prompt embeds the inputs JSON, so the license text is
    recoverable here.
    """
    # The neutral prompt embeds inputs as a JSON blob under "INPUTS:".
    obj_start = prompt.find("{", prompt.find("INPUTS:"))
    # Find the inline.license_text deterministically by parsing the inputs blob.
    # The inputs blob is the INPUTS section up to the next double newline.
    inputs_section = prompt.split("INPUTS:", 1)[1]
    blob = inputs_section.split("\n\n", 1)[0].strip()
    inputs = json.loads(blob)
    license_text = inputs.get("inline", {}).get("license_text", "")
    return json.dumps(classify_license(license_text))


def test_live_smoke_offline_reaches_accepted(tmp_path):
    # OUTCOME-ALTITUDE: fresh ledger, real backbone, live node mocked.
    ledger = _fresh_ledger(tmp_path)
    summary = live_smoke(
        ledger,
        transcript_fn=_fake_claude,
        clock_fn=lambda: _FIXED_TS,
    )

    assert summary.units, "live smoke produced no units"
    assert summary.all_accepted, [u.to_dict() for u in summary.units]

    # The live claude family participates in the accepted quorum on every unit.
    for u in summary.units:
        assert LIVE_FAMILY in u.model_families_in_quorum, u.to_dict()
        assert len(u.model_families_in_quorum) >= 2, u.to_dict()

    # Flowed through the REAL ledger / transparency-log; independently verifiable.
    assert summary.verdict_recorded == len(summary.units)
    assert summary.result_recorded == len(summary.units) * 2  # live + reference
    v = verify_log(tmp_path / "translog.jsonl")
    assert v.ok is True
    assert v.head_hash == summary.log_head


def test_live_smoke_bad_model_fails_closed(tmp_path):
    # A live node returning junk fails closed (empty output) — the unit must NOT
    # crash; it simply may not reach the 2-family diversity quorum on its own.
    ledger = _fresh_ledger(tmp_path)
    summary = live_smoke(
        ledger,
        transcript_fn=lambda prompt: "no idea, sorry",
        clock_fn=lambda: _FIXED_TS,
    )
    # No crash; the run completes and the log is still consistent.
    assert summary.units
    v = verify_log(tmp_path / "translog.jsonl")
    assert v.ok is True
