# Global Configuration

Your global configuration file acts as the singular source of truth for environment initialization. Open it in your system's default `$EDITOR` by running:

```bash
protostar config
```

To restore your configuration to the factory defaults:

```bash
protostar config --reset
```

To bypass the confirmation prompt (e.g., in automated scripts), append `--force`:

```bash
protostar config --reset --force
```

---

## The Default Baseline

When you first run `protostar config` a configuration file is created and opened at `~/.config/protostar/config.toml`:

```toml
--8<-- "default_config.toml"
```

---

## Configuration Reference

### Environment Settings (`[env]`)

Controls base environment toggles and global tool preferences applied whenever `protostar init` is executed:

- `ide`: Preferred IDE (`"vscode"`, `"cursor"`, or `"none"`).
- `python_version`: Default Python version to pin (e.g., `"3.13"`).
- `supported_os`: Operating systems matrix for CI workflows (e.g., `["MacOS", "Linux", "Windows"]`).
- `direnv`: Auto-scaffold `.envrc` shell bindings.
- Tooling toggles (`ruff`, `mypy`, `ty`, `pyrefly`, `pytest`, `pre_commit`, `prek`, `commitizen`, `renovate`, `codecov`, `zensical`, `readthedocs`, `ci`, `release`, `just`, `markdownlint`).

### Development Overrides (`[dev]`)

Force dependencies and AST injections across all initialized projects regardless of CLI flags:

```toml
[dev]
extra_dependencies = ["bump-my-version"]

[dev.pyproject]
custom_ruff = '''
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "T20", "PT", "C4", "D"]
ignore = ["E501", "D100", "D104", "D107"]
'''
```

### Global Template Aliases (`[templates]`)

Map friendly shorthand names to local files or remote URLs:

```toml
[templates]
my-org-api = "https://raw.githubusercontent.com/MyOrg/standards/main/api.toml"
data-science = "~/Developer/templates/ds_base.toml"
```

Templates declared here can be invoked directly with `protostar init --template my-org-api`, appear automatically in the interactive wizard, and bypass the remote trust warning dialog.

For complete documentation on creating and using templates, see **[Templates & Portable Configurations](./templates.md)**.
