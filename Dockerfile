FROM node:22-bookworm-slim AS frontend
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_DEV_LOGIN=false
RUN npm run build

FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && ffmpeg -version && ffprobe -version \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev
COPY backend/app app
COPY backend/migrations migrations
COPY backend/alembic.ini ./
COPY backend/scripts scripts
COPY --from=frontend /web/dist /srv/web
RUN useradd --create-home mustard && chown -R mustard:mustard /srv
USER mustard
ENV ENVIRONMENT=production DEV_AUTH=false COOKIE_SECURE=true
EXPOSE 10000
CMD ["uv", "run", "--no-sync", "python", "-m", "scripts.serve_web"]
