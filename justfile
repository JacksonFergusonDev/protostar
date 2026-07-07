set shell := ["bash", "-uc"]
set unstable
set quiet

# --- ANSI Colors ---

blue := '\033[1;34m'
green := '\033[1;32m'
yellow := '\033[1;33m'
nc := '\033[0m'

# Show available commands
default:
    @just --list

# Sync/install dependencies using uv
sync:
    uv sync --quiet

# Auto-format Python code using Ruff
format: sync
    @printf "\n{{ blue }}=== Formatting Code ==={{ nc }}\n"
    uv run ruff check --fix .
    uv run ruff format .
    @printf "{{ green }}✔ Formatting complete{{ nc }}\n"

# Run linters (Ruff and Markdown)
lint: sync
    @printf "\n{{ blue }}=== Running Linters ==={{ nc }}\n"
    uv run ruff check .
    uv run ruff format --check .
    if command -v markdownlint-cli2 >/dev/null 2>&1; then \
        markdownlint-cli2 "**/*.md"; \
    elif command -v npx >/dev/null 2>&1; then \
        npx --yes markdownlint-cli2 "**/*.md"; \
    else \
        printf "{{ yellow }}⚠ markdownlint-cli2 not found. Skipping markdown linting.{{ nc }}\n"; \
    fi
    @printf "{{ green }}✔ Linting passed{{ nc }}\n"

# Run static type checking with Mypy
typecheck: sync
    @printf "\n{{ blue }}=== Running Type Checks ==={{ nc }}\n"
    uv run mypy .
    @printf "{{ green }}✔ Type checking passed{{ nc }}\n"

# Run only fast unit tests (excludes integration and exhaustive markers)
test-unit: sync
    @printf "\n{{ blue }}=== Running Unit Tests ==={{ nc }}\n"
    uv run pytest -m "not integration and not exhaustive"
    @printf "{{ green }}✔ Unit tests passed{{ nc }}\n"

# Run the full automated testing matrix
test: sync
    @printf "\n{{ blue }}=== Running Tests ==={{ nc }}\n"
    uv run pytest
    @printf "{{ green }}✔ All tests passed{{ nc }}\n"

# Run tests with coverage
test-cov: sync
    @printf "\n{{ blue }}=== Running Tests with Coverage ==={{ nc }}\n"
    uv run pytest --cov
    @printf "{{ green }}✔ Coverage run complete{{ nc }}\n"

# Generate detailed coverage reports
test-cov-report: sync
    @printf "\n{{ blue }}=== Generating Coverage Reports ==={{ nc }}\n"
    uv run pytest --cov --cov-report=term-missing --cov-report=annotate:coverage_annotations/ | tee coverage_report.txt
    @printf "{{ green }}✔ Coverage reports generated{{ nc }}\n"

# Run quick Hyperfine benchmarks
test-benchmark: sync
    @printf "\n{{ blue }}=== Running Quick Hyperfine Benchmarks ==={{ nc }}\n"
    hyperfine --warmup 5 --runs 30 --export-json benchmark.json \
        '.venv/bin/protostar help init' \
        'PROTOSTAR_BENCHMARK_WIZARD=1 .venv/bin/protostar init'
    @printf "{{ green }}✔ Benchmark complete{{ nc }}\n"

# Run slower, more accurate Hyperfine benchmarks
test-benchmark-slower: sync
    @printf "\n{{ blue }}=== Running Full Hyperfine Benchmarks ==={{ nc }}\n"
    hyperfine --warmup 30 --runs 90 --export-json benchmark.json \
        '.venv/bin/protostar help init' \
        'PROTOSTAR_BENCHMARK_WIZARD=1 .venv/bin/protostar init'
    @printf "{{ green }}✔ Benchmark complete{{ nc }}\n"

# Run the fast local CI pipeline executed before pushing
ci: lint typecheck test-unit check-fixtures
    @printf "\n{{ green }}✔ Local CI pipeline completed successfully. Clear to push!{{ nc }}\n"

