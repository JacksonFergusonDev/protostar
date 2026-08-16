# Built-in Templates

Built-in Templates act as high-level macros that execute on top of a base language footprint. They dynamically inject structural scaffolding, directories, and domain-specific dependencies into the environment manifest.

!!! tip "Dynamic Resolution"
    Templates do not hardcode package versions. They pass the library requirements directly to the package manager (`uv`), allowing your environment to resolve the latest compatible telemetry, astrophysics, or API packages at runtime.

## Available Templates

--8<-- "table_templates.md"
