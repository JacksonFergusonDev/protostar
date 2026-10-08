---
description: "The engine's Python API: the manifest, the modules that fill it, and the orchestrator and executor that act on it."
---

# API Reference

The engine keeps deciding apart from doing. The `Orchestrator` runs each enabled `BootstrapModule`, and every module declares what its tool needs into one shared object, the `EnvironmentManifest`. Nothing is written while modules build: the `SystemExecutor` applies the finished manifest afterwards, in one transaction.

The diagram shows the manifest's main parts and the methods modules call most; the class definitions below list everything.

```mermaid
classDiagram
    direction LR

    class EnvironmentManifest {
        +DependencyManifest dependencies
        +FilesystemManifest filesystem
        +ToolingManifest tooling
        +TaskManifest tasks
        +ProjectMetadata metadata
        +CollisionStrategy | None collision_strategy
        +frozenset~Path~ collisions
        +frozenset~MissingTool~ missing_tools
        +TemplateReference | None template_reference
        +bool one_shot
        +add_ide_setting(key: IDESettingKey, value: Any)
        +target_files() set~Path~
        +planned_files() set~Path~
    }

    class DependencyManifest {
        +list[str] dependencies
        +list[str] dev_dependencies
        +list[str] docs_dependencies
        +list[DependencyInclude] includes
        +add(package: str)
        +add_dev(package: str)
        +add_docs(package: str)
        +add_include(group, include)
    }

    class FilesystemManifest {
        +set[str] directories
        +dict[str, str] file_injections
        +dict structured
        +dict regions
        +set[str] vcs_ignores
        +set[str] workspace_hides
        +add_directory(path: str)
        +add_file_injection(path: str, content: str)
        +add_structured(path: str, content: str, producer: str)
        +add_region(path: str, content: str, identity: str)
        +add_vcs_ignore(path: str)
    }

    class TaskManifest {
        +list[SystemTask] system_tasks
        +list[SystemTask] post_install_tasks
        +add_system_task(command, timeout, description, owned_files, owned_trees)
        +add_post_install_task(command, timeout, description, owned_files, owned_trees)
    }

    class ToolingManifest {
        +HookRunner hook_runner
        +bool wants_ci
        +bool wants_release
        +bool wants_docker
        +bool wants_just
        +bool wants_agents
        +bool wants_community
        +add_pre_commit_hook(payload: str)
        +add_ci_step(step_yaml: str)
        +add_ide_extension(extension_id: str)
    }

    EnvironmentManifest *-- DependencyManifest : contains
    EnvironmentManifest *-- FilesystemManifest : contains
    EnvironmentManifest *-- TaskManifest : contains
    EnvironmentManifest *-- ToolingManifest : contains
```

## Class Definitions

!!! abstract "Diagnostics & Error Handling: `protostar.errors`"

    Strictly typed operational errors that halt the execution pipeline safely and return POSIX-compliant exit codes.

    ::: protostar.errors
        options:
            show_source: true
            show_bases: true
            show_root_heading: true
            show_root_toc_entry: true
            separate_signature: true
            members_order: source

!!! abstract "Core Interface: `BootstrapModule`"

    Each module's `build()` declares what its tool needs into the shared manifest, or raises a `ProtostarError` when the request can't be planned. It never writes a file or runs a command.

    ```mermaid
    flowchart LR
    M[BootstrapModule] --> B["build(manifest)"]
    B -->|Declares| EM[(EnvironmentManifest)]
    B -->|Can't be planned| E[ProtostarError]
    ```

    ::: protostar.modules.base.BootstrapModule
        options:
            show_source: true
            show_bases: true
            show_root_heading: true
            show_root_toc_entry: true
            separate_signature: true
