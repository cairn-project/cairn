"""ClaudeCliAdapter — the first live-model adapter.

The ``Adapter`` seam's first LIVE implementation: instead of the deterministic
offline ``MockAdapter`` / ``PilotNodeAdapter`` stand-ins, this adapter runs a real
Cairn work unit by calling a Claude model through the ``claude -p`` CLI. It
renders the portable payload, builds a JSON-only prompt, spawns an ISOLATED
``claude -p``, parses the JSON out of the response (tolerating code fences /
surrounding prose), and returns a ``CandidateResult`` stamped
``model_family="claude"`` with real provenance.

SPAWN ISOLATION: the spawn MUST NOT inherit the caller environment's MCP servers
or plugins — an un-isolated CLI spawn can load and interfere with whatever the
caller has configured. The argv this adapter builds always carries
``--strict-mcp-config`` together with an EMPTY ``--mcp-config`` (an empty-servers
object) so NO MCP servers / plugins load. This is a self-contained minimal
wrapper with no external dependency.

FAIL-CLOSED: a nonzero exit, a timeout, an empty response, or unparseable output
yields a ``CandidateResult`` with an empty ``{}`` output that the unit's
acceptance contract REJECTS — never a crash, never a wave-through.

TESTABILITY: the real spawn is reached only through the default ``transcript_fn``.
Inject a fake ``transcript_fn`` (``prompt -> str``) to keep the offline suite
deterministic without ever calling real claude.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from collections.abc import Callable
from datetime import UTC
from pathlib import Path
from typing import Any

from ..types import WorkUnit
from .adapter import Adapter
from .capability import Capabilities
from .render import RenderedPayload, render_payload
from .result import CandidateResult

#: adapter implementation version (provenance).
_ADAPTER_VERSION = "claude-cli-0.1.0"

#: default model tier for the live call (a cheap default).
_DEFAULT_MODEL = "sonnet"

#: default subprocess timeout for one model call (seconds).
_DEFAULT_TIMEOUT = 120.0

#: the empty MCP-servers config written next to every spawn — strict + empty
#: means NO MCP servers / plugins load (the spawn-isolation guarantee).
_EMPTY_MCP_CONFIG: dict[str, Any] = {"mcpServers": {}}

#: the strict isolation flag the regression test asserts is always present.
_STRICT_MCP_FLAG = "--strict-mcp-config"


class ClaudeCliError(RuntimeError):
    """Raised by ``_claude_print`` on a nonzero exit / timeout / empty response.

    The adapter CATCHES this and fails closed (empty output) — callers of
    ``produce`` never see it.
    """


# A transcript function maps a prompt to the model's raw text response.
TranscriptFn = Callable[[str], str]

# A clock returns the current ISO-8601 timestamp (injected for determinism).
ClockFn = Callable[[], str]


def _default_clock() -> str:
    """Wall-clock ISO-8601 UTC timestamp (the real-provenance default)."""
    from datetime import datetime

    return datetime.now(UTC).isoformat()


def _build_claude_argv(
    mcp_config_path: str,
    *,
    model: str = _DEFAULT_MODEL,
    claude_bin: str = "claude",
) -> list[str]:
    """Build the ISOLATED ``claude -p`` argv (pure — the regression-test unit).

    The argv ALWAYS carries ``--strict-mcp-config`` plus ``--mcp-config
    <empty-servers config>`` so no MCP servers / plugins load.
    ``--output-format json`` lets the wrapper read the real model id for
    provenance. This function does no I/O — the caller writes the empty config to
    ``mcp_config_path`` first.
    """
    return [
        claude_bin,
        "-p",
        _STRICT_MCP_FLAG,
        "--mcp-config",
        mcp_config_path,
        "--model",
        model,
        "--output-format",
        "json",
    ]


def _extract_result_text(stdout: str) -> tuple[str, str | None]:
    """Pull (result_text, model_id) from a ``--output-format json`` envelope.

    Best-effort: the ``claude -p --output-format json`` envelope is a JSON object
    carrying the assistant's final text under ``result`` and a model id under
    ``model`` (or ``modelUsage``). If the envelope does not parse, fall back to
    treating the whole stdout as the result text and an unknown model id.
    """
    try:
        env = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return stdout, None
    if not isinstance(env, dict):
        return stdout, None
    result_text = env.get("result")
    if not isinstance(result_text, str):
        result_text = stdout
    model_id = env.get("model")
    if not isinstance(model_id, str):
        model_id = None
    return result_text, model_id


def _real_claude_print(
    prompt: str,
    *,
    model: str = _DEFAULT_MODEL,
    timeout: float = _DEFAULT_TIMEOUT,
) -> str:
    """The REAL isolated ``claude -p`` spawn (default ``transcript_fn``).

    Writes the empty MCP config, builds the isolated argv, runs the
    subprocess feeding ``prompt`` on stdin, and returns the model's result text.
    Raises ``ClaudeCliError`` on nonzero exit / timeout / empty output so the
    adapter can fail closed.
    """
    with tempfile.TemporaryDirectory(prefix="cairn-claude-") as tmp:
        mcp_path = str(Path(tmp) / "empty-mcp.json")
        Path(mcp_path).write_text(json.dumps(_EMPTY_MCP_CONFIG), encoding="utf-8")
        argv = _build_claude_argv(mcp_path, model=model)
        try:
            proc = subprocess.run(
                argv,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise ClaudeCliError(f"claude -p timed out after {timeout}s") from exc
        except OSError as exc:  # binary missing / not executable
            raise ClaudeCliError(f"could not spawn claude: {exc}") from exc

        if proc.returncode != 0:
            raise ClaudeCliError(f"claude -p exited {proc.returncode}: {proc.stderr.strip()[:400]}")
        result_text, _model_id = _extract_result_text(proc.stdout)
        if not result_text or not result_text.strip():
            raise ClaudeCliError("claude -p returned empty output")
        return result_text


def _extract_json(text: str) -> dict[str, Any] | None:
    """Tolerantly extract a single JSON object from a model response.

    Strategies, in order: (1) parse the whole string; (2) strip a ```json ... ```
    or ``` ... ``` fence and parse; (3) parse the first ``{`` .. matching last
    ``}`` slice. Returns the parsed dict, or ``None`` if nothing parses (the
    adapter then fails closed). Never raises.
    """
    candidates: list[str] = [text.strip()]

    # (2) fenced block — grab the content between the first pair of triple-fences.
    if "```" in text:
        body = text.split("```", 2)
        if len(body) >= 3:
            fenced = body[1]
            # drop a leading language tag line (e.g. "json")
            if "\n" in fenced:
                first_line, rest = fenced.split("\n", 1)
                if first_line.strip().lower() in ("json", "") or not first_line.strip().startswith(
                    "{"
                ):
                    fenced = rest
            candidates.append(fenced.strip())

    # (3) first '{' .. last '}' slice.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(text[start : end + 1])

    for cand in candidates:
        try:
            parsed = json.loads(cand)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _build_prompt(payload: RenderedPayload) -> str:
    """Build the JSON-only prompt from the neutral rendered payload.

    Reuses the vendor-neutral ``payload.prompt`` (objective + inputs + schema) and
    appends a strict JSON-only instruction. We still parse tolerantly downstream.
    """
    return (
        payload.prompt + "\n" + "Return ONLY a single JSON object conforming to the schema above. "
        "Do not include any prose, explanation, or markdown code fences — "
        "output the raw JSON object and nothing else.\n"
    )


class ClaudeCliAdapter(Adapter):
    """A live adapter that runs a work unit through a real Claude via ``claude -p``.

    Pass ``transcript_fn`` to inject a fake transcript producer (offline tests);
    when ``None`` the adapter performs the REAL isolated spawn. ``clock_fn``
    supplies ``produced_at`` (injectable for deterministic tests). ``capabilities``
    defaults to a generously-capable tier so it qualifies for the benign pilot's
    floor.
    """

    name = "claude-cli"
    model_family = "claude"
    version = _ADAPTER_VERSION

    def __init__(
        self,
        *,
        transcript_fn: TranscriptFn | None = None,
        clock_fn: ClockFn | None = None,
        model: str = _DEFAULT_MODEL,
        timeout: float = _DEFAULT_TIMEOUT,
        capabilities: Capabilities | None = None,
    ) -> None:
        self._model = model
        self._timeout = timeout
        self._clock_fn = clock_fn or _default_clock
        if transcript_fn is not None:
            self._transcript_fn: TranscriptFn = transcript_fn
        else:
            self._transcript_fn = lambda prompt: _real_claude_print(
                prompt, model=self._model, timeout=self._timeout
            )
        self._capabilities = capabilities or Capabilities(
            context_window=200_000,
            tools=[],
            modalities=["text"],
            model_family_tier=3,
        )

    @property
    def capabilities(self) -> Capabilities:
        return self._capabilities

    def produce(self, unit: WorkUnit) -> CandidateResult:
        """Render -> prompt -> isolated claude -p -> parse JSON -> CandidateResult.

        Fails closed: on a nonzero exit / timeout / empty / unparseable response,
        the output is an empty ``{}`` object that the acceptance contract rejects.
        Never raises.
        """
        payload = render_payload(unit)
        prompt = _build_prompt(payload)

        output: dict[str, Any]
        try:
            raw = self._transcript_fn(prompt)
        except ClaudeCliError:
            output = {}  # fail-closed: nonzero exit / timeout / spawn failure
        except Exception:  # any unexpected transcript-fn failure also fails closed
            output = {}
        else:
            parsed = _extract_json(raw)
            output = parsed if parsed is not None else {}

        return CandidateResult(
            task_id=unit.task_id,
            output=output,
            adapter_name=self.name,
            model_family=self.model_family,
            adapter_version=self.version,
            produced_at=self._clock_fn(),
        )
