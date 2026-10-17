FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

# PDF receipts use reportlab (pure Python + Pillow wheels): no OS-level PDF packages required.
COPY requirements.txt /srv/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=300 --retries=10 -r /srv/requirements.txt

COPY app /srv/app
COPY migrations /srv/migrations

EXPOSE 8080

# One process on purpose: the /api/v1 rate limiter keeps its rolling window in process memory.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-server-header"]
