.PHONY: up down logs load-bronze dbt-run dbt-test dbt-docs demo clean \
        install-dev lint type-check test test-all audit-init

# ── Docker ──
up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

# ── Data ──
load-bronze:
	python scripts/load_bronze.py

# ── dbt ──
dbt-run:
	cd dbt_project && dbt run

dbt-test:
	cd dbt_project && dbt test

dbt-docs:
	cd dbt_project && dbt docs generate && dbt docs serve --port 8080

# ── Governance ──
audit-init:
	psql -U $${POSTGRES_USER:-pfa} -d $${POSTGRES_DB:-pfa_olist} -f scripts/audit_log_migration.sql

# ── Python quality ──
install-dev:
	pip install -r api/requirements.txt
	pip install ruff mypy pytest httpx

lint:
	ruff check api ml scripts

type-check:
	mypy api --ignore-missing-imports

test:
	pytest -m "not integration and not llm"

test-all:
	pytest

# ── Full demo ──
demo: up load-bronze dbt-run dbt-test audit-init
	@echo "✅ Pipeline complete. Dashboard: http://localhost:3000 | API: http://localhost:8000/docs"

# ── Cleanup ──
clean:
	docker compose down -v
	rm -f data/gold.duckdb
