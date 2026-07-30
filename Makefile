.PHONY: install format lint type test test-unit verify build

install:
	python -m pip install -e ".[dev]"

format:
	python -m ruff format .
	python -m ruff check --fix .

lint:
	python -m ruff format --check .
	python -m ruff check .

type:
	python -m mypy

test:
	python -m pytest

test-unit:
	python -m unittest discover -s tests -v

verify: lint type test
	python scripts/validate_schemas.py
	python scripts/check_traceability.py

build:
	python -m build
