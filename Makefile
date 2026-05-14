.PHONY: install dev backend frontend build start test seed

install:
	cd backend && python -m pip install -r requirements.txt
	cd frontend && npm install

dev:
	npm run dev

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

start:
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000

test:
	cd backend && pytest

seed:
	cd backend && python -m app.db.seed_demo_data
