| Option | Description |
| :--- | :--- |
| `<source>` | A template directory, a template TOML file, or an HTTPS URL. Defaults to the current directory. |
| `--strict` | Fails on warnings as well as errors. |
| `--output-format <format>` | `text` (default) for people, or `github` for GitHub Actions annotations on each finding's file and line. Cannot be combined with `--json`. |
| `--json` | Emits the findings as a JSON payload with `status` `passed` or `failed`. |
