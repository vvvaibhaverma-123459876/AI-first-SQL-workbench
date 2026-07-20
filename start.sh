#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# ── colours ──────────────────────────────────────────────────────────────────
BOLD='\033[1m'; CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RESET='\033[0m'

echo -e "\n${BOLD}${CYAN}  AI SQL Studio${RESET}  —  local-first AI workbench\n"

# ── 1. Python venv ────────────────────────────────────────────────────────────
if [ ! -d "$BACKEND/.venv" ]; then
  echo -e "${YELLOW}Setting up Python environment…${RESET}"
  python3 -m venv "$BACKEND/.venv"
  "$BACKEND/.venv/bin/pip" install -q -r "$BACKEND/requirements.txt"
fi

# ── 2. .env ───────────────────────────────────────────────────────────────────
if [ ! -f "$BACKEND/.env" ]; then
  cp "$BACKEND/.env.example" "$BACKEND/.env"
  # Auto-detect first available Ollama model
  if command -v ollama &>/dev/null; then
    MODEL=$(ollama list 2>/dev/null | awk 'NR>1 {print $1; exit}')
    if [ -n "$MODEL" ]; then
      sed -i '' "s/qwen2.5-coder:7b/$MODEL/" "$BACKEND/.env" 2>/dev/null || \
      sed -i "s/qwen2.5-coder:7b/$MODEL/" "$BACKEND/.env"
      echo -e "  Using Ollama model: ${GREEN}$MODEL${RESET}"
    fi
  fi
fi

# ── 3. Build frontend if dist is stale ───────────────────────────────────────
DIST="$FRONTEND/dist/index.html"
SRC_CHANGED=$(find "$FRONTEND/src" -newer "$DIST" 2>/dev/null | head -1)
if [ ! -f "$DIST" ] || [ -n "$SRC_CHANGED" ]; then
  echo -e "${YELLOW}Building frontend…${RESET}"
  if [ ! -d "$FRONTEND/node_modules/.bin" ]; then
    (cd "$FRONTEND" && npm install --silent)
  fi
  (cd "$FRONTEND" && node_modules/.bin/vite build --logLevel warn)
fi

# ── 4. Seed demo data ─────────────────────────────────────────────────────────
if [ ! -f "$BACKEND/data/demo_analytics.db" ]; then
  echo -e "${YELLOW}Seeding demo database…${RESET}"
  (cd "$BACKEND" && .venv/bin/python -m app.db.seed_demo_data)
fi

# ── 5. Start backend (serves frontend as static files) ───────────────────────
PORT="${PORT:-8000}"
echo -e "\n${GREEN}${BOLD}  Ready!  →  http://localhost:$PORT${RESET}\n"
cd "$BACKEND"
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
