# Cloud Agent Starter Skill — LingShu

> Use this skill whenever you need to set up, run, or test the LingShu codebase
> inside a Cloud Agent environment.

---

## 1. Quick-start: full-stack via Docker Compose (recommended)

The fastest way to get a running system is the **root** `docker-compose.yml`.
It launches backend, frontend, PostgreSQL, Neo4j, and Redis with dev-friendly
defaults (dev auth mode, RBAC off, seeded admin user).

```bash
# From repo root
docker compose up -d          # builds & starts all 5 services
docker compose logs -f backend  # watch backend until "Application startup complete"
```

| Service   | Host URL                    |
|-----------|-----------------------------|
| Frontend  | http://localhost:3100        |
| Backend   | http://localhost:8100        |
| Postgres  | localhost:5440              |
| Neo4j     | localhost:7690 (Bolt)       |
| Redis     | localhost:6390              |

After code changes, rebuild:

```bash
docker compose build backend   # or frontend
docker compose up -d
```

### Seeded credentials (root compose)

| Field    | Value              |
|----------|--------------------|
| Email    | admin@lingshu.dev  |
| Password | admin123           |

Auth mode is `dev` — see §3 for header-based bypass.

---

## 2. Local dev (no Docker for app, only infra)

Use this when you need hot-reload and direct debugger access.

### 2a. Start infrastructure only

```bash
# Option A: lightweight (Postgres + Neo4j + Redis only, test ports)
make test-infra                # ports 5433, 7688, 6380

# Option B: full infra (includes FoundationDB, MinIO, Nessie, Doris)
make dev                       # uses docker/docker-compose.yml
```

### 2b. Backend

```bash
cd backend
uv sync --all-extras           # install deps (or: make install)
```

Create `backend/.env` from `backend/.env.example` and adjust DB URLs to match
whichever infra option you chose. Key vars:

```env
LINGSHU_DATABASE_URL=postgresql+asyncpg://lingshu:lingshu@localhost:5432/lingshu
LINGSHU_NEO4J_URI=bolt://localhost:7687
LINGSHU_NEO4J_PASSWORD=password
LINGSHU_REDIS_URL=redis://localhost:6379/0
LINGSHU_AUTH_MODE=dev
LINGSHU_JWT_SECRET=change-me-in-production
```

Then:

```bash
uv run alembic upgrade head          # run migrations
uv run uvicorn lingshu.main:app --reload --port 8000
```

The seed function (`lingshu.setting.seed.run_seed`) runs automatically on first
startup and creates the default tenant + admin user.

### 2c. Frontend

```bash
cd frontend
pnpm install
NEXT_PUBLIC_API_URL=http://localhost:8000 pnpm dev   # default port 3000
```

When running against Docker-compose backend on port 8100:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8100 pnpm dev
```

---

## 3. Authentication & dev-mode bypass

### Cookie auth (production mode)

POST `/setting/v1/auth/login` with `{ "email": "…", "password": "…" }`.
Backend sets `lingshu_access` cookie. All subsequent requests carry it.

### Header bypass (dev mode — `LINGSHU_AUTH_MODE=dev`)

When no valid cookie is present the `AuthMiddleware` accepts headers:

```
X-User-ID: <any user RID, e.g. ri.user.00000000-0000-0000-0000-000000000001>
X-Tenant-ID: <any tenant RID, e.g. ri.tenant.00000000-0000-0000-0000-000000000001>
X-Role: admin          # optional, defaults to admin
```

Example with curl:

```bash
curl http://localhost:8000/ontology/v1/object-types/query \
  -H "X-User-ID: ri.user.00000000-0000-0000-0000-000000000001" \
  -H "X-Tenant-ID: ri.tenant.00000000-0000-0000-0000-000000000001" \
  -H "Content-Type: application/json" \
  -d '{"pagination":{"page":1,"page_size":20}}'
