"""Work-unit validation against the canonical JSON Schema.

``validate_work_unit`` checks a raw unit dict against
``spec/work_unit.schema.json`` (Draft 2020-12) and enforces the MAJOR-version
compatibility rule from SPEC.md. Pure local work — no network, no secrets.
"""

from __future__ import annotations

import functools
import json
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator

# Spec MAJOR version this build understands. A unit whose schema_version MAJOR
# differs is rejected (SPEC.md versioning rule). Keep in sync with the schema $id
# and SPEC.md "current spec version".
SPEC_MAJOR = 1


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of validating a work unit.

    ``valid`` is True only when there are no errors. ``errors`` is a list of
    human-readable strings, each pointing at the offending location.
    """

    valid: bool
    errors: list[str] = field(default_factory=list)


@functools.lru_cache(maxsize=1)
def _schema() -> dict[str, Any]:
    """Load the canonical work-unit JSON Schema (cached)."""
    text = (
        resources.files("cairn.spec").joinpath("work_unit.schema.json").read_text(encoding="utf-8")
    )
    return json.loads(text)


@functools.lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    return Draft202012Validator(_schema())


def _major_of(version: str) -> int | None:
    try:
        return int(version.split(".", 1)[0])
    except (ValueError, AttributeError, IndexError):
        return None


def validate_work_unit(unit: Any) -> ValidationResult:
    """Validate a raw work-unit dict against the spec.

    Two checks:
      1. JSON Schema structural validation (all fields, types, oneOf on inputs).
      2. schema_version MAJOR must equal this build's SPEC_MAJOR.

    Returns a ValidationResult; never raises on invalid input (collects errors).
    """
    errors: list[str] = []

    if not isinstance(unit, dict):
        return ValidationResult(
            valid=False, errors=[f"work unit must be an object, got {type(unit).__name__}"]
        )

    # 1. structural schema validation
    for err in sorted(_validator().iter_errors(unit), key=lambda e: list(e.path)):
        location = "/".join(str(p) for p in err.path) or "(root)"
        errors.append(f"{location}: {err.message}")

    # 2. version-compatibility (only meaningful if schema_version is a sane string)
    version = unit.get("schema_version")
    major = _major_of(version) if isinstance(version, str) else None
    if major is not None and major != SPEC_MAJOR:
        errors.append(
            f"schema_version: MAJOR {major} is incompatible with this build's "
            f"spec MAJOR {SPEC_MAJOR}"
        )

    return ValidationResult(valid=not errors, errors=errors)
