# AI SQL Studio

AI SQL Studio is a local-first, AI-powered SQL workbench built for analysts and developers who want a modern SQL IDE experience without sending data to paid hosted services.

It combines:
- a professional SQL editor
- schema exploration
- safe read-only query execution
- natural-language-to-SQL
- SQL explanation and repair
- saved queries and query history
- a polished results grid

The project is designed to feel like a lightweight mix of DBeaver, VS Code, and an AI SQL copilot.

## Highlights

- **Local-first**: runs fully on your machine
- **Public-safe**: no proprietary names, secrets, or internal data
- **Read-only by default**: blocks unsafe SQL
- **LLM flexibility**: supports both Ollama and Hugging Face Transformers
- **Portfolio-ready**: modular codebase, tests, synthetic demo data, and clean UI

## Screenshots

Add screenshots here after running locally:
- `docs/screenshot-main.png`
- `docs/screenshot-editor.png`
- `docs/screenshot-results.png`
- `docs/screenshot-ai-panel.png`

## Features

### Workbench
- Schema explorer with tables, columns, PK/FK metadata
- Searchable schema sidebar
- Table preview with sample rows
- Multi-tab SQL editor powered by Monaco
- Query result grid with export to CSV
- Query timing, status, row counts, and logs

### AI Assistant
- Natural language to SQL generation
- SQL explanation in plain English
- SQL repair for failed queries
- Relevant table suggestions
- Join path suggestions
- Unified `/ask` endpoint for assistant workflows

### Safety
- Only `SELECT` and `WITH` statements are allowed
- Single statement enforcement
- Dangerous keywords blocked case-insensitively
- Validation with `sqlglot`
- Optional default `LIMIT` injection when absent

### Productivity
- Saved queries
- Query history
- SQL formatting
- Keyboard shortcut: `Ctrl/Cmd + Enter` to run
- Copy/export workflows

## Architecture

```text
AI SQL Studio/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── llm/
│   │   ├── models/
│   │   ├── services/
│   │   └── utils/
│   ├── data/
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── components/
    │   ├── services/
    │   ├── store/
    │   ├── types/
    │   └── utils/
    ├── package.json
    ├── vite.config.ts
    └── tailwind.config.js
```

## Tech Stack

### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS
- Monaco Editor
- TanStack Table
- Zustand
- Axios

### Backend
- Python 3.11+
- FastAPI
- SQLAlchemy
- Pydantic
- pandas
- sqlglot
- python-dotenv
- uvicorn
- requests

### AI Backends
- Ollama
- Hugging Face Transformers

### Database
- SQLite for demo analytics data
- SQLite for app metadata

## Local Privacy Positioning

AI SQL Studio is built around a local-first workflow:
- demo and metadata databases are local SQLite files
- Ollama can run fully on-device
- Hugging Face pipeline support can also run locally
- no paid API dependency is required

## Quick Start

### 1) Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env
python -m app.db.seed_demo_data
uvicorn app.main:app --reload --port 8000
```

### 2) Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173` and expects backend on `http://localhost:8000`.

## Running Ollama Locally

1. Install Ollama
2. Pull a local model, for example:

```bash
ollama pull llama3.1
```

3. In `backend/.env`, set:

```env
AI_PROVIDER=ollama
OLLAMA_MODEL=llama3.1
OLLAMA_BASE_URL=http://localhost:11434
```

## Using Hugging Face Locally

In `backend/.env`, set:

```env
AI_PROVIDER=hf
HF_MODEL=google/flan-t5-base
```

The backend will lazily load the model the first time it is used.

## Demo Questions

Try these prompts:
- Show the top 20 users by total transaction amount in the last 30 days
- How many onboarding attempts failed by step each month?
- Which referral channels drove the most approved cards?
- Compare support ticket volume by category over time
- What is the average transaction amount by card type?

## API Summary

- `GET /health`
- `GET /schema`
- `GET /tables/{table_name}/preview`
- `POST /generate-sql`
- `POST /validate-sql`
- `POST /execute-sql`
- `POST /explain-sql`
- `POST /repair-sql`
- `POST /suggest-tables`
- `POST /ask`
- `GET /history`
- `POST /saved-queries`
- `GET /saved-queries`
- `GET /saved-queries/{id}`
- `DELETE /saved-queries/{id}`

## Tests

### Backend

```bash
cd backend
pytest
```

### Frontend

```bash
cd frontend
npm run test
```

## Future Roadmap

- PostgreSQL and MySQL connection profiles
- richer relationship graph visualizations
- query plans and cost estimation
- notebook mode
- result charting
- pinned tabs persistence
- role-based SQL policies
- AI semantic caching

## Limitations

- demo ships with SQLite only
- local LLM quality depends on the installed model
- SQL auto-completion is intentionally lightweight in this version
- schema relationship inference is based on FK metadata and naming heuristics

## License

MIT
