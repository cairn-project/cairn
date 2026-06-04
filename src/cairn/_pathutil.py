"""Shared dotted-path resolution over nested dict/list structures.

Both the acceptance layer (``acceptance.py``) and the verify agreement layer
(``verify/agreement.py``) resolve dotted field paths into a result/output dict
(e.g. ``citations.0.url``). This is the single implementation they share; each
caller supplies the sentinel it wants returned on a miss so the function stays
free of any caller-specific "absent" convention.
"""

from __future__ import annotations

from typing import Any


def resolve_dotted(data: Any, dotted: str, *, missing: Any) -> Any:
    """Resolve a dotted path into a nested dict/list; return ``missing`` if absent.

    Dict keys resolve by name; a numeric segment (optionally negative) indexes
    into a list (e.g. ``items.0`` -> first item, ``items.-1`` -> last). Any miss
    — an unknown key, a non-indexable node, or an out-of-range index — returns
    the caller-supplied ``missing`` sentinel.
    """
    cur = data
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.lstrip("-").isdigit():
            idx = int(part)
            if -len(cur) <= idx < len(cur):
                cur = cur[idx]
            else:
                return missing
        else:
            return missing
    return cur
