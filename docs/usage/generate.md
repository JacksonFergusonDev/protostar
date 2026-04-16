# Boilerplate Generation

While `init` handles the one-time scaffolding of your project's architectural foundation, the `generate` command is designed for repeated execution throughout your development lifecycle.

!!! warning "Experimental API (Proof of Concept)"
    The `generate` command is currently an **experimental proof-of-concept**. While `init` is a fully realized, deterministic state machine, `generate` is in its infancy. The current target registry is intentionally minimal. It serves as a structural placeholder demonstrating the baseline mechanics for future declarative, context-aware scaffolding capabilities.

---

## Current Capabilities

The `generate` command currently executes imperative hardcoded file creation. It requires a `TARGET` and, depending on the context, a `NAME` identifier.

**Syntax:** `protostar generate <TARGET> [NAME]`

| Target | Name Parameter Evaluation | Output Description |
| --- | --- | --- |
| `cpp-class` | The class identifier *(e.g., `Engine`)* | Generates standard C++ `.hpp` header and `.cpp` implementation files. |
| `tex` | The output filename *(e.g., `report`)* | Generates a boilerplate LaTeX document based on the global preset. |
| `pio` | The board target ID *(e.g., `esp32dev`)* | Generates a standard PlatformIO environment configuration. |
| `cmake` | *Ignored automatically* | Generates a `CMakeLists.txt` statically linking local C++ source files. |
| `circuitpython` | *Ignored automatically* | Generates a CircuitPython `code.py` boilerplate and IDE type-checking config. |

### Execution Footprints

To illustrate the current baseline, here are the execution paths and resulting payloads for the active generation targets.

#### Document Typesetting (LaTeX)

Generating a LaTeX document sets up a modern compilation environment using `fontspec` and standard geometry styling.

!!! info "Artifact Tracking Note"
    If Protostar does not detect a `.gitignore` in the current workspace during a `tex` generation, it will emit a warning advising you to track LaTeX build artifacts. Note: if the workspace was initialized using `protostar init --latex`, this is already handled automatically.

=== "Terminal Execution"

    ```bash
    protostar generate tex report
    ```

=== "Resulting Workspace"

    ```text
    .
    └── report.tex
    ```

??? abstract "View Generated Files"
    --8<-- "gen_tex.md"

#### Object-Oriented Systems (C++)

Scaffolding a new C++ class automatically generates the header and implementation files, pre-wiring the `#include` directives and standard constructors.

=== "cpp-class Execution"
    ```bash
    protostar generate cpp-class ExampleClass
    ```

    ```text
    .
    ├── ExampleClass.cpp
    └── ExampleClass.hpp
    ```

    ??? abstract "View Generated Files"
        --8<-- "gen_cpp-class.md"

=== "cmake Execution"
    ```bash
    protostar generate cmake
    ```

    ```text
    .
    └── CMakeLists.txt
    ```

    ??? abstract "View Generated Files"
        --8<-- "gen_cmake.md"

#### Embedded Systems (CircuitPython & PlatformIO)

For hardware development, Protostar scaffolds configurations and execution loops tailored to embedded constraints.

=== "CircuitPython Execution"

    ```bash
    protostar generate circuitpython
    ```

    ```text
    .
    ├── .pyrightconfig.json
    └── code.py
    ```

=== "PlatformIO Execution"

    ```bash
    protostar generate pio esp32dev
    ```

    ```text
    .
    └── platformio.ini
    ```

??? abstract "View Generated Files"
    --8<-- "gen_circuitpython.md"

??? abstract "View Generated Files"
    --8<-- "gen_pio.md"

---

## Development Roadmap

To elevate `generate` to a first-class citizen alongside `init`, the architecture will evolve from imperative hardcoding to declarative, context-aware scaffolding. The following structural upgrades are planned:

### 1. User-Defined Extensibility (Template Engine)

Generators are currently locked behind internal Python classes utilizing static f-strings. This will shift to a dynamic template-resolution architecture (e.g., using Jinja2 or a lightweight alternative). Protostar will scan a local `.protostar/templates/` directory before falling back to global defaults, allowing development teams to enforce custom boilerplate standards without modifying the core CLI.

### 2. Auto-Wiring via AST Mutation

Creating a file is only half the friction; the file must be integrated into the broader project structure. Future iterations of `generate` will leverage the existing `tomlkit` AST engine and regex markers to automatically link generated code. For instance, generating a new C++ class will automatically parse and update the local `CMakeLists.txt`'s target sources block, and generating a web router will inject the necessary include directives into the application's entry point.

### 3. Fulfilling the `.protostar.toml` Contract

While the global `config.toml` drives environment initialization, local overrides for generator targets are slated to be managed via a `.protostar.toml` file in the project root. The `TargetGenerator` interface will parse this file to extract repository-specific context—such as injecting designated C++ namespaces or resolving a specific author's name and university affiliation for LaTeX macros—bypassing the current generic placeholders.

### 4. Interactive Variable Resolution

The command currently accepts a singular `identifier` argument. As templates grow in complexity, `generate` will dynamically evaluate missing variables and trigger terminal prompts (via `questionary`) to ingest required context before executing disk writes.
