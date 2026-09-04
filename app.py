"""
app.py – Application entry-point.

Run with:
    python app.py

This starts the FastAPI server on http://localhost:8000 and also
serves the frontend from the /frontend directory.
"""
from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Add project root to path so `src` is importable ──────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import HOST, PORT
from src.rag import init_rag
from src.routes import router


# ── Lifespan: runs before first request, tears down after last ────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise RAG on startup; clean up on shutdown."""
    logger.info("=" * 60)
    logger.info("  Customer Support Resolution Assistant  –  NexusTiq24")
    logger.info("  Track: PS04")
    logger.info("=" * 60)
    logger.info("Initialising RAG pipeline …")
    try:
        init_rag()
        logger.info("RAG pipeline ready. ✓")
    except FileNotFoundError as exc:
        logger.critical("Data file missing – cannot start: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.critical("Failed to initialise RAG: %s", exc)
        sys.exit(1)

    yield  # ← server is running here

    logger.info("Shutting down.")


# ── FastAPI application ───────────────────────────────────────────────────────
app = FastAPI(
    title="Customer Support Resolution Assistant",
    description=(
        "AI-powered telecom support assistant using RAG (FAISS + Gemini), "
        "deterministic escalation, and grounded response generation."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS (allow the served frontend to call the API) ─────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(router, prefix="/api")

# ── Serve frontend static files ───────────────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def serve_index() -> FileResponse:
    """Serve the main SPA."""
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))




# ── Dev runner ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info",
    )
