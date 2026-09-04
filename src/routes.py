"""
FastAPI route definitions.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from src.customer_service import get_customer, list_customers, customer_exists
from src.rag import retrieve, get_all_articles
from src.prompt_builder import build_prompt
from src.llm_service import generate_response
from src.escalation import check_escalation

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Pydantic models ───────────────────────────────────────────────────────────

class Message(BaseModel):
    role: str    # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    customer_id: str
    message: str
    conversation_history: list[Message] = []

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be empty.")
        return v.strip()

    @field_validator("customer_id")
    @classmethod
    def customer_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("customer_id cannot be empty.")
        return v.strip().upper()


class SearchRequest(BaseModel):
    query: str
    top_k: int = 3

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Search query cannot be empty.")
        return v.strip()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health_check() -> dict[str, str]:
    """Basic liveness probe."""
    return {"status": "ok", "service": "Customer Support Resolution Assistant"}


@router.get("/customer/{customer_id}")
async def get_customer_profile(customer_id: str) -> dict[str, Any]:
    """Fetch a single customer profile by ID."""
    profile = get_customer(customer_id.upper())
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=f"Customer '{customer_id}' not found.",
        )
    return profile


@router.get("/customers")
async def get_all_customers() -> list[dict[str, Any]]:
    """Return all customer profiles (for the demo dropdown)."""
    return list_customers()


@router.get("/articles")
async def get_articles() -> list[dict[str, Any]]:
    """Return all support knowledge-base articles."""
    return get_all_articles()


@router.post("/search")
async def search_articles(req: SearchRequest) -> dict[str, Any]:
    """
    Semantic search over the knowledge base.
    Returns top-k articles with similarity scores.
    """
    try:
        results = retrieve(req.query, top_k=req.top_k)
        return {
            "query": req.query,
            "results": results,
            "count": len(results),
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("Search error: %s", exc)
        raise HTTPException(status_code=500, detail="Search failed – please try again.")


@router.post("/chat")
async def chat(req: ChatRequest) -> dict[str, Any]:
    """
    Main chat endpoint.
    1. Validate customer.
    2. Retrieve relevant articles via RAG.
    3. Build prompt and call Gemini.
    4. Apply deterministic escalation rules.
    5. Return structured JSON response.
    """
    # ── Validate customer ─────────────────────────────────────────────────────
    if not customer_exists(req.customer_id):
        raise HTTPException(
            status_code=404,
            detail=f"Customer '{req.customer_id}' not found.",
        )
    customer = get_customer(req.customer_id)

    # ── RAG retrieval ─────────────────────────────────────────────────────────
    try:
        articles = retrieve(req.message)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("RAG retrieval error: %s", exc)
        articles = []

    # ── Build prompt ──────────────────────────────────────────────────────────
    history = [{"role": m.role, "content": m.content} for m in req.conversation_history]
    prompt = build_prompt(
        customer=customer,
        conversation_history=history,
        retrieved_articles=articles,
        user_message=req.message,
    )

    # ── Generate response ─────────────────────────────────────────────────────
    llm_result = generate_response(prompt)

    # ── Apply escalation rules ────────────────────────────────────────────────
    final_result = check_escalation(
        llm_response=llm_result,
        retrieved_articles=articles,
        customer=customer,
        user_message=req.message,
    )

    # Attach retrieved articles metadata for the frontend panels
    final_result["retrieved_articles"] = [
        {
            "article_id": a.get("article_id"),
            "title": a.get("title"),
            "category": a.get("category"),
            "similarity_score": a.get("similarity_score"),
        }
        for a in articles
    ]

    return final_result
