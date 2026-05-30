"""Acceptance-contract evaluation — the machine-checkable predicate layer.

``evaluate_acceptance(result, acceptance_contract)`` runs every predicate in a
contract against a result dict and returns a conjunctive verdict. Each predicate
is a pure function over the result — no LLM, no network (research 02 A.1 step 4,
the cheap client-side filter). The semantic / quorum verify layer (PLAN §3.5)
sits ABOVE this and is a later wave.

Predicate kinds (SPEC.md): required_fields, field_type, value_range, enum,
non_empty, min_items, regex_match. An unknown kind fails closed (raises).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

_MISSING = object()


class UnknownPredicateError(ValueError):
    """Raised when a predicate names a kind with no registered checker.

    Fail-closed: an unrecognized predicate must never be silently treated as a
    pass (a malformed/hostile contract could otherwise wave bad results through).
    """


@dataclass(frozen=True)
class PredicateResult:
    kind: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class AcceptanceResult:
    """Conjunctive verdict over a contract's predicates."""

    passed: bool
    results: list[PredicateResult] = field(default_factory=list)


def _resolve(result: Any, dotted: str) -> Any:
    """Resolve a dotted field path into a nested structure; _MISSING if absent.

    Dict keys resolve by name; a numeric path segment indexes into a list
    (e.g. ``citations.0`` -> first citation). Any miss returns _MISSING.
    """
    cur = result
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.lstrip("-").isdigit():
            idx = int(part)
            if -len(cur) <= idx < len(cur):
                cur = cur[idx]
            else:
                return _MISSING
        else:
            return _MISSING
    return cur


# --- predicate checkers: (result, params) -> (passed, detail) ---------------

_JSON_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


def _check_required_fields(result, params):
    fields = params.get("fields", [])
    missing = [f for f in fields if _resolve(result, f) is _MISSING]
    if missing:
        return False, f"missing fields: {missing}"
    return True, ""


def _check_field_type(result, params):
    fpath, json_type = params["field"], params["json_type"]
    val = _resolve(result, fpath)
    if val is _MISSING:
        return False, f"{fpath} absent"
    expected = _JSON_TYPES.get(json_type)
    if expected is None:
        return False, f"unknown json_type {json_type!r}"
    # bool is a subclass of int — guard so a boolean is not accepted as integer/number
    if json_type in ("integer", "number") and isinstance(val, bool):
        return False, f"{fpath} is boolean, not {json_type}"
    if not isinstance(val, expected):
        return False, f"{fpath} is {type(val).__name__}, expected {json_type}"
    return True, ""


def _check_value_range(result, params):
    fpath = params["field"]
    val = _resolve(result, fpath)
    if val is _MISSING:
        return False, f"{fpath} absent"
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return False, f"{fpath} is not numeric"
    lo, hi = params.get("min"), params.get("max")
    if lo is not None and val < lo:
        return False, f"{fpath}={val} < min {lo}"
    if hi is not None and val > hi:
        return False, f"{fpath}={val} > max {hi}"
    return True, ""


def _check_enum(result, params):
    fpath = params["field"]
    val = _resolve(result, fpath)
    if val is _MISSING:
        return False, f"{fpath} absent"
    allowed = params.get("allowed", [])
    if val not in allowed:
        return False, f"{fpath}={val!r} not in {allowed}"
    return True, ""


def _check_non_empty(result, params):
    fpath = params["field"]
    val = _resolve(result, fpath)
    if val is _MISSING:
        return False, f"{fpath} absent"
    # Refusal-handling: a refusal yields an empty/absent answer field -> fail.
    if val is None:
        return False, f"{fpath} is null"
    if isinstance(val, (str, list, dict)) and len(val) == 0:
        return False, f"{fpath} is empty"
    return True, ""


def _check_min_items(result, params):
    fpath, count = params["field"], params["count"]
    val = _resolve(result, fpath)
    if val is _MISSING:
        return False, f"{fpath} absent"
    if not isinstance(val, list):
        return False, f"{fpath} is not an array"
    if len(val) < count:
        return False, f"{fpath} has {len(val)} items, need >= {count}"
    return True, ""


def _check_regex_match(result, params):
    fpath, pattern = params["field"], params["pattern"]
    val = _resolve(result, fpath)
    if val is _MISSING:
        return False, f"{fpath} absent"
    if not isinstance(val, str):
        return False, f"{fpath} is not a string"
    if re.search(pattern, val) is None:
        return False, f"{fpath} does not match /{pattern}/"
    return True, ""


_CHECKERS: dict[str, Callable[[Any, dict], tuple[bool, str]]] = {
    "required_fields": _check_required_fields,
    "field_type": _check_field_type,
    "value_range": _check_value_range,
    "enum": _check_enum,
    "non_empty": _check_non_empty,
    "min_items": _check_min_items,
    "regex_match": _check_regex_match,
}


def evaluate_acceptance(result: Any, acceptance_contract: Any) -> AcceptanceResult:
    """Run all predicates in a contract against a result (conjunctive).

    ``acceptance_contract`` is the dict form (``{"predicates": [...]}``) or an
    ``AcceptanceContract`` dataclass. Returns an AcceptanceResult; ``passed`` is
    True only if every predicate passes. Raises ``UnknownPredicateError`` on an
    unrecognized predicate kind (fail-closed).
    """
    predicates = _normalize_predicates(acceptance_contract)

    per: list[PredicateResult] = []
    all_passed = True
    for pred in predicates:
        kind = pred.get("kind")
        checker = _CHECKERS.get(kind)
        if checker is None:
            raise UnknownPredicateError(f"unknown acceptance predicate kind: {kind!r}")
        params = {k: v for k, v in pred.items() if k != "kind"}
        passed, detail = checker(result, params)
        per.append(PredicateResult(kind=kind, passed=passed, detail=detail))
        all_passed = all_passed and passed

    return AcceptanceResult(passed=all_passed, results=per)


def _normalize_predicates(acceptance_contract: Any) -> list[dict[str, Any]]:
    """Accept either a dict contract or an AcceptanceContract dataclass."""
    # dataclass form
    preds = getattr(acceptance_contract, "predicates", None)
    if preds is not None and not isinstance(acceptance_contract, dict):
        out: list[dict[str, Any]] = []
        for p in preds:
            if hasattr(p, "kind"):
                d = {"kind": p.kind}
                d.update(getattr(p, "params", {}))
                out.append(d)
            else:
                out.append(p)
        return out
    # dict form
    if isinstance(acceptance_contract, dict):
        return list(acceptance_contract.get("predicates", []))
    raise TypeError(
        "acceptance_contract must be a dict or AcceptanceContract, got "
        f"{type(acceptance_contract).__name__}"
    )
