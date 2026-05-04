# Language Footprints

The base layer of Protostar handles the initialization of language-specific package managers, structural ignores, and compiler cache exclusions.

<div class="grid cards" markdown>

- :material-language-python: __Python (`--python`)__

    Delegates to `uv` (or `pip`) to initialize `pyproject.toml`, establish a virtual environment, and ignore `.venv/`, `__pycache__/`, and Jupyter checkpoints.

- :material-language-rust: __Rust (`--rust`)__

    Triggers `cargo init`, ignores the `target/` build directory, and queues `rustfmt` and `clippy` for pre-commit static analysis.

- :material-nodejs: __Node.js (`--node`)__

    Initializes `package.json` via your configured package manager, ignores `node_modules/`, `dist/`, and `.next/`, and injects Prettier and ESLint hooks.

- :material-language-cpp: __C/C++ (`--cpp`)__

    Ignores heavy compilation artifacts and caches (`*.o`, `*.out`, `build/`, `.cache/`, `compile_commands.json`) and injects the `clang-format` hook to enforce standard styling.

- :material-file-document-outline: __LaTeX (`--latex`)__

    Ignores typesetting auxiliary files (`*.aux`, `*.log`, `*.synctex.gz`) and queues `tex-fmt` to standardize document structures.

</div>

!!! info "The Python Gravity Well"
    Protostar was originally engineered to accelerate Python development pipelines, and its Python scaffolding (specifically via `uv`) is highly refined and deeply integrated.

    While Protostar natively supports scaffolding for C++, Rust, Node.js, and LaTeX, these footprints currently represent basic, standard implementations. If you are a domain expert in these ecosystems, we gladly welcome PRs to help stabilize and expand their dependency pipelines to match the maturity of the Python layer.
