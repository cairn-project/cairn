"""Tests: the code examples shipped in the docs actually run.

OUTCOME-ALTITUDE: extracts every fenced ```python block from README.md and
docs/QUICKSTART.md and executes it verbatim — exactly what a reader who
copy-pastes the project's first code sample does. A doc example that raises
(including a failing ``assert``) fails this suite, so the examples cannot
silently rot away from the code again (the README "Public API" snippet
shipped broken once: it fed ``{"answer", "citations"}`` to a contract that
requires ``{"is_open_license", "license_id"}``).

Offline: the documented examples use only the public library API on shipped
fixtures (no network, no model, no subprocess).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_DOCS_WITH_PYTHON_EXAMPLES = ("README.md", "docs/QUICKSTART.md")

_PYTHON_FENCE = re.compile(r"```python\n(.*?)```", re.DOTALL)


def _python_blocks(relpath: str) -> list[str]:
    text = (_ROOT / relpath).read_text(encoding="utf-8")
    return _PYTHON_FENCE.findall(text)


def _cases() -> list[pytest.param]:
    cases = []
    for relpath in _DOCS_WITH_PYTHON_EXAMPLES:
        for i, block in enumerate(_python_blocks(relpath)):
            cases.append(pytest.param(block, id=f"{relpath}#{i}"))
    return cases


def test_docs_contain_python_examples():
    """Guard the guard: if the fences are renamed/moved, this suite must not
    silently become vacuous."""
    for relpath in _DOCS_WITH_PYTHON_EXAMPLES:
        assert _python_blocks(relpath), f"no ```python blocks found in {relpath}"


@pytest.mark.parametrize("block", _cases())
def test_doc_python_example_executes(block: str) -> None:
    # Execute verbatim, as a copy-pasting reader would. Any exception —
    # including an AssertionError from the example's own asserts — fails.
    exec(compile(block, "<doc-example>", "exec"), {"__name__": "__doc_example__"})
