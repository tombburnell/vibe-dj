# Run from repo root: `make test`, `make test-api`, `make test-web`
.PHONY: test test-api test-web help

help:
	@echo "Targets:"
	@echo "  make test      - API (pytest) + web (npm run test --if-present)"
	@echo "  make test-api  - apps/api only"
	@echo "  make test-web  - apps/web-frontend only (no-op if no test script)"

test: test-api test-web

test-api:
	cd apps/api && uv run pytest

test-web:
	cd apps/web-frontend && npm run test --if-present
