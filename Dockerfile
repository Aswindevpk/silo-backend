FROM python:3.14-slim

# Install uv from official binary image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock /app/

# Sync dependencies into /app/.venv
RUN uv sync --frozen --no-install-project

# Copy remaining application code
COPY . /app/

# Install the project itself
RUN uv sync --frozen