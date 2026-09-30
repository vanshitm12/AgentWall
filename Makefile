.PHONY: up down build test test-api test-e2e migrate logs shell-api clean

# Start all services
up:
	docker compose up -d --build

# Stop all services
down:
	docker compose down

# Build all containers
build:
	docker compose build

# Run all tests
test: test-api

# Run API tests
test-api:
	cd apps/api && python -m pytest tests/ -v

# Run end-to-end tests
test-e2e:
	cd tests && python -m pytest -v

# Run database migrations
migrate:
	cd apps/api && alembic upgrade head

# Tail logs for all services
logs:
	docker compose logs -f

# Tail logs for specific service
logs-%:
	docker compose logs -f $*

# Shell into API container
shell-api:
	docker compose exec agentwall-api /bin/bash

# Shell into dashboard container
shell-dashboard:
	docker compose exec agentwall-dashboard /bin/sh

# Reset database (destructive)
reset-db:
	docker compose down -v postgres
	docker compose up -d postgres
	sleep 3
	$(MAKE) migrate

# Format Python code
fmt:
	cd apps/api && python -m ruff format .
	cd apps/api && python -m ruff check --fix .

# Lint Python code
lint:
	cd apps/api && python -m ruff check .
	cd apps/api && python -m mypy app/

# Clean up
clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
