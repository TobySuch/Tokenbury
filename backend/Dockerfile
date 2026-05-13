FROM oven/bun:alpine AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile
COPY frontend/ .
RUN bun run build

FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim
WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/ .
COPY --from=frontend-builder /app/dist /app/frontend_dist

RUN chmod +x entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
