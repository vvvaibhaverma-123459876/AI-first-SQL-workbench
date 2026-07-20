FROM node:20-bookworm AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend ./
RUN npm run build

FROM python:3.11-slim AS app
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend ./backend
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
WORKDIR /app/backend

# Render/Railway inject $PORT at runtime and expect the process to bind to it;
# 8000 is only the local-dev/docker-compose default.
ENV PORT=8000
# Mock by default in the container — a hosted demo has no local Ollama runtime
# to reach. Override to `ollama` (and set OLLAMA_BASE_URL) for a self-hosted
# container with a real local model available.
ENV AI_MODE=mock

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
