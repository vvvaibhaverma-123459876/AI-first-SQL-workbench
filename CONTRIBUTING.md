# Contributing

`main` auto-deploys once hosting is configured (Render deploy hook, or
Railway's native GitHub integration — see the README's "Deploy" section).
Treat `main` as production.

## Workflow

1. Branch off `main`.
2. Make your change, with tests where it makes sense.
3. Open a PR. `.github/workflows/ci-and-deploy.yml`'s `test` job runs backend
   pytest, frontend build + tests, and a Docker build.
4. **CI must be green before merge.** Merging to `main` triggers a live
   deploy, so a red PR should never be merged.
5. `.github/workflows/health-check.yml` pings the live `/api/health` endpoint
   daily and opens a GitHub issue if the deploy is down.

## Local checks before opening a PR

```bash
cd backend && python -m pytest -q
cd ../frontend && npm run build && npm run test -- --run
docker build -t ai-first-sql-workbench:local ..
```

## Scope

The hosted demo runs `AI_MODE=mock` and must never require an API key or make
an outbound network call — `app/llm/providers.py`'s `MockProvider` is the only
thing it should ever reach. SQL execution must stay read-only in every mode;
`BANNED_PATTERN` in `app/services/validation_service.py` is the guardrail —
don't weaken it without very good reason and matching tests.
