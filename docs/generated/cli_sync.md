```text
protostar sync [options]
```

| Option | Description |
| :--- | :--- |
| `--resolve SELECTOR=CHOICE` | Settle conflicts by id, or every conflict in a file by path. CHOICE is local (keep yours), desired (take the update), or both (text lines only). Repeatable. |
| `--to REF` | Move a repository template to a tag, branch, or full commit SHA, or to the newest release with 'latest'. Records the ref in pyproject.toml. |
| `--var NAME=VALUE` | Set a template variable, such as one a new template version adds; repeat for each. Values are saved to pyproject.toml, so never pass secrets. |
| `--option NAME=VALUE` | Choose a template option: true or false, or one of its choices; repeat for each. Choices are saved to pyproject.toml. |
| `--tier TIER` | Follow the template's workbench tier (lean: exploring and analyzing) or production tier (the full quality gate: building something to publish). Only for templates that declare tiers; the choice is saved to pyproject.toml. |
| `--allow-secret NAME` | Keep a variable's value even though it looks like a credential; repeat for each. |
| `--trust` | Run the commands an untrusted template needs without asking, for this run only. They are still listed. Never saved; to trust a template every time, configure it as an alias with trusted = true. |
| `--dry-run` | Show the changes sync would make, without writing a file or running a command. |
| `--check` | Exit 1 when the project is behind its recipe or has an open conflict. Writes nothing, and edits you kept don't fail it. |
