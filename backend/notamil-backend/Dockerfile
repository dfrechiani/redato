# Dockerfile pro backend Redato (portal + bot unificados).
#
# Optamos por Dockerfile manual em vez de Nixpacks/Railpack porque
# os builders do Railway tinham problemas reproduzíveis pra fazer
# bootstrap do pip em derivações Nix do Python — `pip` não acabava
# no PATH nem como módulo do site-packages.
#
# Quando este arquivo existe, Railway pula Nixpacks/Railpack desde
# que `railway.toml` declare `builder = "DOCKERFILE"`. Healthcheck e
# restart policy continuam vindo do `railway.toml`.
#
# Volume persistente: Railway monta o volume em `/app/data`. Esse
# diretório guarda PDFs (M8), JSONLs de audit/triggers/emails e o
# SQLite legado do bot.

FROM python:3.12-slim

WORKDIR /app

# postgresql-client traz `pg_dump` (usado pelo scripts/backup_postgres.sh).
# Sem libs adicionais — psycopg2-binary já vem com libpq estática.
# `--no-install-recommends` reduz tamanho da imagem.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Instala deps Python primeiro (camada cacheável). Só refaz quando
# requirements.txt muda.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto do código (.dockerignore filtra data/, __pycache__/, etc.).
COPY . .

# Railway injeta $PORT em runtime. CMD em shell form pra expandir a var.
CMD uvicorn redato_backend.unified_app:app --host 0.0.0.0 --port ${PORT:-8000}
