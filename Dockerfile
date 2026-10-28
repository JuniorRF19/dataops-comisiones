# ── base: dependencias + código de la aplicación ──────────────────────────
FROM python:3.11-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /opt/dataops

COPY app/requirements.txt app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt

COPY app/ app/
COPY config/ config/
COPY data/ data/
COPY scripts/ scripts/
COPY infra/ infra/

# ── test: imagen de CI (lint + validación ARM + unit tests) ───────────────
FROM base AS test
COPY requirements-dev.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests/ tests/
CMD ["sh", "-c", "ruff check app scripts tests && python scripts/validate_arm.py && pytest -v --junitxml=reports/junit.xml"]

# ── runtime: imagen que se despliega en DEV / QA / PRD ────────────────────
FROM base AS runtime
CMD ["python", "-m", "app.pipeline", "--env", "dev"]
