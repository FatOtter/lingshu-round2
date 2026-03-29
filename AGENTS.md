# AGENTS.md

## Cursor Cloud specific instructions

### Overview

LingShu is an ontology-centric data operating system with a Python/FastAPI backend and Next.js frontend. See `CLAUDE.md` for full architecture details, and `QUICKSTART.md` / `DEPLOYMENT.md` for user-facing guides.

### Infrastructure Services

Three Docker containers are required (PostgreSQL 16, Neo4j 5, Redis 7). Start them with:

```bash
docker compose -f docker/docker-compose.yml up -d postgres neo4j redis
```

**Gotcha — Neo4j healthcheck:** The `docker/docker-compose.yml` healthcheck for Neo4j references `$NEO4J_AUTH_PASSWORD` which is not set as a container env var (Neo4j interprets `NEO4J_*` vars as config). Neo4j will show as "unhealthy" even though it is running fine. Verify Neo4j manually: `docker exec <neo4j-container> cypher-shell -u neo4j -p lingshu123 'RETURN 1'`. Alternatively, run Neo4j directly:

```bash
docker run -d --name neo4j-dev -e NEO4J_AUTH=neo4j/lingshu123 -p 7474:7474 -p 7687:7687 neo4j:5-community
```

The `docker/` directory needs a `.env` file with at least:

```
POSTGRES_USER=lingshu
POSTGRES_PASSWORD=lingshu123
POSTGRES_DB=lingshu
LINGSHU_NEO4J_PASSWORD=lingshu123
LINGSHU_JWT_SECRET=dev-secret-key-change-in-production
MINIO_ROOT_PASSWORD=minioadmin123
```

### Backend

- Package manager: `uv` (lockfile: `uv.lock`)
- Install: `cd backend && uv sync --all-extras`
- Config uses `pydantic-settings` with `LINGSHU_` env prefix. It does **not** auto-load `.env` files; you must export env vars or set them inline.
- Key env vars for local dev (export these before running backend):

```bash
export LINGSHU_DATABASE_URL="postgresql+asyncpg://lingshu:lingshu123@localhost:5432/lingshu"
export LINGSHU_NEO4J_URI="bolt://localhost:7687"
export LINGSHU_NEO4J_USER="neo4j"
export LINGSHU_NEO4J_PASSWORD="lingshu123"
export LINGSHU_REDIS_URL="redis://localhost:6379/0"
export LINGSHU_AUTH_MODE="dev"
export LINGSHU_JWT_SECRET="change-me-in-production"
export LINGSHU_SERVER_ENV="development"
export LINGSHU_SEED_ADMIN_EMAIL="admin@lingshu.dev"
export LINGSHU_SEED_ADMIN_PASSWORD="admin123"
export LINGSHU_RBAC_ENABLED="false"
```

- Migrations: `cd backend && uv run alembic upgrade head` (needs `LINGSHU_DATABASE_URL` exported)
- Dev server: `cd backend && uv run uvicorn lingshu.main:app --reload --port 8000`
- Lint/test/typecheck commands: see `Makefile` targets `lint`, `test`, `typecheck`
- **Auth mode `dev`**: Uses `X-User-Id`, `X-Tenant-Id`, `X-User-Role` headers for authentication, no JWT cookies required for API calls. Login endpoint still works and seeds the admin user on first startup.
- Default admin: `admin@lingshu.dev` / `admin123`

### Frontend

- Package manager: `pnpm` (lockfile: `pnpm-lock.yaml`)
- Install: `cd frontend && pnpm install`
- The `package.json` includes `pnpm.onlyBuiltDependencies: ["esbuild"]` to avoid interactive build script approval prompts.
- Dev server: `cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8000 pnpm dev`
- Tests: `pnpm test:run` (Vitest), `pnpm lint` (ESLint)
- Frontend connects to backend via `NEXT_PUBLIC_API_URL` env var (default: `http://localhost:8000`)

### Port Summary (local dev, no Docker for app services)

| Service    | Port |
|------------|------|
| Backend    | 8000 |
| Frontend   | 3000 |
| PostgreSQL | 5432 |
| Neo4j HTTP | 7474 |
| Neo4j Bolt | 7687 |
| Redis      | 6379 |

### Docker Installation (Cloud Agent VMs)

Cloud Agent VMs need Docker installed manually. Use fuse-overlayfs storage driver and iptables-legacy. See the system prompt for the exact Docker installation commands.
