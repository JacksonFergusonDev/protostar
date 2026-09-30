| Key | Type | Meaning |
| :--- | :--- | :--- |
| `api_version` | `2` | The machine protocol version. |
| `status` | `success`, `partial` | `success` when nothing is left to settle; `partial` when safe updates were committed but conflicts remain. |
| `template` | `object` or `null` | The template's applied ref and what its repository offers; `null` for a built-in, local, or plain-URL template. |
| `review` | `object` | What the run did and what it asks. |
| `install_commands` | array of `string` | The commands that install the missing tools, in order; only when a package manager was found. |
| `result` | `object` | What the run wrote. |
