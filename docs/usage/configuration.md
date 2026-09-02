---
description: "Configure Protostar's global defaults, including preferred tools, author information, and behaviors."
---

# Global Configuration

Your global configuration file acts as the baseline defaults for environment initialization (which can be overridden by templates or CLI flags). Open it in your system's default `$EDITOR` by running:

```bash
protostar config
```

![Protostar Config Help](../fixtures/cli_config_help.svg)

To restore your configuration to the factory defaults:

```bash
protostar config --reset
```

To bypass the confirmation prompt (e.g., in automated scripts), append `--force-replace`:

```bash
protostar config --reset --force-replace
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

--8<-- "table_config_env.md"

### Supported Licenses

When configuring `license` in `[env]`, Protostar injects the full license file and attaches the official PyPI Trove classifier to `pyproject.toml`:

--8<-- "table_licenses.md"

### Global Template Aliases (`[templates]`)

Map friendly shorthand names to local files or remote URLs:

```toml
[templates]
my-org-api = "https://raw.githubusercontent.com/MyOrg/standards/main/api.toml"
data-science = "~/Developer/templates/ds_base.toml"
```

Templates declared here can be invoked directly with `protostar init --template my-org-api`, appear automatically in the interactive wizard, and bypass the remote trust warning dialog.

---

## Next Steps

- **[Environment Initialization](./init.md):** Test your configured global defaults with `protostar init`.
- **[Templates & Portable Configurations](./templates.md):** Discover how template aliases streamline custom template consumption and bypass remote security prompts.
- **[CLI Reference](./cli-reference.md):** Review all command-line options and runtime flag overrides.
