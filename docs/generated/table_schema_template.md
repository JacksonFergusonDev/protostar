| Key | Type | Meaning |
| :--- | :--- | :--- |
| `ref` | `string` | The tag, branch, or commit applied. |
| `revision` | `string` | The commit the ref names. |
| `kind` | `null`, `tag`, `branch`, `commit` | What the ref is; `null` when the repository no longer has it. |
| `newer` | `string` or `null` | The newest release, when there is one; move to it with `sync --to`. |
| `moved` | `string` or `null` | The commit a tag or branch names now, when it moved. |
| `reachable` | `boolean` | Whether the repository could be reached. |
