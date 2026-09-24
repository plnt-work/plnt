"""FAQ lookup over the tenant's own config — no network, no shared state."""

import re

from plnt import ToolContext, tool

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "do",
    "you",
    "your",
    "what",
    "when",
    "how",
    "i",
    "can",
    "to",
    "of",
    "for",
    "on",
    "in",
    "and",
    "or",
    "my",
    "we",
    "it",
    "does",
}


def _terms(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


@tool
def lookup_faq(question: str, ctx: ToolContext, limit: int = 3) -> dict:
    """Find the business's FAQ entries most relevant to a customer question."""
    want = _terms(question)
    scored = []
    for item in ctx.config.get("faq", []):
        overlap = len(want & _terms(item["q"] + " " + item["a"]))
        if overlap:
            scored.append((overlap, item))
    scored.sort(key=lambda s: -s[0])
    return {"matches": [item for _, item in scored[:limit]]}
