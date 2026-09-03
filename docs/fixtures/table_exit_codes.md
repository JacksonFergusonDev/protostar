| Exit Code | POSIX Name | Exception Class | Trigger Condition |
| :--- | :--- | :--- | :--- |
| `0` | `EX_OK` | *None* | Successful execution |
| `1` | Generic Exit | `CommandExecutionError`<br>`CommandTimeoutError` | Subprocess failure or command timeout |
| `64` | `os.EX_USAGE` | `InvalidUsageError` | Invalid CLI arguments or command usage syntax |
| `65` | `os.EX_DATAERR` | `TemplateResolutionError` | Template resolution error (corrupted archive, missing variables) |
| `69` | `os.EX_UNAVAILABLE` | `MissingDependencyError` | Missing required system binary (`uv`, `git`, etc.) |
| `70` | `os.EX_SOFTWARE` | *(Unhandled exception)* | Unhandled internal Python bug (prompts automated bug report) |
| `74` | `os.EX_IOERR` | `FileSystemError` | Local filesystem read/write or permission failure |
| `75` | `os.EX_TEMPFAIL` | `NetworkFetchError` | Transient network failure during remote template download |
| `77` | `os.EX_NOPERM` | `SecurityViolationError` | Security violation (e.g., path traversal Zip Slip) |
| `78` | `os.EX_CONFIG` | `ConfigurationError` | Invalid TOML syntax or conflicting CLI configuration |
| `130` | Shell Signal | `ExecutionAbortedError` | You aborted interactive wizard prompt (Ctrl+C) |
