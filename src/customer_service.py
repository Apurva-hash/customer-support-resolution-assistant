"""
Customer service – load and query customer profiles from JSON storage.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from src.config import CUSTOMERS_FILE

logger = logging.getLogger(__name__)

_customers: dict[str, dict[str, Any]] = {}   # customer_id → profile


def _load_customers() -> None:
    global _customers
    if not os.path.exists(CUSTOMERS_FILE):
        raise FileNotFoundError(f"Customers file not found at {CUSTOMERS_FILE}")
    with open(CUSTOMERS_FILE, "r", encoding="utf-8") as f:
        data: list[dict[str, Any]] = json.load(f)
    _customers = {c["customer_id"]: c for c in data}
    logger.info("Loaded %d customer profiles.", len(_customers))


# Initialise at import time
_load_customers()


def get_customer(customer_id: str) -> dict[str, Any] | None:
    """Return customer profile or None if not found."""
    return _customers.get(customer_id)


def list_customers() -> list[dict[str, Any]]:
    """Return all customer profiles."""
    return list(_customers.values())


def customer_exists(customer_id: str) -> bool:
    return customer_id in _customers
