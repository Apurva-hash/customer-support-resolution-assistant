"""
Prompt builder – constructs the full prompt for Gemini given customer
context, conversation history, and retrieved support articles.
"""
from __future__ import annotations

from typing import Any

# ── Output schema (injected into every prompt) ────────────────────────────────
_OUTPUT_SCHEMA = """\
{
  "status": "resolved | followup_needed | escalated",
  "response": "<your response to the customer>",
  "confidence": <integer 0-100>,
  "evidence": ["<article_id_1>", "<article_id_2>"],
  "followup_questions": ["<question if info missing>"],
  "summary_for_agent": "<one-paragraph summary for human agent>"
}"""

# ── System instructions ───────────────────────────────────────────────────────
_SYSTEM_INSTRUCTIONS = """\
You are an expert AI customer support assistant for TelecomCo, a telecom company providing broadband and mobile services.

STRICT RULES — NEVER VIOLATE THESE:
1. Answer ONLY using information from the RETRIEVED KNOWLEDGE BASE ARTICLES provided below.
2. NEVER invent facts, figures, prices, timeframes, or processes not mentioned in the articles.
3. ALWAYS cite the article_id(s) you used in the "evidence" field.
4. If the retrieved articles do NOT contain enough information to fully answer the question, set status to "followup_needed" and ask clarifying questions.
5. If you cannot answer confidently (confidence < 70) or if the issue is complex/unresolved, set status to "escalated".
6. Be empathetic, professional, and concise.
7. ALWAYS respond in valid JSON matching the schema exactly — no extra text outside the JSON block.\
"""


def build_prompt(
    customer: dict[str, Any],
    conversation_history: list[dict[str, str]],
    retrieved_articles: list[dict[str, Any]],
    user_message: str,
) -> str:
    """
    Assemble the complete prompt string to send to Gemini.

    Parameters
    ----------
    customer : full customer profile dict
    conversation_history : list of {"role": "user"|"assistant", "content": "..."}
    retrieved_articles : top-k articles returned by RAG
    user_message : the latest message from the customer
    """

    # ── 1. Customer Profile section ───────────────────────────────────────────
    tickets = customer.get("recent_tickets", [])
    ticket_lines = "\n".join(
        f"    • [{t.get('status','?').upper()}] {t.get('ticket_id','?')}: {t.get('issue','?')} ({t.get('date','?')})"
        for t in tickets
    ) or "    (none)"

    customer_block = f"""\
=== CUSTOMER PROFILE ===
Customer ID   : {customer.get('customer_id', 'N/A')}
Name          : {customer.get('name', 'N/A')}
Plan          : {customer.get('plan', 'N/A')}
Billing Status: {customer.get('billing_status', 'N/A')}
Recent Tickets:
{ticket_lines}
========================\
"""

    # ── 2. Conversation History section ───────────────────────────────────────
    if conversation_history:
        history_lines = []
        for msg in conversation_history[-6:]:   # keep last 6 turns in context
            role = "Customer" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content']}")
        history_block = (
            "=== CONVERSATION HISTORY ===\n"
            + "\n".join(history_lines)
            + "\n==========================="
        )
    else:
        history_block = "=== CONVERSATION HISTORY ===\n(This is the first message.)\n==========================="

    # ── 3. Retrieved Articles section ─────────────────────────────────────────
    if retrieved_articles:
        article_parts = []
        for art in retrieved_articles:
            article_parts.append(
                f"[{art['article_id']}] {art['title']} (Category: {art['category']})\n"
                f"  Issue      : {art.get('issue', '')}\n"
                f"  Resolution : {art.get('resolution', '')}\n"
                f"  Escalate if: {art.get('escalation_condition', '')}\n"
                f"  Similarity : {art.get('similarity_score', 0):.2%}"
            )
        articles_block = (
            "=== RETRIEVED KNOWLEDGE BASE ARTICLES ===\n"
            + "\n\n".join(article_parts)
            + "\n========================================="
        )
    else:
        articles_block = (
            "=== RETRIEVED KNOWLEDGE BASE ARTICLES ===\n"
            "NO ARTICLES FOUND. You MUST set status to 'escalated'.\n"
            "========================================="
        )

    # ── 4. Current customer message ───────────────────────────────────────────
    current_msg_block = f"=== CURRENT CUSTOMER MESSAGE ===\n{user_message}\n================================"

    # ── 5. Output schema reminder ─────────────────────────────────────────────
    schema_block = (
        "=== REQUIRED JSON OUTPUT FORMAT ===\n"
        "Respond with ONLY the following JSON — no markdown, no extra text:\n"
        + _OUTPUT_SCHEMA
        + "\n===================================="
    )

    # ── Assemble full prompt ──────────────────────────────────────────────────
    prompt = "\n\n".join([
        _SYSTEM_INSTRUCTIONS,
        customer_block,
        history_block,
        articles_block,
        current_msg_block,
        schema_block,
    ])

    return prompt
