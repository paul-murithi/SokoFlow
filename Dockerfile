# Stage 1: Builder
FROM python:3.12-slim AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
# RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv \
#     uv sync --frozen
RUN uv sync --frozen

# Stage 2: Runtime
FROM python:3.12-slim AS runtime

# Setup system requirements as root
RUN useradd -m sokoflow

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Drop privileges
USER sokoflow

# Copy virtual environment from Stage 1
COPY --from=builder --chown=sokoflow:sokoflow /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy source code with direct ownership
COPY --chown=sokoflow:sokoflow . .

# Expose port and start server
EXPOSE 8000
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
