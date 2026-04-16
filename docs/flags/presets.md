# Dependency Presets

Presets act as high-level macros that execute on top of a base language footprint. They dynamically inject structural scaffolding and domain-specific libraries into the environment manifest.

!!! tip "Dynamic Resolution"
    Presets do not hardcode package versions. They pass the library requirements directly to the package manager, allowing your environment to resolve the latest compatible telemetry, scientific, or API packages at runtime.

## Available Presets

--8<-- "table_presets.md"
