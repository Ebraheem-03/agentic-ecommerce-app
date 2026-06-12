# syntax=docker/dockerfile:1

# ---- Stage 1: builder -------------------------------------------------------
# Build wheels for runtime deps so the final image needs no build toolchain.
FROM python:3.12-slim AS builder
WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
 && pip wheel --wheel-dir /wheels -r requirements.txt

# ---- Stage 2: runtime (production) ------------------------------------------
FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install prebuilt wheels only — no compilers in the final image.
COPY --from=builder /wheels /wheels
COPY requirements.txt ./
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
 && rm -rf /wheels

# Run as an unprivileged user.
RUN useradd --create-home --uid 1001 appuser
COPY --chown=appuser:appuser app ./app
# Alembic config + migrations ship in the image so `alembic upgrade head` can run
# as a deploy/release step against the target DB (URL from DATABASE_URL env).
COPY --chown=appuser:appuser alembic.ini ./alembic.ini
COPY --chown=appuser:appuser alembic ./alembic
USER appuser

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
