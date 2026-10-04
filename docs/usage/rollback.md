---
description: "What Protostar restores when a run fails or you press Ctrl+C, what it can't, and what to do if a restore fails."
---

# Automatic Rollback

If `protostar init` or `protostar sync` fails part-way, or you press `Ctrl+C`, Protostar puts back every file it changed, byte for byte, before it exits. A run either finishes or leaves the project as it found it.

This page is the one statement of what rollback covers; other pages link here.

## When Rollback Happens

Rollback starts on any failure after Protostar begins changing the project:

- A command fails or runs out of time, such as `uv add` failing to resolve a package.
- Something unexpected goes wrong, such as a file that can't be written.
- You press `Ctrl+C`.

Before restoring anything, Protostar stops the command that was running, along with every process it started, so nothing is still writing while the files go back. The error that follows says what failed and whether everything was restored.

Previews never need it: `--dry-run`, `status`, `diff`, and `sync --check` change nothing.

## What Gets Restored

Protostar records each path's original state before it first changes it, and restores that state:

- **Files it changed** go back to their exact original bytes and permissions, including a `pyproject.toml` it merged into.
- **Files it created** are removed.
- **Directories it created** are removed when they are empty again.
- **`pyproject.toml` and `uv.lock`** are recorded before `uv add` or `uv lock` runs, so a failed install leaves both as they were.
- **What its own commands create** is removed: the `.git/` directory `git init` makes, and the `pyproject.toml` and `.python-version` from `uv init`. Each command declares these in advance.
- **`protostar.lock` and the recipe** go back with everything else, so the record never claims a change that was undone.

## What Might Remain

Protostar only restores what it recorded, and never guesses what else a command wrote:

- **The virtual environment and caches.** `.venv`, uv's package cache, and other tools' caches can keep what was installed before the failure. They are rebuilt on the next run, and nothing in the project depends on them.
- **What a template's own commands write.** A template's `system_tasks` and `post_install_tasks` can't declare their outputs, so a file one of them created outside the paths above stays behind.

## When a Restore Fails (`RollbackFailedError`)

Rarely, a path can't be put back, and Protostar raises `RollbackFailedError` listing each one. The usual causes:

- **A directory it created now holds other files,** dropped there by an editor or another program during the run. Protostar never deletes files it didn't create, so it leaves the directory.
- **Permissions changed during the run,** so the original bytes can't be written back.

Look at each listed path, remove or restore it by hand, and run the command again.

## Interrupting with Ctrl+C (`ExecutionInterruptedError`)

`Ctrl+C` during a run starts rollback at once. A second `Ctrl+C` can't interrupt the restore halfway. When it finishes, Protostar raises `ExecutionInterruptedError` and exits with code `130`, meaning the run was cancelled and every change was undone, so you can run the command again.

## Symbolic Links and Special Files (`UnsupportedFilesystemNodeError`)

If a path Protostar would change is a symbolic link, a FIFO, a socket, or a device, it stops with `UnsupportedFilesystemNodeError` before touching it, because it can't safely record or restore it. Replace the link with a regular file or directory, and run the command again.

## Related Pages

- **[Rollback Internals](../mechanics/rollback.md):** How the journal, the transactional filesystem, and process termination work, for contributors.
- **[Error Handling Architecture](../mechanics/error_handling.md):** Every error and its exit code.
- **[Troubleshooting & FAQ](./troubleshooting.md):** Fixes for the problems people run into most.
