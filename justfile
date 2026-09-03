set shell := ["bash", "-euc", "-o", "pipefail"]
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

# Auto-format Python and Markdown
format: sync
    @printf "\n{{ blue }}=== Formatting Code ==={{ nc }}\n"
    uv run ruff check --fix .
    uv run ruff format .
    uv run rumdl fmt .
    @printf "{{ green }}✔ Formatting complete{{ nc }}\n"

# Run linters and check formatting (Ruff and Markdown)
lint: sync
    @printf "\n{{ blue }}=== Running Linters ==={{ nc }}\n"
    uv run ruff check .
    uv run ruff format --check .
    uv run rumdl check .
    uv run rumdl fmt --check .
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
ci: lint typecheck test-unit check-fixtures check-doc-links
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
        tmp_demo \
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

# Generate and verify documentation fixtures are up-to-date
check-fixtures: sync
    @printf "\n{{ blue }}=== Generating All Documentation Fixtures ==={{ nc }}\n"
    uv run python scripts/generate_doc_fixtures.py
    @printf "{{ green }}✔ Documentation fixtures generated in docs/fixtures/{{ nc }}\n"
    @printf "\n{{ blue }}=== Checking Snapshot Drift ==={{ nc }}\n"
    @git diff --exit-code docs/fixtures/ > /dev/null || (printf "{{ yellow }}⚠ Snapshot drift detected. The generator modified files in docs/fixtures/. Review the diff and commit the changes.{{ nc }}\n" && exit 1)
    @printf "{{ green }}✔ Snapshots are up-to-date{{ nc }}\n"

# Validate that embedded documentation links in errors resolve to real files
check-doc-links: sync
    @printf "\n{{ blue }}=== Validating Embedded Documentation Links ==={{ nc }}\n"
    uv run python scripts/check_doc_links.py
    @printf "{{ green }}✔ All embedded documentation links are valid{{ nc }}\n"

# Pre-warm environment and caches for demo generation
prewarm-demo: sync
    @printf "\n{{ blue }}=== Pre-warming Demo Environment & Caches ==={{ nc }}\n"
    @uv pip install --dry-run \
        numpy scipy pandas matplotlib astropy astroquery photutils specutils nbdime \
        mypy pytest pytest-cov pytest-mock ruff rumdl typer rich commitizen prek zensical \
        --quiet 2>/dev/null || true
    @python3 -m compileall -q src/
    @uv run --with prek prek --config docs/fixtures/cli/pre-commit-config.fixture.yaml prepare-hooks 2>/dev/null || true
    @printf "{{ green }}✔ Demo environment warmed{{ nc }}\n"

# Helper recipe to record and render demo using asciinema + agg
_run-demo name target: prewarm-demo
    @printf "\n{{ blue }}=== Generating {{ name }} Demo ==={{ nc }}\n"
    rm -rf /tmp/demo_project && mkdir -p /tmp/demo_project
    PATH="{{ invocation_directory() }}/.venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$$PATH" \
        uv run python scripts/record_demos.py {{ target }} --output docs/assets/demo_{{ target }}.cast
    agg docs/assets/demo_{{ target }}.cast docs/assets/demo_{{ target }}.gif \
        --font-family "JetBrainsMono Nerd Font Mono" \
        --font-size 22 \
        --line-height 1.35 \
        --theme 1e1e2e,cdd6f4,181825,f38ba8,a6e3a1,f9e2af,89b4fa,f5c2e7,94e2d5,bac2de,585b70,f38ba8,a6e3a1,f9e2af,89b4fa,f5c2e7,94e2d5,a6adc8
    rm -rf /tmp/demo_project
    @printf "{{ green }}✔ {{ name }} demo generated in docs/assets/demo_{{ target }}.gif{{ nc }}\n"

# Generate wizard demo
wizard-demo: (_run-demo "Wizard" "wizard")

