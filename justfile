set shell := ["bash", "-uc"]
set unstable := true
set quiet

# --- ANSI Colors ---

blue := '\033[1;34m'
green := '\033[1;32m'
yellow := '\033[1;33m'
nc := '\033[0m'

# Show available commands
default:
    @just --list

# Install dependencies using uv
install:
    @printf "\n{{ blue }}=== Installing Dependencies ==={{ nc }}\n"
    uv sync --all-extras --dev
    @printf "{{ green }}✔ Dependencies installed{{ nc }}\n"

# Auto-format Python code using Ruff
format:
    @printf "\n{{ blue }}=== Formatting Code ==={{ nc }}\n"
    uv run ruff check --fix .
    uv run ruff format .
    @printf "{{ green }}✔ Formatting complete{{ nc }}\n"

# Run linters (Ruff and Markdown)
lint:
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
typecheck:
    @printf "\n{{ blue }}=== Running Type Checks ==={{ nc }}\n"
    uv run mypy .
    @printf "{{ green }}✔ Type checking passed{{ nc }}\n"

# Run the full automated testing matrix
test:
    @printf "\n{{ blue }}=== Running Tests ==={{ nc }}\n"
    uv run pytest
    @printf "{{ green }}✔ All tests passed{{ nc }}\n"

# Run tests with coverage
test-cov:
    @printf "\n{{ blue }}=== Running Tests with Coverage ==={{ nc }}\n"
    uv run pytest --cov
    @printf "{{ green }}✔ Coverage run complete{{ nc }}\n"

# Generate detailed coverage reports
test-cov-report:
    @printf "\n{{ blue }}=== Generating Coverage Reports ==={{ nc }}\n"
    uv run pytest --cov --cov-report=term-missing --cov-report=annotate:coverage_annotations/ | tee coverage_report.txt
    @printf "{{ green }}✔ Coverage reports generated{{ nc }}\n"

# Run quick Hyperfine benchmarks
test-benchmark:
    @printf "\n{{ blue }}=== Running Quick Hyperfine Benchmarks ==={{ nc }}\n"
    hyperfine --warmup 5 --runs 30 --export-json benchmark.json \
        '.venv/bin/protostar help init' \
        'PROTOSTAR_BENCHMARK_WIZARD=1 .venv/bin/protostar init'
    @printf "{{ green }}✔ Benchmark complete{{ nc }}\n"

# Run slower, more accurate Hyperfine benchmarks
test-benchmark-slower:
    @printf "\n{{ blue }}=== Running Full Hyperfine Benchmarks ==={{ nc }}\n"
    hyperfine --warmup 30 --runs 90 --export-json benchmark.json \
        '.venv/bin/protostar help init' \
        'PROTOSTAR_BENCHMARK_WIZARD=1 .venv/bin/protostar init'
    @printf "{{ green }}✔ Benchmark complete{{ nc }}\n"

# Run the exact pipeline executed by GitHub Actions
ci: install lint typecheck test-cov
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

# Generate Markdown fixtures for documentation examples
docs-fixtures:
    @printf "\n{{ blue }}=== Generating Documentation Fixtures ==={{ nc }}\n"
    uv run python scripts/generate_doc_fixtures.py
    @printf "{{ green }}✔ Documentation fixtures generated in docs/includes/{{ nc }}\n"

# Generate wizard demo
wizard-demo:
    @printf "\n{{ blue }}=== Generating Wizard Demo ==={{ nc }}\n"
    vhs demo/wizard.tape
    rm -rf tmp_wizard
    @printf "{{ green }}✔ Wizard demo generated{{ nc }}\n"

# Generate headless demo
headless-demo:
    @printf "\n{{ blue }}=== Generating Headless Demo ==={{ nc }}\n"
    vhs demo/headless_init.tape
    rm -rf tmp_headless
    @printf "{{ green }}✔ Headless demo generated{{ nc }}\n"

# Generate generation demo
gen-demo:
    @printf "\n{{ blue }}=== Generating Generation Demo ==={{ nc }}\n"
    vhs demo/generate.tape
    rm -rf tmp_gen
    @printf "{{ green }}✔ Generation demo generated{{ nc }}\n"

# Generate all demos
all-demo: wizard-demo headless-demo gen-demo
    @printf "\n{{ blue }}=== All demos generated ==={{ nc }}\n"

# Start the documentation preview server
serve:
    @printf "\n{{ blue }}=== Launching Zensical Server ==={{ nc }}\n"
    uv run zensical serve -o
