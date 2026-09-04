TRACK_ID=PS04

# 🤖 Customer Support Resolution Assistant

> An AI-powered telecom support assistant that resolves customer queries using Retrieval-Augmented Generation (RAG), Gemini 2.5 Flash, and FAISS semantic search — with deterministic escalation and zero hallucination.

---

## 🏆 Overview

Built for the **NexusTiq24 Hackathon | Track PS04**, this system acts as a first-line AI support agent for a telecom company offering broadband and mobile services.

It receives a customer's conversation, their account information, and a curated knowledge base of 30 support articles. It then:

- **Understands** the customer's issue using Gemini 2.5 Flash
- **Retrieves** the most relevant support articles using FAISS vector search (RAG)
- **Generates** a grounded, evidence-cited response — never hallucinating
- **Asks follow-up questions** when information is missing
- **Escalates** to a human agent when confidence is low or the issue is complex
- **Generates an agent handover summary** with full context

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔍 RAG Pipeline | FAISS + gemini-embedding-001 for semantic article retrieval |
| 🧠 LLM | Gemini 2.5 Flash with JSON-mode output |
| 📋 Evidence Citing | Article IDs cited in every response |
| ❓ Follow-up Questions | Asked automatically when info is missing |
| 🚨 Deterministic Escalation | 5-rule engine that overrides LLM when needed |
| 📄 Agent Handover Summary | Full context packet for human agents |
| 🚫 No Hallucination | System prompt enforces article-only responses |
| 💾 JSON Storage | Customers and articles stored in flat JSON files |
| 🎨 Premium Dashboard UI | 3-panel dark glassmorphism interface |

---

## 🏗️ Architecture

```
Customer Message
      │
      ▼
  FastAPI /api/chat
      │
      ├─── GET Customer Profile (customers.json)
      │
      ├─── RAG Retrieval
      │     ├── Embed query (gemini-embedding-001)
      │     ├── Search FAISS index
      │     └── Return top-3 articles
      │
      ├─── Build Prompt
      │     ├── Customer profile
      │     ├── Conversation history
      │     └── Retrieved articles
      │
      ├─── Gemini 2.5 Flash
      │     └── Returns structured JSON
      │
      └─── Deterministic Escalation Check
            ├── Confidence < 70%? → Escalate
            ├── No articles found? → Escalate
            ├── Multiple unrelated categories? → Escalate
            ├── Billing dispute not covered? → Escalate
            └── Complex account issue? → Escalate
```

---

## 📁 Folder Structure

```
support-resolution-assistant/
│
├── app.py                      # FastAPI entry point + server
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── .env                        # API keys (create this)
│
├── src/
│   ├── config.py               # All settings & paths
│   ├── llm_service.py          # Gemini 2.5 Flash wrapper
│   ├── embeddings.py           # gemini-embedding-001 + FAISS index builder
│   ├── rag.py                  # RAG pipeline (init + retrieve)
│   ├── customer_service.py     # Customer profile loading & lookup
│   ├── escalation.py           # 5-rule deterministic escalation engine
│   ├── prompt_builder.py       # Prompt engineering template
│   └── routes.py               # All FastAPI endpoints
│
├── data/
│   ├── customers.json          # 20 telecom customer profiles
│   ├── support_articles.json   # 30 support knowledge-base articles
│   └── faiss_index/            # Auto-generated FAISS index files
│       ├── articles.index
│       └── articles_meta.json
│
└── frontend/
    ├── index.html              # Main SPA (3-panel dashboard)
    ├── style.css               # Dark glassmorphism CSS
    └── script.js               # Vanilla JS logic
```

---

## 🔧 Installation

### Prerequisites

