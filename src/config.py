import os
from dotenv import load_dotenv

load_dotenv()

# ── Gemini API ────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()

# ── Model identifiers ─────────────────────────────────────────────────────────
LLM_MODEL: str = "gemini-2.5-flash"
EMBEDDING_MODEL: str = "gemini-embedding-001"

# ── RAG settings ──────────────────────────────────────────────────────────────
TOP_K_ARTICLES: int = 3
EMBEDDING_DIMENSION: int = 3072          # gemini-embedding-001 output dim

# ── Escalation thresholds ─────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD: float = 70.0       # below this → escalate

# ── Data paths ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CUSTOMERS_FILE = os.path.join(DATA_DIR, "customers.json")
ARTICLES_FILE = os.path.join(DATA_DIR, "support_articles.json")
FAISS_INDEX_DIR = os.path.join(DATA_DIR, "faiss_index")
FAISS_INDEX_FILE = os.path.join(FAISS_INDEX_DIR, "articles.index")
FAISS_META_FILE = os.path.join(FAISS_INDEX_DIR, "articles_meta.json")

# ── Server ────────────────────────────────────────────────────────────────────
HOST: str = "0.0.0.0"
PORT: int = 8000
