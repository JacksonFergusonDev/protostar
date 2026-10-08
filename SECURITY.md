# Security Policy

## Supported Versions

Protostar is in active pre-1.0 development. Security updates are applied only to the `main` branch and the latest release tag. Previous releases do not receive backported security patches.

| Version | Supported |
| :--- | :--- |
| Latest (`main` / current release) | :white_check_mark: |
| Older releases | :x: |

## Reporting a Vulnerability

**Please do not report security vulnerabilities in public GitHub issues, discussions, or pull requests.**

Report all vulnerabilities privately through GitHub's [Private Vulnerability Reporting](https://github.com/JacksonFergusonDev/protostar/security/advisories/new).

When filing a report, please include:

- A clear description of the vulnerability and its potential impact.
- Step-by-step instructions or a minimal proof-of-concept (PoC) demonstrating how to reproduce the issue.
- Any relevant details regarding the environment, operating system, or flags used.

Reports will be acknowledged promptly and coordinated privately through GitHub Security Advisories before public disclosure.

## Scope & Threat Model

Protostar scaffolds, manages, and executes project lifecycles, and executes external shell commands and filesystem transactions on user projects.

### In-Scope

- **Path Traversal / Archive Slip:** Bypassing workspace boundaries (`enforce_path_jail`) or extracting archives that write outside the target workspace.
- **Trust Violations:** Running any command for an untrusted template (a `--from` path or URL, or an alias without `trusted = true`) on `init` or `sync` without listing it and requiring the user's confirmation. That covers Protostar's own commands, such as `uv add`, which run in files the template wrote, as well as the template's `system_tasks` and `post_install_tasks`.
- **Binary Safelist Escapes:** Bypassing subprocess execution boundaries (`enforce_binary_safelist`) during template execution.
- **Secret Scanning Bypasses:** Flaws or bypasses in credential detection that allow committed secret patterns past the variable safety net without `--allow-secret`.

### Out-of-Scope

- Vulnerabilities in third-party executables that Protostar coordinates (e.g., `uv`, `git`, `ruff`).
- Commands executed after a user has confirmed them, passed `--trust`, or configured a template alias with `trusted = true`.
- Attack vectors requiring full local administrative access or arbitrary code execution capabilities already present in the user's local shell.
