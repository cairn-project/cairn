"""Tests: ClaudeCliAdapter — the first live adapter.

OFFLINE + deterministic: the real ``claude -p`` subprocess is mocked by injecting
a fake ``transcript_fn``; NO test spawns a real model. Covers JSON parsing (bare /
fenced / prose-wrapped), fail-closed behavior (junk output, nonzero-exit/timeout
via a raising transcript_fn), the SPAWN-ISOLATION argv regression, and injected
provenance clock.
"""

from __future__ import annotations

import json

import pytest

from cairn.execute.claude_adapter import (
    _EMPTY_MCP_CONFIG,
    _STRICT_MCP_FLAG,
    ClaudeCliAdapter,
    ClaudeCliError,
    _build_claude_argv,
)
from cairn.pilot.cause import build_pilot_units, classify_license, load_snippets
from cairn.types import WorkUnit

_FIXED_TS = "2026-01-01T00:00:00+00:00"


def _fixed_clock() -> str:
    return _FIXED_TS


def _first_pilot_unit() -> WorkUnit:
    unit_dict = build_pilot_units(load_snippets())[0]
    return WorkUnit.from_dict(unit_dict)


def _correct_answer_for(unit: WorkUnit) -> dict:
    license_text = unit.inputs.get("inline", {}).get("license_text", "")
    return classify_license(license_text)


# --- JSON parsing: bare / fenced / prose-wrapped ----------------------------


def test_parses_bare_json_transcript():
    unit = _first_pilot_unit()
    answer = _correct_answer_for(unit)

    def fake(prompt: str) -> str:
        return json.dumps(answer)

    adapter = ClaudeCliAdapter(transcript_fn=fake, clock_fn=_fixed_clock)
    cand = adapter.produce(unit)

    assert cand.output == answer
    assert cand.model_family == "claude"
    assert cand.adapter_name == "claude-cli"
    assert cand.task_id == unit.task_id


def test_tolerates_fenced_json_transcript():
    unit = _first_pilot_unit()
    answer = _correct_answer_for(unit)

    def fake(prompt: str) -> str:
        return "```json\n" + json.dumps(answer) + "\n```"

    adapter = ClaudeCliAdapter(transcript_fn=fake, clock_fn=_fixed_clock)
    cand = adapter.produce(unit)
    assert cand.output == answer


def test_tolerates_prose_around_json():
    unit = _first_pilot_unit()
    answer = _correct_answer_for(unit)

    def fake(prompt: str) -> str:
        return (
            "Sure, here is the classification you asked for:\n"
            + json.dumps(answer)
            + "\nLet me know if you need anything else."
        )

    adapter = ClaudeCliAdapter(transcript_fn=fake, clock_fn=_fixed_clock)
    cand = adapter.produce(unit)
    assert cand.output == answer


# --- fail-closed -------------------------------------------------------------


def test_fails_closed_on_junk_output():
    unit = _first_pilot_unit()

    def fake(prompt: str) -> str:
        return "I'm not sure, that doesn't look like a license to me."

    adapter = ClaudeCliAdapter(transcript_fn=fake, clock_fn=_fixed_clock)
    cand = adapter.produce(unit)
    # Empty output (fail-closed) — NOT a crash.
    assert cand.output == {}

    # And that empty output FAILS the unit's acceptance contract.
    from cairn.acceptance import evaluate_acceptance

    acc = evaluate_acceptance(cand.output, unit.acceptance_contract)
    assert acc.passed is False


def test_fails_closed_on_subprocess_error():
    unit = _first_pilot_unit()

    def fake(prompt: str) -> str:
        raise ClaudeCliError("claude -p exited 1: boom")

    adapter = ClaudeCliAdapter(transcript_fn=fake, clock_fn=_fixed_clock)
    cand = adapter.produce(unit)  # must NOT raise
    assert cand.output == {}


def test_fails_closed_on_unexpected_transcript_exception():
    unit = _first_pilot_unit()

    def fake(prompt: str) -> str:
        raise ValueError("unexpected")

    adapter = ClaudeCliAdapter(transcript_fn=fake, clock_fn=_fixed_clock)
    cand = adapter.produce(unit)  # must NOT propagate
    assert cand.output == {}


# --- SPAWN-ISOLATION argv regression (the top safety guarantee) -------------


def test_build_argv_contains_isolation_flags(tmp_path):
    mcp_path = str(tmp_path / "empty-mcp.json")
    argv = _build_claude_argv(mcp_path, model="sonnet")

    # The non-negotiable isolation flags are present by construction.
    assert _STRICT_MCP_FLAG in argv
    assert "--mcp-config" in argv
    # --mcp-config is immediately followed by the empty-servers config path.
    idx = argv.index("--mcp-config")
    assert argv[idx + 1] == mcp_path
    # It is a one-shot print invocation.
    assert "-p" in argv
    assert argv[0] == "claude"


def test_empty_mcp_config_has_no_servers():
    # The config written next to every spawn declares NO MCP servers, so strict
    # mode loads nothing (no MCP servers or plugins from the caller's environment).
    assert _EMPTY_MCP_CONFIG == {"mcpServers": {}}
    assert _EMPTY_MCP_CONFIG["mcpServers"] == {}


def test_real_claude_print_writes_empty_servers_config(monkeypatch):
    # Drive the REAL _real_claude_print but intercept subprocess.run so NO real
    # claude spawns — and assert the argv it would run carries the isolation flags
    # AND points at a config file whose content is the empty-servers object.
    import cairn.execute.claude_adapter as mod

    captured = {}

    class _FakeProc:
        returncode = 0
        stdout = json.dumps({"result": "{}", "model": "claude-test"})
        stderr = ""

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        # the mcp-config file must exist + be empty-servers at spawn time
        idx = argv.index("--mcp-config")
        cfg_path = argv[idx + 1]
        with open(cfg_path, encoding="utf-8") as fh:
            captured["cfg"] = json.load(fh)
        return _FakeProc()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    out = mod._real_claude_print("hello", model="sonnet", timeout=5.0)

    assert _STRICT_MCP_FLAG in captured["argv"]
    assert captured["cfg"] == {"mcpServers": {}}
    assert out == "{}"


def test_real_claude_print_raises_on_nonzero_exit(monkeypatch):
    import cairn.execute.claude_adapter as mod

    class _FakeProc:
        returncode = 1
        stdout = ""
        stderr = "kaboom"

    monkeypatch.setattr(mod.subprocess, "run", lambda argv, **kw: _FakeProc())
    with pytest.raises(ClaudeCliError):
        mod._real_claude_print("hello", timeout=5.0)


# --- provenance: injected clock ---------------------------------------------


def test_produced_at_uses_injected_clock():
    unit = _first_pilot_unit()
    answer = _correct_answer_for(unit)
    adapter = ClaudeCliAdapter(transcript_fn=lambda p: json.dumps(answer), clock_fn=_fixed_clock)
    cand = adapter.produce(unit)
    assert cand.produced_at == _FIXED_TS  # NOT the wall clock
