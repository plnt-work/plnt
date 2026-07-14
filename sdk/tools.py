"""Tool proxies — the microagents-standard set of primitives every runtime
implements. Workflow code imports these and calls them; the runtime binds them
to actual providers at load time (llm.classify → some model, rag.query → some
vector store).

This module exposes the interface, not the implementation.
"""

from __future__ import annotations

from typing import Any


class _LLM:
    async def classify(self, *, text: str, labels: dict[str, list[str]]) -> dict:
        raise NotImplementedError

    async def generate(self, *, prompt: str, max_tokens: int = 512) -> str:
        raise NotImplementedError


class _RAG:
    async def query(self, *, index: str, query: str, k: int = 5) -> list[dict]:
        raise NotImplementedError


class _Policy:
    async def moderate(self, *, text: str) -> dict:
        raise NotImplementedError


class _GCal:
    async def freebusy(self, *, calendar_id: str, start: str, end: str) -> list[dict]:
        raise NotImplementedError


class _GBP:
    async def scrape(self, *, business_id: str) -> dict:
        raise NotImplementedError


class _DB:
    async def query(self, *, sql: str, params: dict[str, Any] | None = None) -> list[dict]:
        raise NotImplementedError


class _Notify:
    async def push(self, *, channel: str, message: str, urgency: str = "normal") -> None:
        raise NotImplementedError


llm = _LLM()
rag = _RAG()
policy = _Policy()
gcal = _GCal()
gbp = _GBP()
db = _DB()
notify = _Notify()
