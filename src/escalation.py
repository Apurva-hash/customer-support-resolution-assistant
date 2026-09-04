"""
Escalation engine – deterministic rules applied on top of Gemini's output.

Escalation is triggered when ANY of the following conditions are true:
  1. LLM confidence < CONFIDENCE_THRESHOLD (70)
  2. No relevant articles found (empty evidence)
  3. Multiple unrelated issues detected (>2 distinct top-level categories)
  4. Billing dispute not resolved by retrieved articles
  5. Account suspension / complex account state
"""
from __future__ import annotations

import logging
from typing import Any

from src.config import CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)

# Keywords that flag billing disputes
_BILLING_DISPUTE_KEYWORDS = {
    "dispute", "overcharged", "wrong charge", "incorrect bill",
    "unauthorized", "fraud", "fraudulent", "double charged",
    "extra charge", "unexpected charge",
}

# Keywords that flag complex account issues
_COMPLEX_ACCOUNT_KEYWORDS = {
    "suspended", "terminated", "blocked", "legal", "contract",
    "ported", "porting", "identity", "kyc", "fraud",
}


def check_escalation(
    llm_response: dict[str, Any],
    retrieved_articles: list[dict[str, Any]],
    customer: dict[str, Any],
    user_message: str,
) -> dict[str, Any]:
    """
    Apply deterministic escalation rules and return either the original
    response (possibly updated) or an escalation response.

    Returns the (possibly modified) llm_response dict.
    """
    reasons: list[str] = []

    # ── Rule 1: Low confidence ────────────────────────────────────────────────
    confidence = llm_response.get("confidence", 0)
    if confidence < CONFIDENCE_THRESHOLD:
        reasons.append(
            f"Low LLM confidence ({confidence}%) – below threshold of {CONFIDENCE_THRESHOLD}%."
        )

    # ── Rule 2: No articles found ─────────────────────────────────────────────
    evidence = llm_response.get("evidence", [])
    if not retrieved_articles or not evidence:
        reasons.append("No relevant knowledge-base articles found for this query.")

    # ── Rule 3: Multiple unrelated issues ─────────────────────────────────────
    categories = {a.get("category", "") for a in retrieved_articles}
    if len(categories) >= 3:
        reasons.append(
            f"Multiple unrelated issue categories detected: {', '.join(categories)}."
        )

    # ── Rule 4: Billing dispute not covered ───────────────────────────────────
    lower_msg = user_message.lower()
    if any(kw in lower_msg for kw in _BILLING_DISPUTE_KEYWORDS):
        # Check if any retrieved article is a billing/dispute article
        billing_covered = any(
            "billing" in a.get("category", "").lower()
            or "refund" in a.get("category", "").lower()
            for a in retrieved_articles
        )
        if not billing_covered:
            reasons.append(
                "Billing dispute raised but no billing/refund article retrieved."
            )

    # ── Rule 5: Complex account issue ─────────────────────────────────────────
    if any(kw in lower_msg for kw in _COMPLEX_ACCOUNT_KEYWORDS):
        reasons.append("Complex account issue detected (suspension/legal/KYC/porting).")

    # ── Account suspension flag ───────────────────────────────────────────────
    if customer.get("billing_status") in ("suspended", "overdue"):
        if "billing" not in (llm_response.get("status", "")):
            reasons.append(
                f"Customer account status is '{customer['billing_status']}', "
                "requiring specialist review."
            )

    # ── Decision ──────────────────────────────────────────────────────────────
    if not reasons:
        return llm_response          # No escalation needed

    logger.info("Escalating conversation for customer %s. Reasons: %s",
                customer.get("customer_id"), reasons)

    summary = _build_escalation_summary(customer, user_message, reasons, retrieved_articles)

    llm_response["status"] = "escalated"
    llm_response["summary_for_agent"] = summary
    llm_response["escalation_reasons"] = reasons

    # Craft a user-facing escalation message
    llm_response["response"] = (
        "I understand your concern and want to make sure you receive the best possible help. "
        "Based on the details of your issue, I'm escalating this to one of our specialist "
        "agents who will be better equipped to assist you. "
        "Please hold — an agent will be with you shortly. "
        "A summary of your issue has been prepared for the agent."
    )

    return llm_response


def _build_escalation_summary(
    customer: dict[str, Any],
    user_message: str,
    reasons: list[str],
    articles: list[dict[str, Any]],
) -> str:
    name = customer.get("name", "Unknown")
    cid = customer.get("customer_id", "Unknown")
    plan = customer.get("plan", "Unknown")
    billing = customer.get("billing_status", "Unknown")
    tickets = customer.get("recent_tickets", [])

    open_tickets = [t for t in tickets if t.get("status") in ("open", "escalated")]
    ticket_summary = (
        ", ".join(f"{t['ticket_id']} ({t['issue']})" for t in open_tickets)
        if open_tickets else "None"
    )

    article_refs = (
        ", ".join(f"{a['article_id']} – {a['title']}" for a in articles)
        if articles else "None retrieved"
    )

    reason_bullets = "\n  - ".join(reasons)

    return (
        f"=== AGENT HANDOVER SUMMARY ===\n"
        f"Customer: {name} (ID: {cid})\n"
        f"Plan: {plan}\n"
        f"Billing Status: {billing}\n"
        f"Open Tickets: {ticket_summary}\n\n"
        f"Customer Message:\n  \"{user_message}\"\n\n"
        f"Escalation Reasons:\n  - {reason_bullets}\n\n"
        f"Knowledge Base Articles Consulted:\n  {article_refs}\n"
        f"=== END OF SUMMARY ==="
    )