```

### Whitelisted paths (no auth required)

`/health`, `/setting/v1/auth/login`, `/setting/v1/auth/sso/config`, `/docs`,
`/openapi.json`, `/redoc`.

---

## 4. Testing workflows by area

### 4a. Backend unit & integration tests

```bash
cd backend
uv run pytest tests/unit -v              # unit only
uv run pytest tests/integration -v       # integration only (needs test infra)
uv run pytest --cov=lingshu --cov-report=term-missing   # full + coverage
```

Coverage must be ≥ 80%.

Backend tests use `httpx.AsyncClient` with `ASGITransport` (in-process, no live
server needed). The conftest creates a fresh `create_app()` per test.

For integration tests, start test infra first:

```bash
make test-infra       # Postgres:5433, Neo4j:7688, Redis:6380
```

### 4b. Backend lint & type-check

```bash
cd backend
uv run ruff check .         # lint
uv run ruff format --check .  # format check (use without --check to auto-fix)
uv run mypy .               # strict type check
```

Or all at once: `make check` (runs lint + typecheck + tests).

### 4c. Frontend Vitest (unit/component)

```bash
cd frontend
pnpm test -- --run          # single run
pnpm test                   # watch mode
```

### 4d. Frontend build

```bash
cd frontend
pnpm build                  # Next.js production build (catches TS errors)
```

### 4e. E2E tests (Playwright)

Playwright expects the app at `http://localhost:3000` (see
`frontend/playwright.config.ts`). Easiest setup:

```bash
# Terminal 1: start full stack via Docker
docker compose up -d

# Terminal 2: run E2E (Playwright auto-starts `pnpm dev` as webServer)
cd frontend
npx playwright install chromium --with-deps  # first time only
npx playwright test e2e/                     # all E2E specs
npx playwright test e2e/docker-e2e.spec.ts   # 33 basic checks
npx playwright test e2e/journeys/            # 78 journey tests
```

If the app is Docker-only (port 3100), override `baseURL`:

```bash
BASE_URL=http://localhost:3100 npx playwright test e2e/docker-e2e.spec.ts
```

### 4f. Full verification checklist

Before declaring "all tests pass", every layer must be green on latest code:

1. `cd backend && uv run pytest tests/ -q`
2. `cd frontend && pnpm test -- --run`
3. `docker compose build && docker compose up -d`
4. `cd frontend && npx playwright test e2e/`

---

## 5. Docker rebuild rules

Any change to `backend/src/` or `frontend/src/` requires a rebuild before
Docker-based E2E tests reflect the change:

```bash
docker compose build backend frontend
docker compose up -d
```

If `backend/pyproject.toml` or `uv.lock` changed, the backend Docker build
re-runs `uv sync`. If frontend `package.json` or `pnpm-lock.yaml` changed, the
frontend build re-runs `pnpm install`.

### Alembic migration safety

Before adding a new migration:

```bash
cd backend
uv run alembic heads          # must show exactly ONE head
uv run alembic revision --autogenerate -m "description"
uv run alembic heads          # still exactly ONE head
```

Multiple heads → `alembic merge` or fix `down_revision` before proceeding.

---

## 6. API conventions

### Request format (paginated queries)

```json
POST /ontology/v1/object-types/query
{ "pagination": { "page": 1, "page_size": 20 } }
```

### Response format

```json
{
  "data": [ ... ],
  "pagination": { "total": 42, "page": 1, "page_size": 20, "has_next": true },
  "metadata": { "request_id": "req_..." }
}
```

Frontend must use `PagedResponse<T>` — access `data?.data` for the array and
`data?.pagination?.total` for count. **Never** use `data?.data?.items`.

### RID format

`ri.{resource_type}.{uuid}` — e.g. `ri.obj.550e8400-e29b-41d4-a716-446655440000`.

### Error response

```json
{
  "error": { "code": "ONTOLOGY_DEPENDENCY_CONFLICT", "message": "..." },
  "metadata": { "request_id": "req_..." }
}
```

