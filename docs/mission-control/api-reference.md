# API Reference

The engine strictly isolates state definition from imperative execution. Rather than executing disjointed setup scripts, the Orchestrator evaluates a polymorphic array of `BootstrapModule` objects interacting exclusively with a centralized state object: the `EnvironmentManifest`.

Think of the `EnvironmentManifest` as the nucleus of the scaffolding process. All modules revolve around this state object, mutating its properties and injecting AST payloads during their respective `build()` phases.

<div class="spacer-2"></div>

```mermaid
classDiagram
    direction BT

    class EnvironmentManifest {
        +DependencyManifest dependencies
        +FilesystemManifest filesystem
        +ToolingManifest tooling
        +TaskManifest tasks
        +ProjectMetadata metadata
        +CollisionStrategy collision_strategy
        +add_ide_setting(key: IDESettingKey, value: Any)
        +add_diagnostic(phase: str, message: str)
    }

    class DependencyManifest {
        +list[str] dependencies
        +list[str] dev_dependencies
        +list[str] docs_dependencies
        +add(package: str)
        +add_dev(package: str)
        +add_docs(package: str)
    }

    class FilesystemManifest {
        +set[str] directories
        +dict[str, str] file_injections
        +dict[str, list[str]] file_appends
        +set[str] vcs_ignores
        +add_directory(path: str)
        +add_file_injection(path: str, content: str)
        +add_file_append(path: str, content: str)
    }

    class TaskManifest {
        +list[SystemTask] system_tasks
        +list[SystemTask] post_install_tasks
        +add_system_task(command: list[str], timeout: int, description: str)
        +add_post_install_task(command: list[str], timeout: int, description: str)
    }

    class ToolingManifest {
        +bool wants_pre_commit
        +bool wants_ci
        +add_pre_commit_hook(payload: str)
        +add_ci_step(step_yaml: str)
    }

    class BootstrapModule {
        <<Abstract>>
        +tuple cli_flags
        +str config_key
        +pre_flight()*
        +build(manifest: EnvironmentManifest)*
    }

    EnvironmentManifest *-- DependencyManifest : contains
    EnvironmentManifest *-- FilesystemManifest : contains
    EnvironmentManifest *-- TaskManifest : contains
    EnvironmentManifest *-- ToolingManifest : contains
    BootstrapModule ..> EnvironmentManifest : Mutates state via build()
```

<div class="spacer-1"></div>

## Class Definitions

!!! abstract "Telemetry & Error Handling: `protostar.errors`"

    Strictly typed operational errors that halt the execution pipeline safely and return POSIX-compliant exit codes.

    ::: protostar.errors.ProtostarError
        options:
            show_source: true
            show_bases: true
            show_root_heading: true
            show_root_toc_entry: true
            separate_signature: true

    ::: protostar.errors.ConfigurationError
        options:
            show_source: true
            show_bases: true
            show_root_heading: true
            show_root_toc_entry: true
            separate_signature: true

    ::: protostar.errors.NetworkFetchError
        options:
            show_source: true
            show_bases: true
            show_root_heading: true
            show_root_toc_entry: true
            separate_signature: true

    ::: protostar.errors.TemplateResolutionError
        options:
            show_source: true
            show_bases: true
            show_root_heading: true
            show_root_toc_entry: true
            separate_signature: true

    ::: protostar.errors.MissingDependencyError
        options:
            show_source: true
            show_bases: true
            show_root_heading: true
            show_root_toc_entry: true
            separate_signature: true

    ::: protostar.errors.CommandExecutionError
        options:
            show_source: true
            show_bases: true
            show_root_heading: true
            show_root_toc_entry: true
            separate_signature: true

    ::: protostar.errors.CommandTimeoutError
        options:
            show_source: true
            show_bases: true
            show_root_heading: true
            show_root_toc_entry: true
            separate_signature: true

    ::: protostar.errors.FileSystemError
        options:
            show_source: true
            show_bases: true
            show_root_heading: true
            show_root_toc_entry: true
            separate_signature: true

    ::: protostar.errors.SecurityViolationError
        options:
            show_source: true
            show_bases: true
            show_root_heading: true
            show_root_toc_entry: true
            separate_signature: true

    ::: protostar.errors.ExecutionAbortedError
        options:
            show_source: true
            show_bases: true
            show_root_heading: true
            show_root_toc_entry: true
            separate_signature: true

    ::: protostar.errors.PartialExecutionAbortedError
        options:
            show_source: true
            show_bases: true
            show_root_heading: true
            show_root_toc_entry: true
            separate_signature: true

!!! abstract "Core Interface: `BootstrapModule`"

    ::: protostar.modules.base.BootstrapModule
        options:
            show_source: true
            show_bases: true
            show_root_heading: true
            show_root_toc_entry: true
            separate_signature: true
