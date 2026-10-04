```text
protostar init [options]
```

| Option | Description |
| :--- | :--- |
| `--dry-run` | Show the change review: every file, command, and decision, without writing a file or running a command. |
| `-t, --template NAME` | A built-in template or one of your aliases; --list-templates shows them. |
| `--list-templates` | List the built-in templates and your aliases. |
| `--one-shot` | Set up the project without recording a recipe or protostar.lock, so sync can't update it later. |
| `--from PATH` | A template file or directory, a repository on GitHub, GitLab, Bitbucket, Codeberg, or Sourcehut, or any HTTPS file or archive. |
| `--var NAME=VALUE` | Set a template variable; repeat for each. Values are saved to pyproject.toml, so never pass secrets. |
| `--option NAME=VALUE` | Choose a template option: true or false, or one of its choices; repeat for each. Choices are saved to pyproject.toml. |
| `--tier TIER` | Follow the template's workbench tier (lean: exploring and analyzing) or production tier (the full quality gate: building something to publish). Only for templates that declare tiers; the choice is saved to pyproject.toml. |
| `--allow-secret NAME` | Keep a variable's value even though it looks like a credential; repeat for each. |
| `--trust` | Run the commands an untrusted template needs without asking, for this run only. They are still listed. Never saved; to trust a template every time, configure it as an alias with trusted = true. |
| `--python-version VERSION` | The Python version the project targets, such as 3.13. Overrides your configuration. |
| `--force-merge` | Merge into files that already exist without asking: keep your values and add what's missing. |
| `--force-replace` | Replace files that already exist with Protostar's version, without asking. |
| `--resolve SELECTOR=CHOICE` | Settle conflicts by id, or every conflict in a file by path. CHOICE is local (keep yours), desired (take the update), or both (text lines only). Repeatable. |
