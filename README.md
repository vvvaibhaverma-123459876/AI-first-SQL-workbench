# AI-first SQL Workbench — Local AI Edition

A local-first AI SQL workbench that combines a React/Vite frontend, FastAPI backend, SQLite demo analytics database, safe SQL execution, and a local AI assistant powered by Ollama or a built-in mock fallback.

The project is designed to be portfolio-ready: one app, local-only AI, safe SQL guardrails, assistant orchestration, caching, and a lightweight learning-memory layer.

## What changed in this edition

### Unified frontend + backend

- API routes now live under `/api`.
- The React app calls `/api` by default.
- Vite proxies `/api` to the FastAPI backend during development.
- FastAPI can serve the built React frontend from `frontend/dist` in production.
- Root-level `package.json`, `Makefile`, `Dockerfile`, and `docker-compose.yml` were added.

### Local AI inside the app

- Added `/api/ai/status` to check local Ollama connectivity and installed models.
- Default local model target: `qwen2.5-coder:7b`.
- No external provider API keys are required.
- If Ollama is not running, the app remains usable through a mock local fallback for demo/testing.

### Assistant orchestrator

New endpoint:

```text
POST /api/assistant/run
```

Flow:

```text
question
→ schema/table suggestion
→ local memory lookup
→ SQL generation through local model
→ SQL validation
→ repair loop if needed
→ safe execution
→ result explanation
→ next-question suggestions
→ memory storage
```

### Local learning memory, not fake RL

This project does **not** pretend to run reinforcement learning on top of Ollama. Instead, it implements the useful local-learning layer you wanted:

- successful questions and generated SQL are stored locally
- similar future questions reuse previous SQL before calling Ollama
- usage count increases confidence
- thumbs-up/down feedback updates confidence
- repeated questions become faster
- model dependency reduces over time for common analysis patterns

New endpoints:

```text
GET  /api/assistant/memory
POST /api/assistant/feedback
```

### Result caching

Repeated read-only SQL queries are cached locally for faster fetching.

Config:

```env
RESULT_CACHE_TTL_SECONDS=900
```

### Workbench UX upgrades

- Local AI status panel
- Assistant run trace/steps
- Feedback buttons
- Local learning memory panel
- Table preview from sidebar
- Click table to insert `SELECT *`
- Click column to insert column name
- Result cache indicator
- Better backend disconnected state

---

## Quick start

### 1. Install backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate       # Windows
pip install -r requirements.txt
cp .env.example .env
python -m app.db.seed_demo_data
```

### 2. Install frontend

```bash
cd frontend
npm install
cp .env.example .env
```

### 3. Start both together

From the project root:

```bash
npm install
npm run dev
```

Or run separately:

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm run dev
```

Open:

```text
http://localhost:5173
```

---

## Run with Ollama

Install Ollama, then pull the recommended SQL/code model:

```bash
ollama pull qwen2.5-coder:7b
```

In `backend/.env`:

```env
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b
```

Start backend + frontend:

```bash
npm run dev
```

The UI will show whether Ollama is connected and whether the active model is available.

---

## Production-style local run

Build the frontend:

```bash
cd frontend
npm run build
```

Start FastAPI:

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000
```

FastAPI will serve the built React app and the `/api` routes from the same server.

---

## Docker

```bash
docker compose up --build
```

The app runs at:

```text
http://localhost:8000
```

The Docker container expects Ollama on the host machine through:

```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

---

## API highlights

```text
GET  /api/health
GET  /api/ai/status
GET  /api/schema
GET  /api/tables/{table_name}/preview
POST /api/generate-sql
POST /api/validate-sql
POST /api/execute-sql
POST /api/explain-sql
POST /api/repair-sql
POST /api/suggest-tables
POST /api/assistant/run
GET  /api/assistant/memory
POST /api/assistant/feedback
GET  /api/history
GET  /api/saved-queries
POST /api/saved-queries
```

Backward-compatible root routes still exist, but `/api/*` is the recommended interface.

---

## Architecture

```text
AI-first-SQL-workbench/
├── backend/
│   ├── app/
│   │   ├── api/                  # FastAPI routes + Pydantic schemas
│   │   ├── assistant/            # end-to-end assistant orchestration
│   │   ├── core/                 # settings + absolute path config
│   │   ├── db/                   # demo data + metadata init
│   │   ├── llm/                  # local providers: Ollama, mock, optional HF
│   │   ├── models/               # saved queries, history, memory, result cache
│   │   ├── services/             # AI, execution, cache, schema, validation
│   │   └── utils/
│   ├── data/
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── components/           # workbench panels
│   │   ├── services/             # axios API client
│   │   ├── store/                # Zustand app state
│   │   └── types/
│   └── dist/                     # generated by npm run build
├── Dockerfile
├── docker-compose.yml
├── Makefile
└── package.json
```

---

## Testing status

Backend tests were run successfully:

```text
6 passed
```

Frontend production build was run successfully:

```text
tsc -b && vite build
```

---

## Current capability score

After these changes:

| Area | Score |
|---|---:|
| Frontend/backend integration | 8/10 |
| Local AI foundation | 7.5/10 |
| Assistant orchestration | 7.5/10 |
| Local learning/cache layer | 7/10 |
| Workbench UX | 7/10 |
| Production readiness | 6.5/10 |
| Portfolio readiness | 7.5/10 |

Overall: **7.5/10**.

The project is now much closer to the intended product. The next jump to 9/10 should focus on multi-database connections, richer semantic layer, charting, stronger eval benchmarks, and advanced schema embeddings.

---

## Remaining roadmap to 10/10

### 1. True semantic layer

Add governed definitions for metrics, dimensions, business terms, and joins.

```text
semantic/metrics.yml
semantic/joins.yml
semantic/business_terms.yml
```

### 2. Local embeddings for schema retrieval

Add a local vector index for schema/table descriptions using `sentence-transformers` + FAISS/Chroma/sqlite-vec.

### 3. Multi-database connection manager

Support:

- SQLite
- DuckDB
- Postgres
- MySQL
- Athena later

### 4. Charting and result intelligence

Add:

- automatic chart suggestion
- trend detection
- anomaly explanation
- top contributor analysis
- funnel/cohort helpers

### 5. Evaluation harness

Add golden question tests:

```text
question → expected tables → expected SQL patterns → execution check
```

Track:

- SQL validity rate
- execution success rate
- repair success rate
- cache hit rate
- feedback score

### 6. Stronger workbench UX

Add:

- close/rename tabs
- run selected SQL
- SQL formatter button
- resizable panels
- command palette
- query folders
- chart panel

---

## Positioning

This is no longer just a SQL editor with an AI button.

It is now a **local AI SQL workbench** with:

- local model runtime support
- assistant workflow
- safe SQL execution
- memory-backed learning
- result caching
- feedback loop
- unified frontend/backend deployment

