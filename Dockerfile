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
RUN uv sync --frozen --no-dev


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
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy source code with direct ownership
COPY --chown=sokoflow:sokoflow . .

EXPOSE 8000

CMD ["python", "main.py"]
