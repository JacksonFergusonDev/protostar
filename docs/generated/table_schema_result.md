| Key | Type | Meaning |
| :--- | :--- | :--- |
| `created_paths` | array of `string` | Paths the run created. |
| `mutated_paths` | array of `string` | Paths that existed and the run changed. |
| `touched_paths` | array of `string` | Every created or mutated path. |
| `diagnostics` | array of `object` | Non-fatal notes from the run. |
| `missing_tools` | array of `object` | Executables a selected tool runs that `PATH` lacks. The steps that run them are skipped. |