# Generate headless demo
headless-demo: (_run-demo "Headless" "headless")

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

    echo "Syncing registry fallbacks..."
    uv run python scripts/sync_registry_fallbacks.py

    echo "Ensuring local repository is up to date..."
    git pull --ff-only

    echo "Checking for pre-existing uncommitted changes..."
    if [[ -n "$(git status --porcelain --untracked-files=no -- pyproject.toml uv.lock)" ]]; then
        echo "Error: pyproject.toml or uv.lock already has uncommitted changes. Commit or stash them first." >&2
        exit 1
    fi

    VERSION=$(uv run https://raw.githubusercontent.com/JacksonFergusonDev/ci-cd-tooling/refs/heads/main/scripts/bump.py {{ part }})
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

# Drop into an isolated macOS sandbox shell with a freshly built local Protostar on $PATH
sandbox *args: sync
    #!/usr/bin/env bash
    set -euo pipefail

    REPO_ROOT="{{ invocation_directory() }}"
    SANDBOX_DIR="$(mktemp -d /tmp/proto-macos-XXXXXX)"
    MOCK_HOME="$SANDBOX_DIR/home"
    WORKSPACE="$SANDBOX_DIR/workspace"
    SANDBOX_VENV="$SANDBOX_DIR/venv"
    HOST_UV_CACHE="${UV_CACHE_DIR:-$HOME/Library/Caches/uv}"

    mkdir -p "$MOCK_HOME" "$WORKSPACE"

    cleanup() {
        printf "\n{{ yellow }}Cleaning up macOS sandbox...{{ nc }}\n"
        rm -rf "$SANDBOX_DIR"
        printf "{{ green }}✔ Sandbox wiped.{{ nc }}\n"
    }
    trap cleanup EXIT INT TERM

    printf "\n{{ blue }}=== Building Fresh Protostar Sandbox Environment ==={{ nc }}\n"

    # 1. Build sandbox venv with local Protostar
    uv venv "$SANDBOX_VENV" --quiet
    UV_CACHE_DIR="$HOST_UV_CACHE" VIRTUAL_ENV="$SANDBOX_VENV" uv pip install \
        --reinstall-package protostar \
        -e "$REPO_ROOT" --quiet

    printf "{{ green }}✔ Protostar built fresh from local source tree{{ nc }}\n"
    printf "{{ yellow }}Mocked HOME:{{ nc }} %s\n" "$MOCK_HOME"
    printf "{{ yellow }}Workspace:  {{ nc }} %s\n" "$WORKSPACE"
    printf "{{ yellow }}Binary:     {{ nc }} %s\n\n" "$SANDBOX_VENV/bin/protostar"

    cd "$WORKSPACE"

    # Evaluate the expanded just parameter directly
    RAW_ARGS="{{ args }}"

    if [[ -n "$RAW_ARGS" ]]; then
        # Single-command mode: run the specified arguments with mocked HOME, host UV cache, and overridden PATH
        HOME="$MOCK_HOME" UV_CACHE_DIR="$HOST_UV_CACHE" PATH="$SANDBOX_VENV/bin:$PATH" protostar {{ args }}
    else
        # Interactive shell mode: drop into sub-shell where 'protostar' points to the sandbox build
        printf "{{ blue }}Entering interactive sandbox shell (type 'exit' or Ctrl+D when done):{{ nc }}\n\n"
        HOME="$MOCK_HOME" UV_CACHE_DIR="$HOST_UV_CACHE" PATH="$SANDBOX_VENV/bin:$PATH" PROTOSANDBOX=1 $SHELL -i
    fi

# Build the local test container with inspection CLI tools, runtime dependencies, and shell aliases
sandbox-linux-build:
    #!/usr/bin/env bash
    docker build -t protostar-test-harness - << 'EOF'
    FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
    ENV DEBIAN_FRONTEND=noninteractive
    RUN apt-get update -qq && \
        apt-get install -qq -y \
            git \
            direnv \
            nodejs \
            npm \
            curl \
            bat \
            ripgrep \
            fd-find \
            nano && \
            npm install -g markdownlint-cli2 && \
            ln -s /usr/bin/batcat /usr/local/bin/bat && \
            ln -s /usr/bin/fdfind /usr/local/bin/fd && \
            # Install eza binary dynamically for current architecture
            ARCH=$(uname -m) && \
            curl -sL "https://github.com/eza-community/eza/releases/latest/download/eza_${ARCH}-unknown-linux-gnu.tar.gz" | tar xz -C /usr/local/bin && \
            chmod +x /usr/local/bin/eza && \
            apt-get clean && rm -rf /var/lib/apt/lists/*

    # Bake native zshrc-style eza aliases into bashrc
    RUN echo 'alias ls="eza --icons --git"' >> /root/.bashrc && \
        echo 'alias ll="eza -l --icons --git"' >> /root/.bashrc && \
        echo 'alias la="eza -la --icons"' >> /root/.bashrc && \
        echo 'alias lt="eza --tree --git-ignore --all --icons"' >> /root/.bashrc && \
        echo 'alias lt2="eza --tree --git-ignore --all --icons --level=2"' >> /root/.bashrc && \
        echo 'alias lt3="eza --tree --git-ignore --all --icons --level=3"' >> /root/.bashrc && \
        echo 'alias lts="eza --tree --git -l --no-permissions --no-user --git-ignore --all --icons"' >> /root/.bashrc && \
        echo 'alias lts2="eza --tree --git -l --no-permissions --no-user --git-ignore --all --icons --level=2"' >> /root/.bashrc && \
        echo 'alias lts3="eza --tree --git -l --no-permissions --no-user --git-ignore --all --icons --level=3"' >> /root/.bashrc

    WORKDIR /workspace
    EOF

# Run Protostar inside an isolated Linux container with a clean build
sandbox-linux *args: sync
    #!/usr/bin/env bash
    set -euo pipefail

    REPO_ROOT="{{ invocation_directory() }}"

    # Start OrbStack background daemon if it isn't running
    if ! docker info >/dev/null 2>&1; then
        printf "{{ yellow }}Starting OrbStack background engine...{{ nc }}\n"
        open -a OrbStack --background
        until docker info >/dev/null 2>&1; do sleep 0.2; done
    fi

    if ! docker image inspect protostar-test-harness >/dev/null 2>&1; then
        printf "{{ yellow }}Building protostar-test-harness base image...{{ nc }}\n"
        just sandbox-linux-build
    fi

    printf "\n{{ blue }}=== Running in Isolated Linux Sandbox ==={{ nc }}\n"

    RAW_ARGS="{{ args }}"

    docker run --rm -it \
        -v "$REPO_ROOT:/protostar:ro" \
        -v protostar-uv-cache:/root/.cache/uv \
        -w /workspace \
        protostar-test-harness \
        bash -c "
            # 1. Create a dedicated container virtualenv and install local protostar
            uv venv /tmp/venv --quiet
            VIRTUAL_ENV=/tmp/venv uv pip install --reinstall-package protostar -e /protostar --quiet
            export PATH=\"/tmp/venv/bin:\$PATH\"

            # 2. Single-command vs interactive shell
            if [ -n \"$RAW_ARGS\" ]; then
                protostar $RAW_ARGS
            else
                printf '{{ blue }}Entering interactive Linux sandbox shell (type \"exit\" or Ctrl+D when done):{{ nc }}\n\n'
                PROTOSANDBOX=1 bash --rcfile /root/.bashrc -i
            fi
        "
