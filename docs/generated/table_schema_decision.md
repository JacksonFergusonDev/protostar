| Present in | Key | Type | Meaning |
| :--- | :--- | :--- | :--- |
| all four | `id` | `string` | Names this decision in `--resolve`. It covers the content, so it changes when the files do. |
| all four | `file` | `string` | The file the decision is in, as a POSIX path. |
| all four | `keys` | array of `string` | The key path inside a structured file; empty for a text file or a whole file. |
| all four | `identity` | `string` or `null` | The record it is in when the keys name a list of records, such as a hook; otherwise `null`. |
| all four | `lines` | `object` or `null` | The lines of a text file, numbered as in a unified diff hunk header; `null` for a structured file. |
| all four | `reason` | one of the values below | Why it is a decision. Each value below says what it means. |
| all four | `choices` | array of `local`, `desired`, `both` | The choices that settle it: `local` keeps your version, `desired` takes the update, and `both` keeps both sides of a text hunk. |
| all four | `sides` | `object` or `null` | What each side holds there; `null` when only a person can settle it. |
| `resolved` | `resolution` | `local`, `desired`, `both` | The choice that settled it. |
| `proposals` | `resolution` | `local`, `desired`, `both` or `null` | The choice made; `null` while it applies. |
| `preserved` | `deleted` | `boolean` | Whether what you kept is a deletion. |
