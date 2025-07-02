# Makefile for FlightioCrawler Development

.PHONY: help install format lint type-check test clean setup-dev run-tests run-mypy run-flake8 run-black run-isort

# Default target
help:
	@echo "Available commands:"
	@echo "  install      Install dependencies"
	@echo "  setup-dev    Setup development environment"
	@echo "  format       Format code with black and isort"
	@echo "  lint         Run all linting tools"
	@echo "  type-check   Run mypy type checking"
	@echo "  test         Run all tests"
	@echo "  clean        Clean temporary files"
	@echo "  run-tests    Run pytest with coverage"
	@echo "  run-mypy     Run mypy type checker"
	@echo "  run-flake8   Run flake8 linter"
	@echo "  run-black    Run black formatter"
	@echo "  run-isort    Run isort import sorter"

# Install dependencies
install:
	python -m pip install --upgrade pip
	python -m pip install -r requirements.txt
	python -m pip install -e .

# Setup development environment
setup-dev:
	python -m pip install --upgrade pip
	python -m pip install poetry
	poetry install --with dev
	@echo "Development environment setup complete!"
	@echo "Run 'make format' to format code"
	@echo "Run 'make lint' to check code quality"
	@echo "Run 'make test' to run tests"

# Format code with black and isort
format: run-black run-isort
	@echo "Code formatting complete!"

# Run black formatter
run-black:
	@echo "Running black..."
	python -m black . --line-length=88

# Run isort import sorter
run-isort:
	@echo "Running isort..."
	python -m isort . --profile=black --line-length=88

# Run flake8 linter
run-flake8:
	@echo "Running flake8..."
	python -m flake8 --max-line-length=88 --extend-ignore=E203,W503,E722,F401 --max-complexity=15 .

# Run mypy type checker
run-mypy:
	@echo "Running mypy..."
	python -m mypy --config-file=mypy.ini .

# Run all linting tools
lint: run-flake8 run-mypy
	@echo "Linting complete!"

# Type checking
type-check: run-mypy

# Run tests with coverage
run-tests:
	@echo "Running tests..."
	python -m pytest tests/ --tb=short --cov=. --cov-report=term-missing --cov-report=html

# Run all tests
test: run-tests

# Clean temporary files
clean:
	@echo "Cleaning temporary files..."
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf htmlcov/ 2>/dev/null || true
	rm -rf .pytest_cache/ 2>/dev/null || true
	rm -rf .mypy_cache/ 2>/dev/null || true
	@echo "Cleanup complete!"

# Security check with bandit
security:
	@echo "Running security checks..."
	python -m bandit -r . -f json -o bandit-report.json || true
	@echo "Security check complete! Check bandit-report.json for results."

# Check for vulnerabilities in dependencies
safety:
	@echo "Checking dependencies for vulnerabilities..."
	python -m safety check --json --output safety-report.json || true
	@echo "Safety check complete! Check safety-report.json for results."

# Run all quality checks
quality: format lint security safety test
	@echo "All quality checks complete!"

# Build documentation (if sphinx is used)
docs:
	@echo "Building documentation..."
	cd docs && make html
	@echo "Documentation built in docs/_build/html/"

# Start development server
dev-server:
	@echo "Starting development server..."
	python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Start production server
prod-server:
	@echo "Starting production server..."
	python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# Database migrations (if using alembic)
migrate:
	@echo "Running database migrations..."
	python -m alembic upgrade head

# Create new migration
migration:
	@echo "Creating new migration..."
	@read -p "Enter migration message: " msg; \
	python -m alembic revision --autogenerate -m "$$msg"

# Docker commands
docker-build:
	@echo "Building Docker image..."
	docker build -t flightio-crawler .

docker-run:
	@echo "Running Docker container..."
	docker-compose up -d

docker-stop:
	@echo "Stopping Docker containers..."
	docker-compose down

# Performance profiling
profile:
	@echo "Running performance profiling..."
	python -m cProfile -o profile.stats main_crawler.py
	@echo "Profile saved to profile.stats"

# Check dependencies for updates
check-updates:
	@echo "Checking for dependency updates..."
	python -m pip list --outdated

# Update dependencies
update-deps:
	@echo "Updating dependencies..."
	python -m pip install --upgrade -r requirements.txt

# Backup database
backup-db:
	@echo "Creating database backup..."
	pg_dump -h localhost -U crawler flight_data > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "Database backup created!"

# Full development setup from scratch
setup-full: setup-dev format lint test
	@echo "Full development setup complete!"
	@echo "Your development environment is ready!"

# Quick check before commit
pre-commit: format lint test
	@echo "Pre-commit checks passed! Ready to commit."

# CI/CD simulation
ci: format lint type-check security safety test
	@echo "CI/CD simulation complete!"

# Show project status
status:
	@echo "=== Project Status ==="
	@echo "Python version: $(shell python --version)"
	@echo "Pip version: $(shell python -m pip --version)"
	@echo "Working directory: $(shell pwd)"
	@echo "Git status:"
	@git status --short 2>/dev/null || echo "Not a git repository"
	@echo ""
	@echo "=== Recent test results ==="
	@python -m pytest tests/ --tb=no -q 2>/dev/null || echo "No tests run yet" 