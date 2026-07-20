## What changed and why

<!-- Summarize the change and the motivation. -->

## Checklist

- [ ] Backend: `cd backend && python -m pytest -q` passes
- [ ] Frontend: `cd frontend && npm run build && npm run test -- --run` passes
- [ ] `docker build .` succeeds
- [ ] If SQL execution or validation logic changed: confirmed no write statement
      (INSERT/UPDATE/DELETE/DROP/ALTER/etc.) can pass, including through the mock
      AI assistant path
- [ ] No new required env var without updating `.env.example` / the README

**Reminder:** `main` auto-deploys on every merge once the hosting secrets are
configured (`RENDER_DEPLOY_HOOK` + `DEPLOY_URL`, or Railway's native GitHub
integration). CI must be green before merging.
