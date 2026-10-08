| Exit Code | Name | Error | When |
| :--- | :--- | :--- | :--- |
| `0` | `EX_OK` | *None* | The command succeeded |
| `1` | General failure | `CommandExecutionError`<br>`CommandTimeoutError` | A command Protostar ran failed or timed out, or `sync --check` found the project out of step |
| `64` | `EX_USAGE` | `InvalidUsageError` | The command line is invalid |
| `65` | `EX_DATAERR` | `TemplateResolutionError` | The template can't be read, such as a corrupted archive or a missing variable |
| `69` | `EX_UNAVAILABLE` | `MissingDependencyError` | `uv` or `git` isn't installed |
| `70` | `EX_SOFTWARE` | *(Unhandled exception)* | A bug in Protostar; it prints a link to report it |
| `74` | `EX_IOERR` | `FileSystemError` | A file couldn't be read or written, or permission was denied |
| `75` | `EX_TEMPFAIL` | `NetworkFetchError` | A remote template couldn't be downloaded; retrying may work |
| `77` | `EX_NOPERM` | `SecurityViolationError` | A safety check refused the run, such as a path that escapes the project or a variable value that looks like a credential |
| `78` | `EX_CONFIG` | `ConfigurationError` | Invalid TOML, or settings that contradict each other |
| `130` | Interrupted (128 + `SIGINT`) | `ExecutionAbortedError`<br>`ExecutionInterruptedError` | You cancelled setup or pressed Ctrl+C |
