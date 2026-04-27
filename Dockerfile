FROM python:3.11-slim AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY ./app ./app
COPY alembic.ini .
COPY alembic ./alembic

EXPOSE 8000

CMD ["sh", "-c", "python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]