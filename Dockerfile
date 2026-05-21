FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# F-14 Phase 4.2: usuário não-root fixo (uid 10001).
# Volume media_data precisa estar chowned para 10001:10001 no host
# antes do primeiro deploy desta versão.
RUN groupadd --system --gid 10001 app \
    && useradd  --system --uid 10001 --gid 10001 --home-dir /app --shell /usr/sbin/nologin app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts

# Ownership do /app (binários + código) — necessário para alembic gravar
# em alembic/versions se for o caso, e para media (mount externo).
RUN mkdir -p /app/media && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python -m scripts.bootstrap_admin && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
