# ── Builder stage ────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency manifests first for cache-friendly layers
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtual environment
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

# Install the project itself
RUN uv sync --frozen --no-dev

# ── Runtime stage ───────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN groupadd --system lingshu && useradd --system --gid lingshu lingshu

WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini

# Put venv on PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER lingshu

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn lingshu.main:app --host 0.0.0.0 --port 8000"]
