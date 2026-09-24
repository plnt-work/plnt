"""review-responder — draft an on-brand reply to a Google Business review.

Runtimes (e.g. plnt) load this module as the workflow entrypoint. Each step
declared in workflow.yaml maps to an @step-decorated function.
"""

from __future__ import annotations

from typing import Any, Optional

from microagents.sdk import step, workflow, tools


@workflow(name="review-responder", version="1.2.0")
class ReviewResponder:
    """Four-step DAG: classify -> retrieve brand voice -> draft -> moderate."""

    @step(id="classify_intent")
    async def classify(self, review: dict) -> dict:
        result = await tools.llm.classify(
            text=review["text"],
            labels={"sentiment": ["positive", "neutral", "negative"]},
        )
        return {"sentiment": result["sentiment"], "topics": result.get("topics", [])}

    @step(id="retrieve_brand_voice", deps=["classify_intent"])
    async def retrieve_voice(self, tenant_id: str, sentiment: str) -> dict:
        docs = await tools.rag.query(
            index=f"brand-voice/{tenant_id}",
            query=f"tone for {sentiment} feedback",
            k=3,
        )
        return {"voice_examples": docs}

    @step(id="draft_reply", deps=["retrieve_brand_voice"])
    async def draft(self, review: dict, sentiment: str, voice_examples: list[dict]) -> str:
        prompt = _build_draft_prompt(review, sentiment, voice_examples)
        return await tools.llm.generate(prompt=prompt, max_tokens=280)

    @step(id="safety_check", deps=["draft_reply"])
    async def moderate(self, draft: str) -> dict:
        verdict = await tools.policy.moderate(text=draft)
        return {"safe": verdict["safe"], "reasons": verdict.get("reasons", [])}


def _build_draft_prompt(review: dict, sentiment: str, voice_examples: list[dict]) -> str:
    examples = "\n\n".join(f"- {d['text']}" for d in voice_examples[:3])
    return (
        "Draft a short, on-brand reply to this Google Business review.\n\n"
        f"Review (sentiment: {sentiment}):\n{review['text']}\n\n"
        f"Brand voice examples:\n{examples}\n\n"
        "Reply (max 3 sentences):"
    )
