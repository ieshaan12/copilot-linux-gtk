# Justfile for Copilot for GNOME
# https://github.com/casey/just

# Default recipe: show help
default:
    @just --list

# Run the application
run:
    uv run copilot-gtk

# Run all unit tests (excludes UI tests)
test:
    uv run pytest tests/ -v --ignore=tests/ui

# Run unit tests only (alias for 'test')
test-unit:
    uv run pytest tests/ -v --ignore=tests/ui

# Run unit tests with coverage
test-coverage:
    uv run pytest tests/ -v --ignore=tests/ui --cov=src/copilot_gtk --cov-report=term-missing

# Run UI tests (requires display server; uses Xvfb if available)
test-ui:
    #!/usr/bin/env bash
    set -e
    export COPILOT_GTK_MOCK_BACKEND=1
    export COPILOT_GTK_MOCK_DELAY=30
    export GTK_A11Y=atspi
    if command -v xvfb-run &> /dev/null; then
        xvfb-run --auto-servernum --server-args="-screen 0 1280x1024x24" \
            uv run pytest tests/ui/ -v --timeout=60
    else
        uv run pytest tests/ui/ -v --timeout=60
    fi

# Run all tests (unit + UI)
test-all: test-unit test-ui

# Run all checks + all tests (for CI)
test-ci: lint typecheck test-unit test-ui

# Run lint checks (ruff)
lint:
    uv run ruff check src/ tests/
    uv run ruff format --check src/ tests/

# Auto-fix lint issues
lint-fix:
    uv run ruff check --fix src/ tests/
    uv run ruff format src/ tests/

# Run type checking (mypy)
typecheck:
    uv run mypy src/copilot_gtk/ --ignore-missing-imports

# Run all checks (lint + typecheck + test)
check: lint typecheck test

# Validate data files (desktop, appstream, GSettings schema)
validate:
    desktop-file-validate data/io.github.ieshaan.CopilotGTK.desktop.in || true
    appstreamcli validate --no-net data/io.github.ieshaan.CopilotGTK.metainfo.xml.in || true
    glib-compile-schemas --strict --dry-run data/

# Sync dependencies
sync:
    uv sync

# Clean build artifacts
clean:
    rm -rf build/ build-flatpak/ .pytest_cache/ .mypy_cache/
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
