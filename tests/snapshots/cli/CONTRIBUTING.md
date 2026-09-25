<!-- region: protostar b7a348d5 -->
# Contributing to demo-project

<!-- Protostar generates and updates this section from the project's tooling. Keep your own notes outside the surrounding Protostar markers. -->

Thank you for helping improve demo-project. This guide covers setting up a development environment and the checks every change passes.

## Development Setup

1. Install [uv](https://docs.astral.sh/uv/).
1. Clone your fork and run `uv sync` to create the environment with Python 3.13.
1. Run `uv run prek install` to install the git hooks.

Add dependencies with `uv add <package>`, or `uv add --dev <package>` for development tools, so `uv.lock` stays in sync.

## Commands

- `just format`: apply formatters and safe lint fixes.
- `just lint`: run the linters.
- `just typecheck`: run static type checks.
- `just test`: run the test suite.
- `just ci`: run lint, typecheck, test; the local check to pass before pushing.

## Git Hooks

prek runs the hooks in `.pre-commit-config.yaml` on every commit and runs the tests before every push. If a hook fails or rewrites a file, fix the cause, restage, and commit again.

## Commit Messages

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/), such as `feat: add an export command` or `fix: handle empty input`. Commitizen reads them to bump the version and write the changelog. The `commit-msg` hook rejects any other message.

## Pull Requests

1. For a larger change, open an issue first so the approach can be agreed before you start.
1. Keep each pull request focused on one change, with tests that cover it.
1. Make sure `just ci` passes before you push. CI runs the same checks on every pull request.
1. Fill in the pull request template.

## Conduct and Security

Everyone taking part in this project is expected to follow its code of conduct. Report security vulnerabilities privately, as the security policy describes, never in a public issue.
<!-- endregion: protostar b7a348d5 -->