# Remove caches, artifacts, and temp files
clean:
    @printf "\n{{ blue }}=== Cleaning Workspace ==={{ nc }}\n"
    rm -rf \
        .pytest_cache \
        .mypy_cache \
        .ruff_cache \
        htmlcov \
        .coverage \
        coverage.xml \
        coverage_annotations \
        tmp_wizard \
        tmp_headless \
        tmp_gen \
        site \
        .benchmarks \
        .cache
    rm -f \
        benchmark.json \
        coverage_report.txt \
        lcov.info \
        coverage.lcov
    find . -type d -name "__pycache__" -exec rm -rf {} +
    @printf "{{ green }}✔ Workspace cleaned{{ nc }}\n"

# Generate ALL Markdown fixtures for documentation
docs-fixtures: sync
    @printf "\n{{ blue }}=== Generating All Documentation Fixtures ==={{ nc }}\n"
    uv run python scripts/generate_doc_fixtures.py
    @printf "{{ green }}✔ Documentation fixtures generated in docs/includes/{{ nc }}\n"

# Generate only the fast documentation fixtures
docs-fixtures-fast: sync
    @printf "\n{{ blue }}=== Generating Fast Documentation Fixtures ==={{ nc }}\n"
    uv run python scripts/generate_doc_fixtures.py --fast
    @printf "{{ green }}✔ Fast documentation fixtures generated in docs/includes/{{ nc }}\n"

# Check if documentation fixtures are out of sync with the codebase
check-fixtures: docs-fixtures
    @printf "\n{{ blue }}=== Checking Documentation Fixture Drift ==={{ nc }}\n"
    @git diff --exit-code docs/includes/ > /dev/null || (printf "{{ yellow }}⚠ Fixture drift detected. The generator modified files in docs/includes/. Please commit them.{{ nc }}\n" && exit 1)
    @printf "{{ green }}✔ Documentation fixtures are up-to-date{{ nc }}\n"

# Generate wizard demo
wizard-demo: sync
    @printf "\n{{ blue }}=== Generating Wizard Demo ==={{ nc }}\n"
    vhs demo/wizard.tape
    rm -rf tmp_wizard
    @printf "{{ green }}✔ Wizard demo generated{{ nc }}\n"

# Generate headless demo
headless-demo: sync
    @printf "\n{{ blue }}=== Generating Headless Demo ==={{ nc }}\n"
    vhs demo/headless_init.tape
    rm -rf tmp_headless
    @printf "{{ green }}✔ Headless demo generated{{ nc }}\n"

# Generate all demos
all-demo: wizard-demo headless-demo
    @printf "\n{{ blue }}=== All demos generated ==={{ nc }}\n"

# Start the documentation preview server
serve: sync
    @printf "\n{{ blue }}=== Launching Zensical Server ==={{ nc }}\n"
    uv run zensical serve -o

# Bump project version (part: major, minor, patch), sync lockfile, commit, tag, and atomic push
bump part: lint typecheck test-unit
    #!/usr/bin/env bash
    set -euo pipefail

    echo "Ensuring local repository is up to date..."
    git pull --ff-only

    echo "Checking for pre-existing uncommitted changes..."
    if [[ -n "$(git status --porcelain --untracked-files=no -- pyproject.toml uv.lock)" ]]; then
        echo "Error: pyproject.toml or uv.lock already has uncommitted changes. Commit or stash them first." >&2
        exit 1
    fi

    VERSION=$(uv run scripts/bump.py {{ part }})
    NEW_TAG="v$VERSION"

    echo "Checking tag $NEW_TAG does not already exist..."
    if git rev-parse "$NEW_TAG" >/dev/null 2>&1; then
        echo "Error: tag $NEW_TAG already exists." >&2
        git checkout -- pyproject.toml
        exit 1
    fi

    echo "Updating lockfile for $NEW_TAG..."
    uv sync

    echo "Staging changes and creating commit..."
    git add pyproject.toml uv.lock
    git commit -m "chore: bump version to $VERSION"
    git tag -a "$NEW_TAG" -m "Bump version to $NEW_TAG"

    echo "Shipping atomically to remote..."
    git push origin HEAD --tags
