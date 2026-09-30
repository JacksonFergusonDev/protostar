| Key | Type | Meaning |
| :--- | :--- | :--- |
| `edits` | array of `object` | Every file the run writes or removes. |
| `directories` | array of `string` | Directories the run creates, as POSIX paths. |
| `migrations` | array of `object` | What each template migration does to one file. |
| `conflicts` | array of `object` | Open conflicts. Your version stays until each is resolved. |
| `resolved` | array of `object` | Conflicts settled by `--resolve`, each with the choice made. |
| `proposals` | array of `object` | Changes into content Protostar never owned. Each applies unless resolved with `local`. |
| `preserved` | array of `object` | Your edits and deletions that stay under an unchanged update. Resolving one with `desired` takes Protostar's version there. |
| `state_changed` | `boolean` | Whether the ownership records must advance. |
| `resolver` | `object` | The package work uv does; its output is never simulated. |
| `initialization_only` | array of array of `string` | Commands only `init` runs, such as `git init`; `sync` never runs them again. |
| `initialization_only_ide_probe` | `boolean` | Whether `init` also checks your IDE for the extensions the tools recommend. |
| `hooks` | `object` | What `sync` does to this clone's git hooks. They never count as pending. |
| `missing_tools` | array of `object` | Executables a selected tool runs that `PATH` lacks. The steps that run them are skipped. |
| `selections` | array of `object` | Which tools are on, and which layer decided each. |
| `producers` | array of `object` | Which module declared each part of the plan. |