Error codes follow `{MODULE}_{CATEGORY}_{SPECIFIC}`.

---

## 7. Common environment variables

| Variable | Default | Notes |
|----------|---------|-------|
| `LINGSHU_AUTH_MODE` | `production` | Set to `dev` for header-based auth bypass |
| `LINGSHU_RBAC_ENABLED` | `true` | Set to `false` to skip Casbin checks |
| `LINGSHU_DATABASE_URL` | (see .env.example) | `postgresql+asyncpg://...` |
| `LINGSHU_NEO4J_URI` | `bolt://localhost:7687` | |
| `LINGSHU_REDIS_URL` | `redis://localhost:6379/0` | |
| `LINGSHU_JWT_SECRET` | `change-me-in-production` | Production rejects known weak values |
| `LINGSHU_CORS_ORIGINS` | `http://localhost:3000,http://localhost:3100` | Comma-separated |
| `LINGSHU_SEED_ADMIN_EMAIL` | `admin@example.com` | Seeded on first boot |
| `LINGSHU_SEED_ADMIN_PASSWORD` | `change_me_123` | Seeded on first boot |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend → backend base URL |

---

## 8. Project layout cheat-sheet

```
backend/src/lingshu/
  main.py          – FastAPI app factory, lifespan, middleware, routers
  config.py        – Pydantic Settings (LINGSHU_* env prefix)
  infra/           – DB, context vars, error codes, RID, logging
  setting/         – Auth, users, tenants, RBAC, audit
  ontology/        – Type definitions, versioning, graph storage
  data/            – Data sources, queries, masking
  function/        – Actions, global functions, workflows
  copilot/         – LangGraph agent, A2UI, sessions

frontend/src/
  app/             – Next.js App Router pages
  lib/api/         – API client functions per module
  hooks/           – React hooks (TanStack Query)
  stores/          – Zustand stores
  components/      – Shared UI (Shadcn/UI + Tailwind)

e2e/               – Playwright tests
  docker-e2e.spec.ts   – 33 basic smoke tests
  journeys/            – 78 user-journey tests (J01–J22)
```

### Module dependency direction

`Setting (横切) → Ontology → Data → Function → Copilot`

No reverse dependencies. Modules communicate via `Protocol` interfaces.

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| CORS errors in browser | Middleware order wrong or 500 masking | Ensure `CORSMiddleware` added **after** `AuthMiddleware` (LIFO = outer) |
| Login returns 500 (hidden by CORS) | DateTime timezone mismatch | Use `DateTime(timezone=True)` everywhere |
| List pages show "No items found" | Frontend using wrong response shape | Use `PagedResponse<T>`, access `data?.data` not `data?.data?.items` |
| 404 on API call | Frontend path ≠ backend router path | `grep -r "@router" backend/src/lingshu/{module}/router.py` |
| Docker "Multiple head revisions" | Conflicting Alembic migrations | `uv run alembic merge heads` |
| E2E test can't find element | Selector doesn't match actual UI | Read the target `page.tsx` first; prefer `getByRole` over `getByText` |

---

## 10. Keeping this skill up to date

When you discover a new setup trick, testing workaround, or debugging runbook
entry, **add it here** so future Cloud Agents benefit immediately.

### What to add

- New environment variables or feature flags that affect testing.
- Workarounds for flaky tests or infrastructure quirks.
- New Makefile targets or npm scripts.
- Changes to auth flow, seed data, or default credentials.
- Docker port changes or new services.
- Lessons learned from debugging sessions (add to §9 Troubleshooting).

### How to add

1. Open this file (`.cursor/skills/cloud-agent-starter.md`).
2. Add the entry to the most relevant section (or create a new subsection).
3. Keep entries concise: one symptom → one cause → one fix.
4. Commit with message: `docs(skill): <what you added>`.

### Review cadence

After completing any task that required non-obvious environment setup or
revealed a gotcha, ask yourself: "Would a future agent need this?" If yes,
update this skill before ending your session.
