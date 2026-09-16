| Exit Code | POSIX Name | Exception Class | Trigger Condition |
| :--- | :--- | :--- | :--- |
| `0` | `EX_OK` | *None* | Successful execution |
| `1` | Generic Exit | `CommandExecutionError`<br>`CommandTimeoutError` | Subprocess failure or command timeout |
| `64` | `os.EX_USAGE` | `InvalidUsageError` | Invalid CLI arguments or command usage syntax |
| `65` | `os.EX_DATAERR` | `TemplateResolutionError` | Template resolution error (corrupted archive, missing variables) |
| `69` | `os.EX_UNAVAILABLE` | `MissingDependencyError`<br>`AggregatedDependencyError` | Missing required system binary (`uv`, `git`, etc.) |
| `70` | `os.EX_SOFTWARE` | `ConfigurationError`<br>`InvalidRollbackStateError` | Internal logic invariant breach, corrupt manifest, or failed rollback |
| `73` | `os.EX_CANTCREAT` | `WorkspaceCollisionError`<br>`UnsupportedFilesystemNodeError` | Target files exist, symlinks/special nodes encountered, or unwriteable disk |
| `130` | POSIX SIGINT | `KeyboardInterrupt` | Interactive execution cancelled by user (`Ctrl+C`) |
