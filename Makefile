.PHONY: test lint clean install dev

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	python -m pytest tests/ -v --tb=short

test-cov:
	python -m pytest tests/ -v --cov=app --cov=bot --cov=analytics --cov-report=term-missing

lint:
	ruff check app/ bot.py analytics.py tests/

lint-fix:
	ruff check --fix app/ bot.py analytics.py tests/

clean:
	rm -rf __pycache__ .pytest_cache app/__pycache__ app/**/__pycache__
	rm -rf *.egg-info dist build
	rm -rf data/*.db

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down
