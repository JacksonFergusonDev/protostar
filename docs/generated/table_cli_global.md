| Flag | Shorthand | Description |
| :--- | :--- | :--- |
| `--json` | *None* | Position-independent flag. Emits structured JSON to `stdout` and redirects human-readable logging to `stderr`. |
| `--dry-run` | *None* | Executes the read-only `plan()` phase to preview planned files, AST merges, and system tasks without touching disk. |
| `--config <path>` | *None* | Reads global configuration from this file instead of the default location. Missing files are an error. |
| `--no-config` | *None* | Ignores global configuration entirely and runs on built-in defaults. |
| `--verbose` | `-v` | Enables debug-level logging and uncapped Python tracebacks for triage. |
| `--version` | *None* | Displays the installed Protostar version string. |
| `--help` | `-h` | Displays top-level help and available subcommands. |
