FROM node:20-bookworm-slim AS prisma

ENV HOME=/home/appuser \
    XDG_CACHE_HOME=/home/appuser/.cache \
    PRISMA_HOME_DIR=/home/appuser/.prisma \
    PRISMA_BINARY_CACHE_DIR=/home/appuser/.cache/prisma-python/binaries \
    PRISMA_NODEENV_CACHE_DIR=/home/appuser/.cache/prisma-python/nodeenv

WORKDIR /app

COPY prisma ./prisma
COPY requirements.txt ./

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    && mkdir -p /home/appuser/.cache/prisma-python/binaries \
    /home/appuser/.cache/prisma-python/nodeenv \
    /home/appuser/.cache/prisma \
    /home/appuser/.prisma \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --break-system-packages prisma==0.11.0

RUN python3 -m prisma generate --schema=./prisma/schema.prisma

RUN python3 - <<'PY'
import pathlib
import shutil

import prisma

source = pathlib.Path(prisma.__file__).resolve().parent
target = pathlib.Path("/prisma-artifacts/prisma-package")

if target.exists():
    shutil.rmtree(target)

target.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(source, target)
PY


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    HOME=/home/appuser \
    XDG_CACHE_HOME=/home/appuser/.cache \
    PRISMA_HOME_DIR=/home/appuser/.prisma \
    PRISMA_BINARY_CACHE_DIR=/home/appuser/.cache/prisma-python/binaries \
    PRISMA_NODEENV_CACHE_DIR=/home/appuser/.cache/prisma-python/nodeenv

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=prisma /app/prisma /app/prisma
COPY --from=prisma /prisma-artifacts/prisma-package /usr/local/lib/python3.12/site-packages/prisma
COPY --from=prisma /home/appuser/.cache/prisma /home/appuser/.cache/prisma
COPY --from=prisma /home/appuser/.cache/prisma-python /home/appuser/.cache/prisma-python

RUN addgroup --system --gid 1001 appgroup \
    && adduser --system --uid 1001 --gid 1001 --home /home/appuser appuser \
    && mkdir -p /home/appuser/.cache/prisma-python/binaries \
    /home/appuser/.cache/prisma-python/nodeenv \
    /home/appuser/.prisma \
    && chown -R appuser:appgroup /app /home/appuser

USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
