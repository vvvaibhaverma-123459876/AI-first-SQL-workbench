# AI SQL Studio — Local-First AI Workbench

A privacy-first SQL workbench that turns plain-English questions into SQL using a local AI model (Ollama). No cloud API keys. No data sent to the internet. Everything runs on your machine.

**[Live demo](http://localhost:8000)** · React + FastAPI + SQLite + Ollama

---

## Quick start

```bash
git clone https://github.com/vvvaibhaverma-123459876/AI-first-SQL-workbench.git
cd AI-first-SQL-workbench
./start.sh
```

Open **http://localhost:8000** — that's it.

`start.sh` handles everything automatically:
- creates the Python virtual environment
- installs backend dependencies
- detects your installed Ollama model
- builds the React frontend
- seeds the demo analytics database
- starts the server

> **Requires:** Python 3.11+, Node.js 18+, [Ollama](https://ollama.com) with any model installed (`mistral:7b`, `qwen2.5-coder:7b`, `llama3`, etc.)

---

## What it does

Type a question in plain English. The assistant:

1. Suggests relevant tables from the schema
2. Checks local memory for a cached answer
3. Generates SQL using your local Ollama model
4. Validates and auto-repairs the SQL if needed
5. Executes safely (read-only guardrails)
6. Explains the result in plain English
7. Suggests follow-up analyses
8. Stores the successful run locally for faster future queries

Everything happens locally. The only network call is to `localhost:11434` (Ollama).

---

## Features

### AI assistant
- **Ask + Run** — natural language → SQL → result → explanation in one click
- **Generate Only** — generate SQL without executing
- **Explain** — get a plain-English explanation of any SQL
- **Fix** — auto-repair broken SQL using the local model
- **Suggest Tables** — identify relevant tables for a question

### Editor
- Monaco editor with SQL syntax highlighting
- Multi-tab query workspace
- `⌘↵` to run SQL
- Inline save with named queries
- One-click table/column insertion from schema browser

### Results
- Paginated data table with sticky headers
- **Automatic bar chart** for numeric result sets
- Clickable follow-up questions from the assistant
- Export to CSV
- Cache-hit indicator (repeated queries return instantly)

### Schema browser
- Collapsible table list with column types and PK/FK indicators
- Table preview as a mini data grid
- Full-text search across tables and columns

### Learning memory
- Successful queries stored locally
- Reused on similar future questions (before calling Ollama)
- Thumbs-up/down feedback adjusts confidence
- Use count tracked — common patterns get faster over time

---

## Ollama setup

```bash
# Install Ollama: https://ollama.com
ollama pull mistral:7b        # recommended
# or: ollama pull qwen2.5-coder:7b
# or: ollama pull llama3
```

`start.sh` auto-detects whichever model you have installed. To override, edit `backend/.env`:

```env
OLLAMA_MODEL=mistral:7b
```

If Ollama is not running, the app falls back to a mock provider so you can still run SQL manually.

---

## Demo database

The app ships with a pre-seeded SQLite analytics database containing:

| Table | Description |
|---|---|
| `users` | 1 000 users with country, signup date, status |
| `transactions` | 5 000 transactions with amount, status, type |
| `cards` | Card assignments per user |
| `referrals` | Referral source and conversion data |
| `support_tickets` | Open/closed tickets with category |
| `onboarding_events` | Step-by-step onboarding funnel |

### Suggested demo queries

Try these in the AI prompt:

- *Top 20 users by total transaction amount*
- *Which referral channel has the best card activation rate?*
- *Monthly revenue trend for the last 6 months*
- *Users with open support tickets and their total spend*
- *Average days to first transaction by country*

---

## Architecture

```
AI-first-SQL-workbench/
├── start.sh                      ← single-command startup
├── backend/
│   └── app/
│       ├── api/                  ← FastAPI routes + Pydantic schemas
│       ├── assistant/            ← end-to-end orchestration pipeline
│       ├── core/                 ← settings, config
│       ├── db/                   ← demo seed data, metadata init
│       ├── llm/                  ← Ollama, mock, optional HuggingFace
│       ├── models/               ← SQLAlchemy metadata models
│       ├── services/             ← AI, execution, cache, schema, validation
│       └── utils/
├── frontend/
│   └── src/
│       ├── components/           ← Sidebar, EditorPanel, ResultsPanel, AIPanel
│       ├── services/             ← axios API client
│       ├── store/                ← Zustand global state
│       └── types/
├── Dockerfile
├── docker-compose.yml
└── Makefile
```

**Runtime flow:**

```
Browser → FastAPI (:8000)
            ├── /api/*   → Python services → SQLite / Ollama
            └── /*       → React SPA (served as static files)
```

No separate frontend server in production — FastAPI serves everything.

---

## Manual setup (alternative to start.sh)

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # edit OLLAMA_MODEL if needed
python -m app.db.seed_demo_data

# Frontend
cd ../frontend
npm install
npm run build                 # builds into frontend/dist/

# Start
cd ../backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Dev mode (hot reload)

```bash
npm install           # root — installs concurrently
npm run dev           # starts FastAPI + Vite dev server simultaneously
```

Frontend at `http://localhost:5173`, backend at `http://localhost:8000`.

---

## Docker

```bash
docker compose up --build
```

Open `http://localhost:8000`. Expects Ollama on the host at:

```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

---

## API reference

```
GET  /api/health
GET  /api/ai/status
GET  /api/schema
GET  /api/tables/{name}/preview

POST /api/generate-sql
POST /api/validate-sql
POST /api/execute-sql
POST /api/execute-sql/export
POST /api/explain-sql
POST /api/repair-sql
POST /api/suggest-tables

POST /api/assistant/run
GET  /api/assistant/memory
POST /api/assistant/feedback

GET  /api/history
GET  /api/saved-queries
POST /api/saved-queries
DELETE /api/saved-queries/{id}
```

---

## Configuration

All options in `backend/.env`:

```env
AI_PROVIDER=ollama                  # ollama | mock | hf
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral:7b

DEFAULT_ROW_LIMIT=200
RESULT_CACHE_TTL_SECONDS=900        # cache TTL for repeated queries
ASSISTANT_CACHE_MIN_SCORE=0.74      # similarity threshold for memory hits
MAX_REPAIR_ATTEMPTS=2
SQL_EXECUTION_TIMEOUT_SECONDS=30
```

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Zustand, Monaco Editor |
| Backend | Python, FastAPI, SQLAlchemy, Pydantic, sqlglot |
| AI runtime | Ollama (local) with mock fallback |
| Database | SQLite (demo) — extensible to Postgres, DuckDB |
| Dev tooling | concurrently, pytest, vitest |
