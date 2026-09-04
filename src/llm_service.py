"""
llm_service.py – local rule-based response generator (no API key required).

Parses the structured prompt produced by prompt_builder.py and generates a
JSON response matching the same schema the rest of the app expects:

  {
    "status": "resolved | followup_needed | escalated",
    "response": "...",
    "confidence": 0-100,
    "evidence": ["ART001", ...],
    "followup_questions": [],
    "summary_for_agent": "..."
  }

The logic:
  1. Extract retrieved articles + customer info from the prompt text.
  2. Pick the highest-similarity article(s).
  3. Build a grounded, empathetic reply from the article's resolution text.
  4. Set confidence based on how many articles were found and their similarity.
  5. Flag escalation / follow-up the same way the original Gemini prompt instructed.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _parse_prompt(prompt: str) -> dict[str, Any]:
    """
    Extract structured data from the prompt string built by prompt_builder.py.
    Returns a dict with keys: articles, customer_id, customer_name, billing_status,
    user_message.
    """
    result: dict[str, Any] = {
        "articles": [],
        "customer_id": "",
        "customer_name": "",
        "billing_status": "active",
        "user_message": "",
    }

    # ── Customer profile fields ────────────────────────────────────────────────
    m = re.search(r"Customer ID\s*:\s*(.+)", prompt)
    if m:
        result["customer_id"] = m.group(1).strip()

    m = re.search(r"Name\s*:\s*(.+)", prompt)
    if m:
        result["customer_name"] = m.group(1).strip()

    m = re.search(r"Billing Status\s*:\s*(.+)", prompt)
    if m:
        result["billing_status"] = m.group(1).strip().lower()

    # ── User message ───────────────────────────────────────────────────────────
    m = re.search(
        r"=== CURRENT CUSTOMER MESSAGE ===\n(.+?)\n===",
        prompt, re.DOTALL
    )
    if m:
        result["user_message"] = m.group(1).strip()

    # ── Retrieved articles ─────────────────────────────────────────────────────
    # Each article block looks like:
    # [ART001] Title (Category: X)
    #   Issue      : ...
    #   Resolution : ...
    #   Escalate if: ...
    #   Similarity : 87.23%
    art_pattern = re.compile(
        r"\[(?P<id>ART\d+)\]\s*(?P<title>[^\n]+)\(Category:\s*(?P<category>[^)]+)\)\n"
        r"\s*Issue\s*:\s*(?P<issue>[^\n]+)\n"
        r"\s*Resolution\s*:\s*(?P<resolution>[^\n]+)\n"
        r"\s*Escalate if\s*:\s*(?P<escalate_if>[^\n]+)\n"
        r"\s*Similarity\s*:\s*(?P<sim>[0-9.]+)%",
        re.MULTILINE,
    )
    for m in art_pattern.finditer(prompt):
        result["articles"].append({
            "article_id": m.group("id"),
            "title": m.group("title").strip(),
            "category": m.group("category").strip(),
            "issue": m.group("issue").strip(),
            "resolution": m.group("resolution").strip(),
            "escalate_if": m.group("escalate_if").strip(),
            "similarity": float(m.group("sim")) / 100.0,
        })

    return result


def _build_reply(parsed: dict[str, Any]) -> dict[str, Any]:
    """Core rule-based decision engine."""
    articles = parsed["articles"]
    user_msg = parsed["user_message"].lower()
    billing_status = parsed["billing_status"]

    # ── No articles found → escalate ──────────────────────────────────────────
    if not articles:
        return _escalated(
            response=(
                "I'm sorry, I wasn't able to find a relevant solution in our "
                "knowledge base for your query. Let me connect you with a specialist "
                "who can assist you directly."
            ),
            confidence=0,
            evidence=[],
            summary=f"No matching articles for: {parsed['user_message'][:200]}",
        )

    # Sort by similarity desc
    articles = sorted(articles, key=lambda a: a["similarity"], reverse=True)
    best = articles[0]
    evidence_ids = [a["article_id"] for a in articles]

    # ── Confidence based on best similarity ───────────────────────────────────
    sim = best["similarity"]
    if sim >= 0.75:
        confidence = 88
    elif sim >= 0.55:
        confidence = 74
    elif sim >= 0.40:
        confidence = 62
    else:
        confidence = 45

    # ── Check escalation conditions ───────────────────────────────────────────
    escalate_keywords = best["escalate_if"].lower()
    escalation_triggers = [
        "multiple", "repeated", "persistent", "hardware", "replacement",
        "port", "fraud", "legal", "suspend", "overdue", "disputed",
        "cannot resolve", "specialist",
    ]
    needs_escalation = (
        confidence < 70
        or billing_status in ("suspended", "overdue")
        or any(kw in escalate_keywords for kw in escalation_triggers
               if kw in user_msg)
    )

    # ── Follow-up: check if user message is vague ─────────────────────────────
    vague_indicators = [
        "not working", "issue", "problem", "help", "broken",
        "slow", "bad", "error",
    ]
    is_vague = (
        len(parsed["user_message"].split()) < 8
        and any(v in user_msg for v in vague_indicators)
        and not needs_escalation
        and confidence >= 70
    )

    # ── Build the user-facing response text ───────────────────────────────────
    customer_name = parsed["customer_name"].split()[0] if parsed["customer_name"] else "there"

    response_text = (
        f"Hi {customer_name}, thank you for reaching out.\n\n"
        f"Based on your message, I believe this relates to: **{best['title']}**.\n\n"
        f"{best['resolution']}\n\n"
    )

    if len(articles) > 1:
        additional = ", ".join(
            f"{a['article_id']} ({a['title']})" for a in articles[1:]
        )
        response_text += (
            f"I also found related information in our knowledge base "
            f"({additional}) which may be helpful.\n\n"
        )

    response_text += (
        "If this doesn't fully resolve your issue, please let me know and I'll "
        "arrange further assistance."
    )

    # ── Assemble output ───────────────────────────────────────────────────────
    if needs_escalation:
        return _escalated(
            response=response_text,
            confidence=confidence,
            evidence=evidence_ids,
            summary=(
                f"Customer {parsed['customer_id']} ({parsed['customer_name']}) "
                f"queried: \"{parsed['user_message'][:200]}\". "
                f"Best match: {best['article_id']} ({best['title']}, sim={sim:.0%}). "
                f"Escalation triggered: billing_status={billing_status}."
            ),
        )

    if is_vague:
        return {
            "status": "followup_needed",
            "response": (
                f"Hi {customer_name}, I'd be happy to help! "
                "Could you give me a bit more detail? For example:\n"
                "• When did the issue start?\n"
                "• Have you tried restarting your device?\n"
                "• Is the issue affecting all services or just one?\n\n"
                f"In the meantime, here's something that might help: {best['resolution']}"
            ),
            "confidence": confidence,
            "evidence": evidence_ids,
            "followup_questions": [
                "When did this issue start?",
                "Have you restarted your device or router?",
                "Is this affecting all services or a specific one?",
            ],
            "summary_for_agent": (
                f"Customer sent a vague message: \"{parsed['user_message']}\". "
                f"Follow-up questions asked. Best article: {best['article_id']}."
            ),
        }

    return {
        "status": "resolved",
        "response": response_text,
        "confidence": confidence,
        "evidence": evidence_ids,
        "followup_questions": [],
        "summary_for_agent": (
            f"Customer {parsed['customer_id']} query resolved using "
            f"{best['article_id']} (sim={sim:.0%}): {best['title']}."
        ),
    }


def _escalated(
    response: str,
    confidence: int,
    evidence: list[str],
    summary: str,
) -> dict[str, Any]:
    return {
        "status": "escalated",
        "response": response,
        "confidence": confidence,
        "evidence": evidence,
        "followup_questions": [],
        "summary_for_agent": summary,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Public API (same signature as the original)
# ──────────────────────────────────────────────────────────────────────────────

def generate_response(prompt: str) -> dict[str, Any]:
    """
    Parse *prompt* and return a rule-based JSON response dict.
    This is a drop-in replacement for the Gemini-based generate_response().
    """
    try:
        parsed = _parse_prompt(prompt)
        result = _build_reply(parsed)
        return _validate_response(result)
    except Exception as exc:
        logger.error("Local LLM error: %s", exc)
        return _fallback_response(str(exc))


def _validate_response(data: dict[str, Any]) -> dict[str, Any]:
    """Ensure all required fields are present with correct types."""
    defaults: dict[str, Any] = {
        "status": "escalated",
        "response": "",
        "confidence": 0,
        "evidence": [],
        "followup_questions": [],
        "summary_for_agent": "",
    }
    for key, default in defaults.items():
        if key not in data:
            data[key] = default

    data["confidence"] = max(0, min(100, int(data.get("confidence", 0))))
    return data


def _fallback_response(reason: str) -> dict[str, Any]:
    return {
        "status": "escalated",
        "response": (
            "I'm sorry, I encountered a technical issue while processing "
            "your request. Please hold while I connect you to a human agent."
        ),
        "confidence": 0,
        "evidence": [],
        "followup_questions": [],
        "summary_for_agent": f"Automatic escalation due to: {reason}",
    }
