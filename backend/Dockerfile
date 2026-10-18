FROM node:22-slim AS web-build

WORKDIR /web
COPY mobile/package.json mobile/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY mobile ./
ENV EXPO_NO_TELEMETRY=1
RUN npm run web:export


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

# PDF receipts use reportlab (pure Python + Pillow wheels): no OS-level PDF packages required.
COPY backend/requirements.txt /srv/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=300 --retries=10 -r /srv/requirements.txt

COPY backend/app /srv/app
COPY backend/migrations /srv/migrations
COPY --from=web-build /web/dist /srv/web

ENV WEB_DIST_DIR=/srv/web

EXPOSE 8080

# One process on purpose: the /api/v1 rate limiter keeps its rolling window in process memory.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-server-header"]
