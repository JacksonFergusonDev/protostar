---
description: "Install Protostar, uv, and git on macOS, Linux, or Windows, starting from nothing."
icon: material/download
---

# Installation

Protostar needs two programs beside itself, and checks for both before it does anything:

- **[uv](https://docs.astral.sh/uv/)** installs Python and your project's packages. You don't need Python installed first: uv downloads the version a project asks for.
- **[git](https://git-scm.com/)** records the history of your project's files. Protostar starts a git repository in every project.

Pick your platform below. Each path is the one we recommend for someone with no Python setup, and says which of the two programs it installs for you.

=== "macOS"

    Use [Homebrew](https://brew.sh/), the usual package manager on macOS. If `brew --version` says the command isn't found, install Homebrew first with the command on its home page. Its installer also installs Apple's Command Line Tools, which include git.

    ```bash
    brew install jacksonfergusondev/tap/protostar
    ```

    **You get:** Protostar, uv, and git. Homebrew installs uv and git with Protostar, so there is nothing else to install.

=== "Linux"

    Install git and curl with your system's package manager, then uv with its official installer, then Protostar with uv. On Debian or Ubuntu:

    ```bash
    sudo apt install git curl
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

    On Fedora, use `sudo dnf install git curl` for the first line; on Arch, `sudo pacman -S git curl`. Open a new terminal so it finds `uv`, then:

    ```bash
    uv tool install protostar
    ```

    **You get:** Protostar. You install uv and git yourself, in the first two commands.

=== "Windows"

    Use winget, which comes with Windows 10 and 11, in PowerShell or Windows Terminal:

    ```powershell
    winget install --exact --id astral-sh.uv
    winget install --exact --id Git.Git
    ```

    Close the terminal and open a new one so it finds `uv` and `git`, then:

    ```powershell
    uv tool install protostar
    ```

    **You get:** Protostar. You install uv and git yourself, in the first two commands.

Check that all three are found:

```bash
protostar --version
uv --version
git --version
```

If `protostar` isn't found after `uv tool install`, run `uv tool update-shell` and open a new terminal: it adds the folder uv installs programs into to your `PATH`, the list of folders your terminal searches for commands.

!!! note "Installing with pip"
    If you manage your own Python environments and want Protostar inside one, `pip install protostar` works. pip installs neither uv nor git, and brings in `textual` for the recipe editor, which can conflict with other tools in the same environment that pin `textual` or `rich`. The paths above install Protostar in its own isolated environment instead.

## Tools a Project May Use

Some of the tools Protostar sets up are separate programs: [direnv](https://direnv.net/), which activates a project's environment when you `cd` into it, and [just](https://just.systems/), which runs the project's commands by short names. You don't need to install them now. Protostar never stops for them: a project that uses one is set up completely, and the output ends with the one command that installs whatever is missing. See [Tool Binaries](usage/troubleshooting.md#tool-binaries-direnv-just) for each platform.

## Updating

Update the same way you installed:

=== "macOS"

    ```bash
    brew upgrade protostar
    ```

=== "Linux and Windows"

    ```bash
    uv tool upgrade protostar
    ```

## Next Steps

- **[Your First Project<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](first-project.md):** Create a project, run it, change it, and check it, one step at a time.
- **[Getting Started<span class="hs-icon hs-icon-arrow-right" aria-hidden="true"></span>](getting-started.md):** A faster tour for people who already know Python tooling.
