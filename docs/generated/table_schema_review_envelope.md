| Key | Type | Meaning |
| :--- | :--- | :--- |
| `api_version` | `2` | The machine protocol version. |
| `status` | `reviewed` | Always `reviewed`. |
| `pending` | `boolean` | Whether the project is out of date: files, directories, ownership, package work, or conflicts. Git hooks never count. |
| `check_passed` | `boolean` | Only from `sync --check`: whether nothing is pending. |
| `template` | `object` or `null` | The template's applied ref and what its repository offers; `null` for a built-in, local, or plain-URL template. |
| `review` | `object` | What the run does and what it asks. |
| `diffs` | array of `object` | A unified diff for each entry in `review.edits`. |
