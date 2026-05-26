# Plan 35 — accounting-mcp Docker image
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    PORT=8014

WORKDIR /app

# Install uv (faster than pip for resolving deps)
RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY src ./src
RUN uv pip install --system .

EXPOSE 8014
CMD ["gestnova-accounting-http"]
