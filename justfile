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

# Run linters and check formatting (Ruff, Markdown, and GitHub Workflows)
lint: sync
    @printf "\n{{ blue }}=== Running Linters ==={{ nc }}\n"
    uv run ruff check .
    uv run ruff format --check .
    uv run rumdl check .
    uv run rumdl fmt --check .
    uv run actionlint .github/workflows/*.yml
    @printf "{{ green }}✔ Linting passed{{ nc }}\n"

# Run static type checking with Mypy
typecheck: sync
    @printf "\n{{ blue }}=== Running Type Checks ==={{ nc }}\n"
    uv run mypy .
    @printf "{{ green }}✔ Type checking passed{{ nc }}\n"

# Run the full automated testing matrix
test: sync
    @printf "\n{{ blue }}=== Running Tests ==={{ nc }}\n"
    uv run pytest -n auto --dist worksteal
    @printf "{{ green }}✔ All tests passed{{ nc }}\n"

# Fail init at every write and command of every template and seed, checking each rollback (nightly also raises every fault around real commands)
test-rollback: sync
    @printf "\n{{ blue }}=== Running Every Rollback Fault ==={{ nc }}\n"
    uv run pytest tests/test_rollback.py --rollback-scope full -n auto --dist worksteal
    @printf "{{ green }}✔ Every fault rolled back{{ nc }}\n"

# Run tests with coverage
test-cov: sync
    @printf "\n{{ blue }}=== Running Tests with Coverage ==={{ nc }}\n"
    uv run pytest -n auto --dist worksteal --cov
    @printf "{{ green }}✔ Coverage run complete{{ nc }}\n"

# Generate detailed coverage reports
test-cov-report: sync
    @printf "\n{{ blue }}=== Generating Coverage Reports ==={{ nc }}\n"
    uv run pytest -n auto --dist worksteal --cov --cov-report=term-missing --cov-report=annotate:coverage_annotations/ | tee coverage_report.txt
    @printf "{{ green }}✔ Coverage reports generated{{ nc }}\n"

# Time scenarios under the working tree, e.g. `just bench sync 'init-*'` (performance work only; see AGENTS.md)
bench *args: sync
    uv run python -m scripts.benchmarks run {{ args }}

# Compare the working tree with another version, e.g. `just bench-compare main sync`
bench-compare ref *args: sync
    uv run python -m scripts.benchmarks compare {{ ref }} {{ args }}

# Profile one scenario with pyinstrument, e.g. `just bench-profile sync` (writes .benchmarks/)
bench-profile scenario *args: sync
    uv run python -m scripts.benchmarks profile {{ scenario }} {{ args }}

# Run mutation testing on one module, e.g. `just mutate journal` (slow; the full set runs in the Mutation Testing workflow)
mutate module workers="2":
    @printf "\n{{ blue }}=== Mutation Testing: {{ module }} ==={{ nc }}\n"
    uv run --group mutation mutmut run --max-children {{ workers }} "protostar.{{ module }}.*"
    uv run python scripts/mutation_report.py report --json mutants/summary.json --survivors mutants/survivors.txt
    uv run --group mutation python scripts/mutation_report.py diffs --out mutants/survivors.md
    @printf "{{ green }}✔ Mutation run complete (what to fix: mutants/survivors.md){{ nc }}\n"

# Run the fast local CI pipeline executed before pushing
ci: lint typecheck test docs check-snapshots check-doc-links check-docs-drift check-schemas secrets
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
        tmp_interactive \
        tmp_headless \
        tmp_gen \
        site \
        .benchmarks \
        mutants \
        .cache
    rm -f \
        benchmark.json \
        coverage_report.txt \
        lcov.info \
        coverage.lcov
    find . -type d -name "__pycache__" -exec rm -rf {} +
    @printf "{{ green }}✔ Workspace cleaned{{ nc }}\n"

# Generate and verify scenario regression snapshots and documentation assets
check-snapshots: sync
    @printf "\n{{ blue }}=== Verifying Regression Snapshots & Documentation Assets ==={{ nc }}\n"
    uv run python scripts/run_snapshots.py

# Validate embedded documentation links and every tool's documentation URL
check-doc-links: sync
    @printf "\n{{ blue }}=== Validating Embedded Documentation Links ==={{ nc }}\n"
    uv run python scripts/check_doc_links.py
    @printf "{{ green }}✔ All embedded documentation links are valid{{ nc }}\n"

# Validate that hand-written documentation still agrees with the code
check-docs-drift: sync
    @printf "\n{{ blue }}=== Checking Documentation Against the Code ==={{ nc }}\n"
    uv run python scripts/check_docs_drift.py

# Validate repository and snapshot configurations against official schemas
check-schemas: sync
    @printf "\n{{ blue }}=== Validating JSON & YAML Schemas ==={{ nc }}\n"
    uv run python scripts/check_schemas.py

# Alias for check-schemas
schema-check: check-schemas

# Scan repository for hardcoded secrets with Gitleaks
secrets:
    @printf "\n{{ blue }}=== Scanning for Hardcoded Secrets ==={{ nc }}\n"
    uv run prek run gitleaks --all-files
    @printf "{{ green }}✔ No secrets detected{{ nc }}\n"

# Regenerate the secret-detection rules from the gitleaks tag pinned in _fallbacks.py
sync-secret-rules: sync
    @printf "\n{{ blue }}=== Regenerating Secret-Detection Rules ==={{ nc }}\n"
    uv run python scripts/sync_secret_rules.py

# Vendor the house-style release pinned in scripts/sync_house_style.py into docs/house/
sync-house-style: sync
    @printf "\n{{ blue }}=== Vendoring house-style ==={{ nc }}\n"
    uv run python scripts/sync_house_style.py

# Pre-warm environment and caches for demo generation
demo-prewarm: sync
    @printf "\n{{ blue }}=== Pre-warming Demo Environment & Caches ==={{ nc }}\n"
    @uv pip install --dry-run \
        numpy scipy pandas matplotlib astropy astroquery specutils nbdime \
        mypy pytest pytest-cov pytest-mock ruff rumdl typer rich commitizen prek zensical \
        --quiet 2>/dev/null || true
    @python3 -m compileall -q src/
    @uv run --with prek prek --config tests/snapshots/cli/pre-commit-config.fixture.yaml prepare-hooks 2>/dev/null || true
    @printf "{{ green }}✔ Demo environment warmed{{ nc }}\n"

# Helper recipe to record and render demo using asciinema + agg
_demo-run name target trials="5": demo-prewarm
    @printf "\n{{ blue }}=== Generating {{ name }} Demo (trials: {{ trials }}) ==={{ nc }}\n"
    rm -rf /tmp/demo_project && mkdir -p /tmp/demo_project
    PATH="{{ invocation_directory() }}/.venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$$PATH" \
        uv run python scripts/record_demos.py {{ target }} --trials {{ trials }} --output docs/assets/demo_{{ target }}.cast
    agg docs/assets/demo_{{ target }}.cast docs/assets/demo_{{ target }}.gif \
        --font-family "JetBrainsMono Nerd Font Mono" \
        --font-size 22 \
        --line-height 1.35
    rm -rf /tmp/demo_project
    @printf "{{ green }}✔ {{ name }} demo generated in docs/assets/demo_{{ target }}.gif{{ nc }}\n"

# Generate headless init demo (production, best of 5 trials)
demo-init-headless trials="5": (_demo-run "Init Headless" "init_headless" trials)

# Generate headless init demo draft (single trial)
demo-init-headless-draft: (_demo-run "Init Headless (Draft)" "init_headless" "1")

# Generate interactive init demo (production, best of 5 trials)
demo-init-interactive trials="5": (_demo-run "Init Interactive" "init_interactive" trials)

# Generate interactive init demo draft (single trial)
demo-init-interactive-draft: (_demo-run "Init Interactive (Draft)" "init_interactive" "1")

# Generate sync demo (production, best of 5 trials)
demo-sync trials="5": (_demo-run "Sync" "sync" trials)

# Generate sync demo draft (single trial)
demo-sync-draft: (_demo-run "Sync (Draft)" "sync" "1")

# Generate all demos (production, best of 5 trials)
demo-all trials="5": (demo-init-interactive trials) (demo-init-headless trials) (demo-sync trials)
    @printf "\n{{ blue }}=== All production demos generated ==={{ nc }}\n"

# Generate all demo drafts (single trial)
demo-all-draft: demo-init-interactive-draft demo-init-headless-draft demo-sync-draft
    @printf "\n{{ blue }}=== All demo drafts generated ==={{ nc }}\n"

# Re-render the docs' social share card (docs/assets/og-card.png)
og-card:
    @printf "\n{{ blue }}=== Rendering the share card ==={{ nc }}\n"
    uv run --with playwright python -m playwright install chromium
    uv run --with playwright python scripts/render_og_card.py

# Build documentation site in strict mode
docs: sync
    @printf "\n{{ blue }}=== Building Documentation ==={{ nc }}\n"
    uv run zensical build --strict
    @printf "{{ green }}✔ Documentation build complete{{ nc }}\n"

# Alias for docs
docs-build: docs

# Start the documentation preview server
serve: sync
    @printf "\n{{ blue }}=== Launching Zensical Server ==={{ nc }}\n"
    uv run zensical serve -o

# Preview the metrics dashboard on port 8765, separately from the docs server
serve-metrics port="8765":
    uv run python scripts/serve_metrics.py --port {{ port }}

# Refresh release inputs for review, then bump version, sync lockfile, commit, tag, and push
bump part:
    uv run python scripts/prepare_release.py
    uv run --refresh https://raw.githubusercontent.com/JacksonFergusonDev/ci-cd-release-infrastructure/refs/heads/main/scripts/release.py {{ part }}

# Drop into an empty isolated macOS sandbox shell
sandbox *args: (_sandbox "empty" args)

# Open an existing Python repository that has never used Protostar
sandbox-existing *args: (_sandbox "existing" args)

# Open a Protostar project whose local template has a pending update
sandbox-sync *args: (_sandbox "sync" args)

# Open a Protostar project whose template update conflicts with a local change
sandbox-sync-conflict *args: (_sandbox "sync-conflict" args)

# Build a local Protostar and prepare the requested sandbox scenario
_sandbox scenario *args: sync
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

    if [[ "{{ scenario }}" != "empty" ]]; then
        HOME="$MOCK_HOME" XDG_CONFIG_HOME="$MOCK_HOME/.config" \
            UV_CACHE_DIR="$HOST_UV_CACHE" PATH="$SANDBOX_VENV/bin:$PATH" \
            "$SANDBOX_VENV/bin/python" "$REPO_ROOT/scripts/prepare_sandbox.py" \
            "{{ scenario }}" "$WORKSPACE" --fixture "$SANDBOX_DIR/fixture"
    fi
    # A lifecycle scenario trusts its template in its own configuration
    if [[ -f "$SANDBOX_DIR/fixture/config.toml" ]]; then
        export PROTOSTAR_CONFIG="$SANDBOX_DIR/fixture/config.toml"
    fi

    cd "$WORKSPACE"

    # Evaluate the expanded just parameter directly
    RAW_ARGS="{{ args }}"

    if [[ -n "$RAW_ARGS" ]]; then
        # Single-command mode: run the specified arguments with mocked HOME, host UV cache, and overridden PATH
        HOME="$MOCK_HOME" XDG_CONFIG_HOME="$MOCK_HOME/.config" \
            UV_CACHE_DIR="$HOST_UV_CACHE" PATH="$SANDBOX_VENV/bin:$PATH" protostar {{ args }}
    else
        # Interactive shell mode: drop into sub-shell where 'protostar' points to the sandbox build
        printf "{{ blue }}Entering interactive sandbox shell (type 'exit' or Ctrl+D when done):{{ nc }}\n\n"
        HOME="$MOCK_HOME" XDG_CONFIG_HOME="$MOCK_HOME/.config" \
            UV_CACHE_DIR="$HOST_UV_CACHE" PATH="$SANDBOX_VENV/bin:$PATH" \
            PROTOSANDBOX=1 $SHELL -i || true
    fi

# Build the local test container with inspection CLI tools, runtime dependencies, and shell aliases
sandbox-linux-build:
    #!/usr/bin/env bash
    docker build -t protostar-test-harness - << 'EOF'
    FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
    ENV DEBIAN_FRONTEND=noninteractive
    COPY --from=node:22-bookworm-slim /usr/local/include/node /usr/local/include/node
    COPY --from=node:22-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
    COPY --from=node:22-bookworm-slim /usr/local/bin/node /usr/local/bin/node
    RUN ln -s /usr/local/bin/node /usr/local/bin/nodejs && \
        ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
        ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx && \
        apt-get update -qq && \
        apt-get install -qq -y \
            git \
            direnv \
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
                PROTOSANDBOX=1 bash --rcfile /root/.bashrc -i || true
            fi
        "
