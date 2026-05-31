.PHONY: test test-cov lint format check clean

# Run all tests
test:
	pytest tests/ -v --tb=short

# Run tests with coverage
test-cov:
	pytest tests/ -v --cov=. --cov-report=term-missing

# Run linter
lint:
	ruff check .

# Auto-format all source files
format:
	ruff format .

# Lint + tests (CI gate)
check: lint test

# Remove build artifacts
clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -f tests/**/*.xlsx tests/**/*.xlsm 2>/dev/null || true
