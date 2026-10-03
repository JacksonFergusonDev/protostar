---
description: "A quick tour for people who know Python tooling: the recipe editor, a headless init, and what a new project contains."
icon: material/rocket
---

# Getting Started

## Installation

```bash
brew install jacksonfergusondev/tap/protostar   # macOS
uv tool install protostar                       # Linux and Windows
```

Protostar needs `uv` and `git`. [Installation](installation.md) covers both on each platform, for a machine with no Python setup. New to Python tooling? [Your First Project](first-project.md) walks through a project from start to finish.

`protostar init` sets up a project in the current directory, either in a terminal screen where you choose everything, or headlessly from flags.

## The Recipe Editor

Run `protostar init` with no arguments in an empty folder, or in a project you already have, and it opens the recipe editor: the template, its tier and options, every tool as a switch, and the project's details, with a live preview of the files it will write. `Ctrl+S` continues to the change review, which shows every file and command before anything runs. The keyboard does everything, and `?` lists the keys.

```bash
mkdir orbital-mechanics-sim
cd orbital-mechanics-sim
protostar init
```

<div class="hs-terminal">
  <div class="hs-terminal-bar">
    <div class="hs-terminal-dots" aria-hidden="true">
      <span class="dot dot-close"></span>
      <span class="dot dot-minimize"></span>
      <span class="dot dot-maximize"></span>
    </div>
    <span class="hs-terminal-title">protostar init</span>
  </div>
  <div class="hs-terminal-screen" data-asciinema="../assets/demo_init_interactive.cast">
    <noscript>
      <a href="../assets/demo_init_interactive.cast">Download the Protostar terminal recording</a>
    </noscript>
  </div>
</div>

## Headless Setup

Pass a template, and any tool flags, to skip the screens:

```bash
mkdir hyperdrive-cli
cd hyperdrive-cli
protostar init --template cli
```

It writes the files, runs `git init` and `uv init`, and installs the dependencies with uv, which takes as long as the downloads do. Add `--dry-run` first to see the plan without writing anything, and `--no-<tool>` to leave a tool out.

<div class="hs-terminal">
  <div class="hs-terminal-bar">
    <div class="hs-terminal-dots" aria-hidden="true">
      <span class="dot dot-close"></span>
      <span class="dot dot-minimize"></span>
      <span class="dot dot-maximize"></span>
    </div>
    <span class="hs-terminal-title">protostar init --template cli</span>
  </div>
  <div class="hs-terminal-screen" data-asciinema="../assets/demo_init_headless.cast">
    <noscript>
      <a href="../assets/demo_init_headless.cast">Download the Protostar terminal recording</a>
    </noscript>
  </div>
</div>

### What the Project Contains

The `cli` template starts in the production tier, so the project has the full quality gate:

- **A Typer and Rich command-line package** in `src/`, installable with Hatchling, with its console script in `[project.scripts]` and a test in `tests/`.
- **Tool settings in `pyproject.toml`:** Ruff, strict Mypy, pytest with coverage, and rumdl for Markdown.
- **Commit hooks** in `.pre-commit-config.yaml`, run by prek, with Commitizen checking each commit message and keeping `CHANGELOG.md`.
- **CI and releases:** GitHub Actions workflows that run the checks and publish to PyPI on a version tag, Renovate settings, and Codecov.
- **Documentation:** a Zensical site in `docs/`, ready for Read the Docs.
- **The files GitHub shows contributors:** `CONTRIBUTING.md`, a code of conduct, a security policy, and issue and pull request templates.
- **A `justfile`** with `just lint`, `just test`, and `just ci`, and an `.envrc` that activates the virtual environment through direnv.

??? abstract "Every file `protostar init --template cli` writes"
    ```text
    --8<-- "tree_cli.txt"
    ```

Two of those files make this a Protostar project rather than a copy of a template. `[tool.protostar]` in `pyproject.toml` is the **recipe**: what you asked for. `protostar.lock` records what Protostar wrote. Commit both, and when the template or Protostar improves, `protostar status` shows the update and `protostar sync` applies it without overwriting your edits. [How Protostar Tracks Your Files](usage/tracking.md) explains how.

## Getting Help

`protostar help` lists every command, and `protostar help <command>` shows one command's options. The [CLI Reference](usage/cli-reference.md) has the same, generated from the same source.

![Protostar Help](./assets/terminals/cli_help.svg)

## Shell Completion and an Alias

To speed up your workflow, you can enable CLI autocompletion and set up a shorter alias.

### 1. Enable Autocomplete

Protostar provides native dynamic completion script generation for **Zsh**, **Bash**, **Fish**, and **PowerShell** via `protostar completion`. No external packages or separate installations are required.

To guarantee zero impact on your terminal startup latency (0ms overhead), Protostar generates a static completion script that connects directly to the fast dynamic completer.

=== "Zsh (macOS / Linux)"
    Generate the static completion script and source it in `~/.zshrc`:

    ```bash
    protostar completion zsh > ~/.protostar-completion.zsh
    echo 'source ~/.protostar-completion.zsh' >> ~/.zshrc
    source ~/.zshrc
    ```

    !!! tip "Using Custom Completion Directories (`$fpath`)"
        If you manage completions via `~/.zsh/completions` and call `compinit`, you can save the file directly to your completions directory instead:
        ```bash
        protostar completion zsh > ~/.zsh/completions/_protostar
        ```

=== "Bash (Linux / macOS)"
    Generate the static completion script and source it in your bash profile (`~/.bashrc` on Linux, `~/.bash_profile` on macOS):

    ```bash
    protostar completion bash > ~/.protostar-completion.bash
    echo 'source ~/.protostar-completion.bash' >> ~/.bashrc
    source ~/.bashrc
    ```

=== "Fish (macOS / Linux)"
    Save the completion script to Fish's native completions directory for instant autoloading (no config edits required):

    ```fish
    mkdir -p ~/.config/fish/completions
    protostar completion fish > ~/.config/fish/completions/protostar.fish
    ```

=== "PowerShell (Windows / Cross-platform)"
    Save the completion script and source it in your PowerShell `$PROFILE`:

    ```powershell
    protostar completion powershell > "$HOME\protostar-completion.ps1"
    Add-Content -Path $PROFILE -Value '. "$HOME\protostar-completion.ps1"'
    . $PROFILE
    ```

    !!! tip "PowerShell Profile Setup"
        If your profile script does not exist yet, create it:
        ```powershell
        if (!(Test-Path -Path $PROFILE)) { New-Item -ItemType File -Path $PROFILE -Force }
        ```
        If script execution is restricted on Windows, allow signed local scripts by running:
        ```powershell
        Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
        ```

### 2. Set an Alias (Optional)

Because `proto` is a common namespace, Protostar does not commandeer it by default. If you want the keystroke savings, map it manually in your `~/.zshrc` or `~/.bashrc`:

```bash
alias proto="protostar"
```

## Next Steps

- **[Configuration](./usage/configuration.md):** Set your name, editor, Python version, and the tools new projects start with, once.
- **[Tooling & Flags Matrix](./usage/tooling-matrix.md):** Every tool, its flag, and the built-in templates.
- **[CLI Reference](./usage/cli-reference.md):** Comprehensive reference for all subcommands, global options, and POSIX exit codes.
- **[Troubleshooting & FAQ](./usage/troubleshooting.md):** Solutions for missing dependencies, workspace collisions, and IDE schema integration.
- **[Project Lifecycle](./usage/lifecycle.md):** Keep the project current with `status`, `diff`, and `sync`.
