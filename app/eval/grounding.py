"""Number-grounding check — the load-bearing trust eval.

Premise: the LLM never computes or invents numbers in this project. Every numeric
token that lands in the memo must trace to a value present in `review_facts.json`
(which itself was produced by the deterministic core).

`check_grounding(memo, facts)` returns the list of ungrounded numeric tokens. An
empty list means "every memo number is sourced from facts." Tests use this to
catch hallucinations injected into the prose path.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable


# Match a signed number (with optional decimal and optional trailing %) only when it is
# *not* embedded in a word like "D01_B03". The word-boundary lookarounds keep school IDs,
# action IDs, and ISO week labels from being mis-tokenised as bare numbers.
_NUMBER_RE = re.compile(r"(?<![\w-])-?\d+(?:\.\d+)?(?:%)?(?!\w)")

# Numbers that can show up in the memo without appearing in facts (axis labels,
# implicit scale references). Keep this list small and explicit — every entry is a
# pre-justified, documented constant.
_ALLOWLIST: frozenset[str] = frozenset(
    {
        "0",     # baseline / zero count
        "1",     # rank / counter
        "2",     # rank / counter
        "100",   # explicit risk-scale max (also stored in facts.risk_score_scale_max)
    }
)


def _normalise(token: str) -> str:
    """Canonical form for a numeric token.

    Strip a trailing '%' and the sign so '12%', '12.0%', '12', '+12' all collapse to
    the same key. Integers and floats with the same magnitude collapse too.
    """
    raw = token.rstrip("%").lstrip("+")
    if raw == "" or raw == "-":
        return token
    try:
        f = float(raw)
    except ValueError:
        return token
    # Equal-but-formatted-differently floats collapse to one key.
    if f == int(f):
        return str(int(f))
    return f"{f:.6f}".rstrip("0").rstrip(".")


def _collect_from_json(payload: Any, sink: set[str]) -> None:
    """Recursively walk a JSON-ish payload, collecting every numeric token."""
    if payload is None:
        return
    if isinstance(payload, bool):
        return
    if isinstance(payload, (int, float)):
        sink.add(_normalise(str(payload)))
        return
    if isinstance(payload, str):
        for tok in _NUMBER_RE.findall(payload):
            sink.add(_normalise(tok))
        return
    if isinstance(payload, dict):
        for k, v in payload.items():
            _collect_from_json(k, sink)
            _collect_from_json(v, sink)
        return
    if isinstance(payload, (list, tuple, set)):
        for item in payload:
            _collect_from_json(item, sink)
        return
    # Fall-through: stringify and re-scan.
    for tok in _NUMBER_RE.findall(str(payload)):
        sink.add(_normalise(tok))


def grounded_numbers(facts: Any) -> set[str]:
    """All numeric tokens that appear anywhere in `facts` (recursively)."""
    sink: set[str] = set()
    _collect_from_json(facts, sink)
    sink.update(_ALLOWLIST)
    return sink


def memo_numbers(memo: str) -> list[str]:
    """All numeric tokens that appear in the rendered memo, in document order."""
    return [_normalise(t) for t in _NUMBER_RE.findall(memo)]


def check_grounding(memo: str, facts: Any) -> list[str]:
    """Return numeric tokens from `memo` that do NOT appear in `facts` (or the allowlist).

    Empty list => the memo is fully grounded in the deterministic facts.
    """
    allowed = grounded_numbers(facts)
    return [tok for tok in memo_numbers(memo) if tok not in allowed]


def check_grounding_from_paths(memo_path: str, facts_path: str) -> list[str]:
    with open(memo_path, "r", encoding="utf-8") as fh:
        memo = fh.read()
    with open(facts_path, "r", encoding="utf-8") as fh:
        facts = json.load(fh)
    return check_grounding(memo, facts)
