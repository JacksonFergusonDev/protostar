| Code | POSIX Name | Trigger Condition |
| :--- | :--- | :--- |
| `0` | `EX_OK` | Successful execution |
| `1` | Generic | Subprocess failure or command timeout |
| `64` | `os.EX_USAGE` | Invalid CLI arguments or command usage syntax |
| `65` | `os.EX_DATAERR` | Template resolution error (corrupted archive, missing variables) |
| `69` | `os.EX_UNAVAILABLE` | Missing required system binary (`uv`, `git`, etc.) |
| `70` | `os.EX_SOFTWARE` | Unhandled internal Python bug (prompts automated bug report) |
| `74` | `os.EX_IOERR` | Local filesystem read/write or permission failure |
| `75` | `os.EX_TEMPFAIL` | Transient network failure during remote template download |
| `77` | `os.EX_NOPERM` | Security violation (e.g., path traversal Zip Slip) |
| `78` | `os.EX_CONFIG` | Invalid TOML syntax or conflicting CLI configuration |
| `130` | Shell Signal | You aborted interactive wizard prompt (Ctrl+C) |