- Python 3.10+
- pip
- A Google Gemini API key ([Get one here](https://aistudio.google.com/))

### Steps

```bash
# 1. Clone / navigate to the project
cd support-resolution-assistant

# 2. Create a virtual environment
python -m venv venv

# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your .env file
echo GEMINI_API_KEY=your_api_key_here > .env
```

---

## 🔑 Environment Variables

Create a `.env` file in the `support-resolution-assistant/` directory:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ Yes | Your Google Gemini API key from AI Studio |

---

## 🚀 How To Run

```bash
python app.py
```

The server starts at **http://localhost:8000**

- 🌐 **Dashboard UI**: http://localhost:8000
- 📚 **API Docs (Swagger)**: http://localhost:8000/docs
- 📖 **API Docs (ReDoc)**: http://localhost:8000/redoc

> **Note**: On first startup, the RAG pipeline will embed all 30 support articles and build the FAISS index. This takes ~30-60 seconds depending on API latency. Subsequent startups are instant (index is cached).

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the dashboard UI |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/customer/{id}` | Get customer profile by ID |
| `GET` | `/api/customers` | List all customers |
| `GET` | `/api/articles` | List all knowledge-base articles |
| `POST` | `/api/chat` | Main AI chat endpoint |
| `POST` | `/api/search` | Semantic search over articles |

### POST /api/chat – Request Body

```json
{
  "customer_id": "CUST001",
  "message": "My internet is very slow in the evenings.",
  "conversation_history": []
}
```

### POST /api/chat – Response

```json
{
  "status": "resolved",
  "response": "Based on article ART002, slow internet during peak hours (6–11 PM) ...",
  "confidence": 87,
  "evidence": ["ART002", "ART001"],
  "followup_questions": [],
  "summary_for_agent": "...",
  "retrieved_articles": [...]
}
```

---

## 🎬 Demo Flow

1. **Open** http://localhost:8000 in your browser
2. **Select a customer** from the dropdown (e.g., `CUST001 — Aditya Sharma`)
3. The **left panel** populates with the customer's plan, billing status, and recent tickets
4. **Type a message** or click a quick-suggestion chip (e.g., "📶 Slow Internet?")
5. The AI:
   - Embeds the query and retrieves the top-3 most relevant articles via FAISS
   - Sends the customer profile + articles + conversation to Gemini 2.5 Flash
   - Returns a structured response with evidence article IDs
6. The **right panel** shows:
   - Confidence score with animated bar
   - Status badge (Resolved / Follow-up Needed / Escalated)
   - Retrieved articles with similarity scores
   - Agent handover summary (if escalated)
7. Try a billing dispute with `CUST002 — Priya Nair` (overdue account) to see **escalation** in action

### Sample Queries to Try

| Customer | Query | Expected Outcome |
|---|---|---|
| CUST001 | "Internet is slow every evening" | Resolved – ART002 |
| CUST003 | "My SIM is not activating" | Resolved – ART012 |
| CUST002 | "I was double charged this month, I need a refund" | Escalated – billing dispute |
| CUST004 | "My account was suspended without notice" | Escalated – complex account |
| CUST010 | "I recharged but my balance wasn't updated" | Resolved – ART016 |

---

## 🛡️ Escalation Rules

The deterministic escalation engine triggers when:

1. **Confidence < 70%** – LLM is not confident enough
2. **No articles found** – No relevant knowledge base content for the query
3. **Multiple unrelated categories** – 3+ distinct issue categories in retrieved articles
4. **Billing dispute not covered** – Dispute keywords detected but no billing article retrieved
5. **Complex account issue** – Suspension/KYC/legal keywords detected

---

## 🧰 Tech Stack

| Component | Technology |
|---|---|
| Backend | Python, FastAPI |
| LLM | Gemini 2.5 Flash (`gemini-2.5-flash`) |
| Embeddings | `gemini-embedding-001` |
| Vector DB | FAISS (flat inner-product index) |
| Frontend | HTML5, Vanilla CSS, Vanilla JS |
| Storage | JSON files |
| Server | Uvicorn (ASGI) |

---

*Built with ❤️ for NexusTiq24 Hackathon | Track PS04*
