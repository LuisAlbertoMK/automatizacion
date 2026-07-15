.PHONY: setup test lint fmt run api health check clean

# ── Setup ────────────────────────────────────────────────────
setup:
	pip install -e ".[test,web,dev]"
	playwright install chromium

# ── Quality ──────────────────────────────────────────────────
test:
	pytest tests/ -v --tb=short --cov=src --cov-report=term-missing --cov-fail-under=80

test-fast:
	pytest tests/ -x -q --tb=short

lint:
	ruff check src/ tests/ app.py

fmt:
	ruff format src/ tests/ app.py

typecheck:
	mypy src/ --ignore-missing-imports

security:
	bandit -r src/ -x tests/ -ll --quiet

# ── Run ──────────────────────────────────────────────────────
run:
	streamlit run app.py

api:
	uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload

# ── Docker ───────────────────────────────────────────────────
up:
	docker compose --profile app --profile api up -d

down:
	docker compose --profile app --profile api down

logs:
	docker compose logs -f --tail=50

# ── Health ───────────────────────────────────────────────────
health:
	python health_check.py --quick

# ── Cleanup ──────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf coverage_html/ .pytest_cache/ .mypy_cache/
