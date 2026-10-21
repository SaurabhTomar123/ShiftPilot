# Backend image: API, optimization worker, outbox relay and one-shot jobs (migrate, retention).
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app

COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY . .
RUN useradd --uid 10001 --no-create-home shiftpilot
USER shiftpilot

EXPOSE 8000
CMD ["uvicorn", "api.v2.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
