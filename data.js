window.BENCHMARK_DATA = {
  "lastUpdate": 1784342118553,
  "repoUrl": "https://github.com/JacksonFergusonDev/protostar",
  "entries": {
    "Protostar Initialization Latency": [
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "1fddaefa15b1f1ad7a8865a68e00ac3c6b05a4b2",
          "message": "chore: migrate to hyperfine, decouple workflows, and add rigorous benchmark tier (#41)\n\n- Replace `pytest-benchmark` with `hyperfine` for accurate out-of-process latency measurement.\n- Split CI logic: `benchmark.yml` (state mutator with write perms) and `ci.yml` (read-only regression gatekeeper).\n- Add `test-benchmark-slower` to Makefile (30 warmup, 90 runs) to resolve hyperfine caching/outlier warnings.\n- Configure `benchmark.yml` to use the rigorous benchmark tier for high-precision historical tracking on `main`.\n- Keep `ci.yml` on the faster benchmark tier to maintain PR velocity.\n- Remove latency badge generation/push logic to prevent reporting volatile CI VM metrics as true performance.\n- Update README to reflect accurate local M3 benchmark metrics (~83.7 ms) and remove badge references.",
          "timestamp": "2026-03-07T18:09:07-08:00",
          "tree_id": "2b158d9991db5b0b9af5c889c3a3fcb7c4029681",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1fddaefa15b1f1ad7a8865a68e00ac3c6b05a4b2"
        },
        "date": 1772935814932,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 130.56,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "67a6565e9429026fecbabf3a9516213b9a798333",
          "message": "test: harden suite with structural TOML assertions, true e2e, and I/O fault tolerance (#42)\n\n- test(integration): removed `subprocess.run` mocks from e2e tests to execute the actual `uv` binary, verifying true upstream integration within a safe `tmp_path` sandbox.\n\n- test(executor): refactored TOML configuration generation tests to use structural `tomllib` assertions against complex external fixtures, replacing brittle string checks.\n\n- fix(executor): patched `_deep_merge_tomlkit` to strictly purge stale scalar keys during `OVERWRITE` collisions, a bug uncovered by the new structural tests.\n\n- test(executor): added edge-case coverage for OS-level file I/O interruptions, updating the Orchestrator to gracefully handle `OSError` and `PermissionError` without raw tracebacks.",
          "timestamp": "2026-03-07T19:03:58-08:00",
          "tree_id": "43f25bfbd15f20a0859ee5ad01a1549f4399cdcc",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/67a6565e9429026fecbabf3a9516213b9a798333"
        },
        "date": 1772939103656,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 134.74,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "09d61bb5c7146ce19c1bf700807d002fcf5710e7",
          "message": "test: elevate core modules to 95% total test coverage (#43)\n\n- cli: cover init abortion on missing footprints, generate target resolution, and config editor spawning via subprocess mocks\n- cli: cover help dispatcher and parser metadata loading fallbacks\n- wizards: add intercept logic for PROTOSTAR_BENCHMARK_WIZARD and keyboard interrupt abort paths\n- generators: cover collision interceptions and missing identifier validations for pio and circuitpython\n- generators: verify latex generator applies tex suffixes, handles academic presets, and warns on missing gitignores\n- modules: add pre-flight system binary validation (cargo, uv, pip, npm) to language layers\n- modules: verify deterministic artifact injection and pre-commit hooks for rust, cpp, and latex layers\n- modules: verify automatic `-y` flag injection for npm configurations\n- modules: cover basic property validation and `*~` ignore logic for Linux/macOS layers",
          "timestamp": "2026-03-07T19:34:43-08:00",
          "tree_id": "02843cc149050420f8951285b05186be20e67d87",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/09d61bb5c7146ce19c1bf700807d002fcf5710e7"
        },
        "date": 1772940950897,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 131.05,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "7a00e9753b40627af3afbaed0315788bcb9c96d1",
          "message": "build: enforce strict linting, 90% coverage gate, and optimize CI execution (#44)\n\n- build: expand ruff select rules to include RUF, N, and RET\n- build: configure local coverage report to fail_under 90% and skip_covered\n- build: optimize CI workflows to only sync the `ci` dependency group, bypassing unused dev tools\n- style: annotate `ProtoHelpFormatter.styles` with `ClassVar` (RUF012)\n- style: replace list concatenation with iterable unpacking in executor subprocesses (RUF005)\n- test: replace unused unpacked variables in test suite with splat operators (RUF059)\n- test: convert pytest.raises match strings to raw strings and escape regex wildcards (RUF043)",
          "timestamp": "2026-03-07T23:19:28-08:00",
          "tree_id": "b2bf3a578158a0cf46edc05d48697ec7bb1dc966",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/7a00e9753b40627af3afbaed0315788bcb9c96d1"
        },
        "date": 1772954434917,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 132.61,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "032965e4b5a33afe14d7956407f21f6bda2b3303",
          "message": "fix: resolve pre-commit DAG execution order and harden testing lifecycle (#45)\n\n- Execution Lifecycle: Introduced a `post_install_tasks` queue to the `EnvironmentManifest` and `SystemExecutor` to enforce that virtual environment binaries (e.g., `pre-commit`, `direnv`) are strictly invoked after dependency resolution materializes the `.venv`.\n\n- Binary Routing: Updated `PreCommitModule` to explicitly route execution through the active package manager context (`uv run` or `.venv/bin/`) to prevent global `$PATH` contamination.\n\n- Telemetry UI: Refactored the unhandled exception crash reporter to utilize Rich's OSC 8 markdown hyperlink syntax, hiding massive URL-encoded tracebacks behind a clickable terminal link.\n\n- Lifecycle Testing: Implemented `test_executor_lifecycle_ordering` with mocker tracking to explicitly assert the topological phases of the DAG execution.\n\n- Integration Coverage: Added complete E2E tests for the `pre-commit` and `direnv` modules, parent `$VIRTUAL_ENV` shell isolation, and the telemetry UI via a new hidden `--crash-test` flag.\n\n- Headless Assertions: Updated tooling tests to correctly assert against the `post_install_tasks` queue and configured the crash reporter E2E test to handle dynamic TTY-stripping by the Rich console.",
          "timestamp": "2026-03-08T13:06:49-07:00",
          "tree_id": "e49b6c9c27f31a941984e723f9d295e6763a75f5",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/032965e4b5a33afe14d7956407f21f6bda2b3303"
        },
        "date": 1773000478812,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 134.15,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "2c080529f49247c5a68916310703a797be87aef9",
          "message": "fix: sandbox test suite environment and implement dynamic global config seeding (#46)\n\nThe run_cli test fixture was previously inheriting the host machine's OS environment variables, allowing the host's global ~/.config/protostar/config.toml to leak into the test execution. This caused O(N) network cascades when pre-commit was enabled globally, as background git processes were spawned for every parameterized test.\n\nThis patch:\n- Overrides HOME and USERPROFILE in the test subprocess to strictly map to the pytest tmp_path.\n- Explicitly preserves UV_CACHE_DIR to maintain test velocity.\n- Introduces the `seed_global_config` fixture to allow integration tests to dynamically generate mock global configurations.\n- Refactors integration tests to explicitly validate the orchestrator's state resolution hierarchy against mock file systems.",
          "timestamp": "2026-03-08T14:26:52-07:00",
          "tree_id": "fbe2d74368c4903307a1156107802c1fb625d9cb",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/2c080529f49247c5a68916310703a797be87aef9"
        },
        "date": 1773005275838,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 131.55,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "8de6cc5142a0a419c4aff88cdaf30139ec6095a0",
          "message": "feat: enforce python 3.13 baseline, fix autocomplete docs, and refine UX (#47)\n\n- Enforces a deterministic Python 3.13 baseline in the global config and executor fallbacks to override arbitrary `uv` version resolution.\n\n- Updates `README.md` shell autocomplete instructions to include `~/.local/bin` PATH requirements and `bashcompinit` initialization for Zsh.\n\n- Injects astrophysics-themed terminology into specific terminal status spinners and collision warnings.\n\n- Synchronizes the `pytest` suite to expect version-specific binary calls and initialization flags.",
          "timestamp": "2026-03-08T14:56:43-07:00",
          "tree_id": "eace1806695e8ddd9854409339e27623e30613a5",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/8de6cc5142a0a419c4aff88cdaf30139ec6095a0"
        },
        "date": 1773007069558,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 131.78,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "cdf7582fe3101197fe8c78f8810c89a5c946f194",
          "message": "chore: bump version 0.5.0 → 0.6.0",
          "timestamp": "2026-03-08T15:00:22-07:00",
          "tree_id": "26faeb01fd9052b21d41aa385107f9937d4c4ed7",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/cdf7582fe3101197fe8c78f8810c89a5c946f194"
        },
        "date": 1773007294946,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 127.25,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "1ab73f240e609fb51448b8aeb4c9ef2860a622bd",
          "message": "fix: rectify LaTeX pre-commit resolution and stabilize SIGINT handling (#48)\n\n* fix(latex): resolve dead upstream url for tex-fmt pre-commit hook\n\nUpdates the repository target for the `tex-fmt` hook from `aarnphm/tex-fmt`\nto the correct upstream `WGUNDERWOOD/tex-fmt`. This resolves a latent bug\nwhere `pre-commit autoupdate` would attempt to clone a nonexistent repository,\ntriggering a blocking OS-level credential manager prompt and hanging the\nsubprocess execution block.\n\n* fix(cli): trap SIGINT to prevent traceback spillage on manual abort\n\nImplements a top-level `KeyboardInterrupt` exception handler within the\nmain execution pipeline. This ensures the orchestrator exits cleanly with\nthe standard POSIX code 130 instead of dumping the raw Python call stack\nto `stderr` when a user issues a `Ctrl+C` interrupt signal.\n\n* refactor(wizard): suppress argparse help dump on interactive cancellation\n\nModifies `intercept_interactive_wizards` to execute a silent exit (code 130)\nwhen a user intentionally aborts the TUI selection prompt. This removes the\nanti-pattern of forcing a verbose `argparse` manual dump to the terminal\nimmediately after a cancellation event.\n\n* fix(wizard): return exit code 0 on benchmark intercept\n\nUpdates the `PROTOSTAR_BENCHMARK_WIZARD` early exit in `run_init_wizard`\nto explicitly call `sys.exit(0)` instead of returning `None`. This ensures\nthat `hyperfine` registers the simulated abort as a successful execution\nduring CI performance testing, fixing the workflow regression introduced\nby the recent TUI cancellation refactor. Updates the corresponding\n`test_run_init_wizard_benchmark_abort` unit test to catch and validate\nthe successful `SystemExit` state.\n\n* test: add keyboard interrupt handling test to increase code coverage",
          "timestamp": "2026-03-09T18:20:51-07:00",
          "tree_id": "cbe5e1f48c7ec1667823f3cd02f594948e87bd64",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1ab73f240e609fb51448b8aeb4c9ef2860a622bd"
        },
        "date": 1773105719208,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 131.45,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "0de94e2e8ff2db612171da606bb56e0bf2a8c6ae",
          "message": "feat(presets): expand astro preset with scientific stack and nbdime integration (#49)\n\n* feat(presets): expand astro preset with scientific stack and nbdime integration\n\n- Injects foundational scientific libraries (numpy, scipy, pandas, matplotlib) alongside astropy.\n- Scaffolds `.gitattributes` to enforce binary tracking for FITS files and LF line endings for notebooks.\n- Queues `nbdime config-git --enable` post-install task to resolve JSON-diff conflicts.\n- Automates `git init` dependency if a repository is not present.\n\n* test: fix exhaustive suite failures and add pip fallback coverage for astro preset\n\n- Resolves `test_preset_orthogonality` integration failures caused by `nbdime` crashing on uninitialized git repos.\n- Expands unit tests in `test_presets.py` to cover new `AstroPreset` dependencies and `.gitattributes` injections.\n- Adds specific coverage for the `pip` vs `uv` fallback logic in the `nbdime` execution routing.",
          "timestamp": "2026-03-12T19:50:04-07:00",
          "tree_id": "3cea83dfb3993833fbe8b125df4b61490f5813a7",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/0de94e2e8ff2db612171da606bb56e0bf2a8c6ae"
        },
        "date": 1773370272256,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 131.77,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "29139614+renovate[bot]@users.noreply.github.com",
            "name": "renovate[bot]",
            "username": "renovate[bot]"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "e096965654d076dac2cc8eba91fa8c3960bbbad4",
          "message": "chore(deps): lock file maintenance (#51)\n\nCo-authored-by: renovate[bot] <29139614+renovate[bot]@users.noreply.github.com>",
          "timestamp": "2026-03-12T23:34:04-07:00",
          "tree_id": "ae71b6e47123b9a021602e72c4e4d21bd08f32b2",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/e096965654d076dac2cc8eba91fa8c3960bbbad4"
        },
        "date": 1773383719605,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 137.51,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "29139614+renovate[bot]@users.noreply.github.com",
            "name": "renovate[bot]",
            "username": "renovate[bot]"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "fe7e35885c432b0f811adfbcfadafac0836c3424",
          "message": "chore(deps): update github-actions (#50)\n\nCo-authored-by: renovate[bot] <29139614+renovate[bot]@users.noreply.github.com>",
          "timestamp": "2026-03-12T23:36:37-07:00",
          "tree_id": "8f37ce937bc1ab407868477d8389dd35e0113e5d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/fe7e35885c432b0f811adfbcfadafac0836c3424"
        },
        "date": 1773383868852,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 132.53,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "d49358f9aad279f0dfd266a193befff9c3336dcd",
          "message": "feat: implement granular task-level timeouts for system execution (#52)\n\nReplaces unbounded blocking I/O calls with task-specific execution timeouts to prevent the orchestrator from hanging indefinitely on stalled network requests.\n\n- Introduces `SystemTask` dataclass to bind execution time limits to shell commands.\n- Implements `TimeoutExpired` exception handling in the core subprocess wrapper.\n- Applies a default 30-second timeout to local shell configurations.\n- Grants a 600-second boundary for package manager resolutions (uv/pip).\n- Updates test suite to enforce the new architectural constraints.",
          "timestamp": "2026-03-13T19:08:37-07:00",
          "tree_id": "948b46f0c065dc3746a380755c022fbde6820fec",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d49358f9aad279f0dfd266a193befff9c3336dcd"
        },
        "date": 1773454189239,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 129.86,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "9a171c60906ec88047b9f4c59fb88899f1137b26",
          "message": "refactor: enforce explicit language constraints for tooling modules (#53)\n\nReplaces the hardcoded `requires_python` boolean in the base `BootstrapModule` with a scalable `required_languages` tuple. This prevents impossible combinations (e.g., scaffolding Ruff for a Rust project) from polluting the workspace in both headless and interactive execution paths.\n\n- Updates `BootstrapModule` interface to use dynamic language mapping.\n- Binds `RuffModule`, `MypyModule`, and `PytestModule` strictly to `PythonModule`.\n- Patches the TUI wizard (`run_init_wizard`) to evaluate and reject invalid combinations at the prompt.\n- Patches the CLI parser (`handle_init`) to intercept, warn, and drop explicit CLI tooling flags that violate language constraints.\n- Expands test suite coverage in `test_cli.py`, `test_wizard.py`, and `test_modules.py` to explicitly verify constraint logic.",
          "timestamp": "2026-03-13T19:41:35-07:00",
          "tree_id": "bcd84e82f249933bfee993464f1df86f32fb32af",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/9a171c60906ec88047b9f4c59fb88899f1137b26"
        },
        "date": 1773456158334,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 124.23,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "7d3bb1c76c508e3087760b7b28df61d93d957a8d",
          "message": "refactor(core): unify system exclusions and localize IDE injection (#54)\n\n- Default `ide` preference to `None` in global configuration to prevent implicit assumptions.\n- Migrate `vscode`/`cursor` interpreter path injection directly into `PythonModule`, ensuring strict coupling to Python footprint generation.\n- Excise deprecated `ide_layer.py` and `VSCodeModule` to eliminate dead code and abstraction overhead.\n- Rename `os_layer.py` to `system_layer.py` and implement a unified `SystemWorkspaceModule`.\n- Apply universal repository hygiene ignores (`.idea/`, `.vscode/`, `.env`, `.DS_Store`, `*~`) deterministically on every `init`.\n- Update test suite to reflect new component routing, removed mocks, and the `None` configuration baseline.",
          "timestamp": "2026-03-14T15:50:48-07:00",
          "tree_id": "ae1876f697ae54e3cffc9c43956e98dc75da6fcd",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/7d3bb1c76c508e3087760b7b28df61d93d957a8d"
        },
        "date": 1773528713597,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 130.86,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "1fe345c320b61544f67adf76ee479b1cafe41d62",
          "message": "refactor(core): unify system exclusions and localize IDE injection (#54)\n\n- Default `ide` preference to `None` in global configuration to prevent implicit assumptions.\n- Migrate `vscode`/`cursor` interpreter path injection directly into `PythonModule`, ensuring strict coupling to Python footprint generation.\n- Excise deprecated `ide_layer.py` and `VSCodeModule` to eliminate dead code and abstraction overhead.\n- Rename `os_layer.py` to `system_layer.py` and implement a unified `SystemWorkspaceModule`.\n- Apply universal repository hygiene ignores (`.idea/`, `.vscode/`, `.env`, `.DS_Store`, `*~`) deterministically on every `init`.\n- Update test suite to reflect new component routing, removed mocks, and the `None` configuration baseline.",
          "timestamp": "2026-03-14T18:30:24-07:00",
          "tree_id": "6ee3abf3045af771705220f8d2501f904195628a",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1fe345c320b61544f67adf76ee479b1cafe41d62"
        },
        "date": 1773538304943,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 130.77,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "aa88e36a248102c8efd81f53bf63cc5fc6f0cd02",
          "message": "fix(orchestrator): hoist --force flag evaluation above TTY check (#55)\n\nPreviously, the `--force` flag was ignored during interactive terminal\nsessions because `sys.stdin.isatty()` was evaluated first, routing the\nexecution flow directly to the questionary prompt.\n\nThis commit hoists the `self.force` check to the top of the\n`_evaluate_collisions` method, ensuring the explicit CLI flag acts as an\nunconditional override for the merge strategy, regardless of the\nenvironment's interactive status.",
          "timestamp": "2026-03-15T15:44:42-07:00",
          "tree_id": "0f84a6e17a590fdb7e7e102ae954edd047ac60f5",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/aa88e36a248102c8efd81f53bf63cc5fc6f0cd02"
        },
        "date": 1773614748059,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 131.33,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "27734dca5e751dd7f846468db1a5e85912ef3259",
          "message": "docs: implement zensical framework and structural guides (#60)\n\n* docs: implement zensical framework and structural guides\n\n* ci(benchmark): switch benchmark to use just",
          "timestamp": "2026-04-16T12:44:28-07:00",
          "tree_id": "ecd81960463e97f936db87a9466cb9fe5887e0c3",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/27734dca5e751dd7f846468db1a5e85912ef3259"
        },
        "date": 1776368727717,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 110.35,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "41f2a95adbc663550eddbba997bcbd85f023439a",
          "message": "fix: resolve readthedocs build failure and finalize zensical migration (#61)\n\nUpdate .readthedocs.yaml to use uv export and uv pip install --system. \nThis ensures that the Zensical framework and documentation dependencies \nare installed into the active system environment utilized by the \nReadTheDocs runner, rather than being isolated within a local .venv.\n\nAdditionally, update mkdocs.yml to switch the theme name and emoji \nextension namespace from material to zensical, resolving the \nModuleNotFoundError encountered during the build phase.",
          "timestamp": "2026-04-16T13:16:52-07:00",
          "tree_id": "99922c27070d87079ca63cbf796a16375cbe0af7",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/41f2a95adbc663550eddbba997bcbd85f023439a"
        },
        "date": 1776370678822,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 138.22,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "9c3fd1c822fcae432041cd4e370b6d264feb23d1",
          "message": "fix: resolve readthedocs build failure (#61)\n\nUpdate .readthedocs.yaml to use uv export and uv pip install --system.\nThis ensures that the Zensical framework and documentation dependencies\nare installed into the active system environment utilized by the\nReadTheDocs runner, rather than being isolated within a local .venv.",
          "timestamp": "2026-04-16T13:20:26-07:00",
          "tree_id": "786c61b84ac245ade7bad53f34f32f0931f5ddc4",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/9c3fd1c822fcae432041cd4e370b6d264feb23d1"
        },
        "date": 1776370925883,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 114.8,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "76b1cff90e49c7b58e124ca20a50322a15ff138d",
          "message": "fix: resolve readthedocs build failure (#61)\n\nUpdate .readthedocs.yaml to use uv export and uv pip install --system.\nThis ensures that the Zensical framework and documentation dependencies\nare installed into the active system environment utilized by the\nReadTheDocs runner, rather than being isolated within a local .venv.\n\nAdditionally, update mkdocs.yml to switch the emoji\nextension namespace from material to zensical, resolving the\nModuleNotFoundError encountered during the build phase.",
          "timestamp": "2026-04-16T13:26:01-07:00",
          "tree_id": "4092ddd8f290aff097e9239ed4747d24967847de",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/76b1cff90e49c7b58e124ca20a50322a15ff138d"
        },
        "date": 1776371270020,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 130.31,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "da4db743d6e8a66838765151381f01061411fe99",
          "message": "fix: resolve readthedocs build failure (#61)\n\nUpdate .readthedocs.yaml to use uv export and uv pip install --system.\nThis ensures that the Zensical framework and documentation dependencies\nare installed into the active system environment utilized by the\nReadTheDocs runner, rather than being isolated within a local .venv.\n\nAdditionally, update mkdocs.yml to switch the emoji\nextension namespace from material to zensical, resolving the\nModuleNotFoundError encountered during the build phase.",
          "timestamp": "2026-04-16T13:41:21-07:00",
          "tree_id": "c2210f661b4a2ce3d54b5959a06563e6b809f839",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/da4db743d6e8a66838765151381f01061411fe99"
        },
        "date": 1776372153852,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 126.07,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "432d6759e73cda1f1ff21cc18b97c4ae60d9d228",
          "message": "fix: resolve readthedocs build failure (#61)\n\nUpdate .readthedocs.yaml to use uv export and uv pip install --system.\nThis ensures that the Zensical framework and documentation dependencies\nare installed into the active system environment utilized by the\nReadTheDocs runner, rather than being isolated within a local .venv.\n\nAdditionally, update mkdocs.yml to switch the emoji\nextension namespace from material to zensical, resolving the\nModuleNotFoundError encountered during the build phase.",
          "timestamp": "2026-04-16T13:43:54-07:00",
          "tree_id": "6d6a5c6b5f3ecc388f7670ba4c6fd522b7521886",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/432d6759e73cda1f1ff21cc18b97c4ae60d9d228"
        },
        "date": 1776372298782,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 132.6,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "0fb0219d755239d0776760e9534d65d743100e99",
          "message": "fix: resolve readthedocs build failure (#61)",
          "timestamp": "2026-04-16T13:51:37-07:00",
          "tree_id": "6d6a5c6b5f3ecc388f7670ba4c6fd522b7521886",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/0fb0219d755239d0776760e9534d65d743100e99"
        },
        "date": 1776372802002,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 126.95,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "854c13ca7919ff6d96cdda4ef2ca5e6ccb2687a1",
          "message": "style(branding): transition to official lightweight static logos (#62)\n\nReplaces computationally expensive, script-generated animated logos with static SVGs to eliminate CPU spikes during documentation rendering. \n\n- Removes Python logo generation scripts and legacy assets\n- Integrates `hero-page.svg` and `favicon.svg` into MkDocs and CSS\n- Adds responsive light/dark mode SVGs to the README\n- Restyles README badges to match the Protostar theme colors\n- Transitions to a dynamic PyPI version badge, removing the README target from `pyproject.toml`",
          "timestamp": "2026-04-18T16:41:52-07:00",
          "tree_id": "fc6c3cf7a4331898f341a30458fc29f1e6772d8d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/854c13ca7919ff6d96cdda4ef2ca5e6ccb2687a1"
        },
        "date": 1776555769292,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 135.7,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "c4f3abcf2b37239cbac1209d9d54eac6e7d17e59",
          "message": "docs: migrate deep-dive documentation to ReadTheDocs and streamline README (#63)\n\n* docs: compress brew install and migrate autocomplete guide\n\n- Compressed Homebrew tap and install steps into a single command for cleaner UX.\n- Migrated 'Shell Autocomplete & Aliasing' out of the README and into the Getting Started documentation.\n- Added package-manager specific installation branches (Homebrew vs uv) for `argcomplete` to prevent toolchain contamination.\n\n* docs: refactor README into a top-of-funnel landing page\n\n- Stripped out heavy command matrices, AST configuration guides, and autocomplete setups to reduce cognitive load.\n- Injected prominent routing and badges linking to the new ReadTheDocs instance.\n- Compressed the Homebrew installation block into a single command.\n- Preserved the core architecture philosophy, latency benchmarks, and Quick Start execution paths to ensure the tool's value proposition is immediately clear.",
          "timestamp": "2026-04-19T14:24:20-07:00",
          "tree_id": "15d453b4df8313a0fe64b1de04cfb4ee6c4b9863",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/c4f3abcf2b37239cbac1209d9d54eac6e7d17e59"
        },
        "date": 1776633916546,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 131.32,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "4df00ed0977a520eca71c461c1afa38a596c0732",
          "message": "fix(ci): parse all hyperfine benchmark results for gh-pages (#64)\n\nPreviously, the inline Python script in the benchmark workflow hardcoded\nextraction to the 0th index of the benchmark results array, causing the\nTUI wizard latency metrics to be dropped before reporting.\n\nThis updates the transformation step to iterate through the entire JSON\narray and dynamically maps the raw execution commands to distinct\ndashboard labels (Headless Latency vs. TUI Wizard Latency).",
          "timestamp": "2026-04-19T14:48:20-07:00",
          "tree_id": "367749faacf683c0b9510fc1f6e8545cb02239e6",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/4df00ed0977a520eca71c461c1afa38a596c0732"
        },
        "date": 1776635357462,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 130.97,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 203.29,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "c6125aeecd8cd25a2cf128cac407be60a4c6d9d4",
          "message": "docs: enforce canonical rich UI default and optimize doc routing (#65)\n\n- Force `slate` palette as the default MkDocs state, disregarding local OS media queries.\n- Reframe theme toggle semantics to represent Rich/Minimal UI states.\n- Map dynamic hero SVG visibility strictly to `data-md-color-scheme` DOM attributes via CSS instead of native HTML media attributes.\n- Elevate documentation links in the README hierarchy.\n- Propagate readthedocs URL to package metadata in `pyproject.toml`.",
          "timestamp": "2026-04-19T21:59:22-07:00",
          "tree_id": "5fff0319bbdb1cff8f0f8a8e44fd7b101ac19203",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/c6125aeecd8cd25a2cf128cac407be60a4c6d9d4"
        },
        "date": 1776661218294,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 129.78,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 198.89,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "a50fa282ef531948a32d450b5b4e24a2ce4d43ba",
          "message": "refactor(docs): overhaul CSS architecture to remove technical debt (#66)\n\n- Consolidate duplicate selectors across the stylesheet\n- Remove !important overrides to flatten CSS specificity\n- Group MkDocs slate theme variables into a single source of truth\n- Purge dead code and establish strict universal vs. dark-mode boundaries",
          "timestamp": "2026-04-19T22:20:55-07:00",
          "tree_id": "3a9f002c20d5ba91baa5dc7838337892bbfd0b44",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a50fa282ef531948a32d450b5b4e24a2ce4d43ba"
        },
        "date": 1776662514751,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 142.73,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 214.4,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "1919281552247013fc1b072c9a904f5226a544f1",
          "message": "chore: simplify pyproject config and trim sdist contents (#67)\n\n- Removed `pyproject.toml` settings that were explicitly restating tool defaults\n- Simplified Ruff configuration by dropping unnecessary default-valued options\n- Replaced Ruff `exclude` usage with a leaner additive approach where appropriate\n- Removed redundant `mypy` settings that were already default behavior\n- Merged split author metadata into a single `{ name, email }` entry\n- Added explicit Hatch `sdist` exclusions for non-package repo content",
          "timestamp": "2026-04-19T22:39:44-07:00",
          "tree_id": "dffb1bf3fcac6dc37c4eec9cf146509ecd1707c3",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1919281552247013fc1b072c9a904f5226a544f1"
        },
        "date": 1776663643538,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 130.18,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 195.93,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "31bc16058db687d211c6556d02932b66ea64a977",
          "message": "fix: deterministic artifacts, notebook scoping, and generator formatting (#68)\n\n- fix(executor): enforce deterministic sorting for .gitignore appending to prevent hash randomization churn.\n- fix(generators): strip trailing whitespace from `CircuitPythonGenerator` multi-line string payload to ensure pre-commit compliance.\n- refactor(presets): remove `*.ipynb_checkpoints` from the base Python footprint and inject it exclusively into data science presets (Astro, ML, Scientific).\n- docs(fixtures): update `generate_doc_fixtures.py` payload with `--docker` and sync all markdown includes.",
          "timestamp": "2026-04-20T12:06:32-07:00",
          "tree_id": "cc9256a9303681869e672ff8aaef63488f34405e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/31bc16058db687d211c6556d02932b66ea64a977"
        },
        "date": 1776712049171,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 126.83,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 194.68,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "8ace60dc849f46eabbeb07fd86cb0698f9c284aa",
          "message": "fix: stabilize tomlkit AST injection spacing and refresh doc fixtures (#69)\n\n* fix(executor): resolve TOML AST injection spacing anomalies\n\n- Explicitly append `tomlkit.nl()` to newly injected `Table` and `AoT` objects in `_deep_merge_tomlkit` to prevent blocks from rendering flush against subsequent tables.\n- Introduce a regex pass in `_append_files` to condense stacked newlines (3+ down to 2) resulting from AST table overwrites.\n- Ensure standard trailing newlines are preserved when dumping the mutated document.\n\n* docs(fixtures): regenerate pyproject.toml markdown fixtures\n\nUpdate docs/includes fixtures to reflect the corrected TOML formatting, demonstrating proper single-line spacing before the `[dependency-groups]` block and standard EOF newlines.\n\n* test(executor): achieve full coverage on TOML AST spacing logic\n\n- Add test for empty Array of Tables (AoT) injection to verify the newline append bypass logic in `_deep_merge_tomlkit`.\n- Add test for identical AST mutations to ensure `_append_files` safely bypasses redundant disk I/O when the merged tree yields the same string as the base document.",
          "timestamp": "2026-04-20T21:24:23-07:00",
          "tree_id": "83ce1221359035cf10a234f2d748df2b80b1398e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/8ace60dc849f46eabbeb07fd86cb0698f9c284aa"
        },
        "date": 1776745524304,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 130.69,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 195.22,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "ac3f71ecf1cb771b768c17f636d9754348d59e20",
          "message": "feat: add context-aware status descriptions for system tasks (#70)\n\nResolves an abstraction leak where the SystemExecutor generated UI status \nspinners based purely on the raw command executable (e.g., displaying \"uv\" \nwhile actually running a heavy `pre-commit autoupdate` task). \n\n- Extends `SystemTask` and `EnvironmentManifest` with an optional `description` field.\n- Updates `SystemExecutor` to prioritize module-provided descriptions, falling back to a clean binary name extraction if omitted.\n- Injects domain-specific descriptions into `PreCommitModule`, `DirenvModule`, `AstroPreset`, and the primary language modules to clarify long-running network tasks.\n- Expands test suite with `pytest-mock` to verify the new UI routing and fallback logic without executing real subprocesses.\n- Synchronizes the Manifest API documentation and generated JSON fixtures with the new task signatures.",
          "timestamp": "2026-04-21T21:40:22-07:00",
          "tree_id": "0df101bec2fb5122584e4e5172fa4b2eb63b2534",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/ac3f71ecf1cb771b768c17f636d9754348d59e20"
        },
        "date": 1776832880128,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 135.85,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 205.44,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "d99fe064a224278d43ba45abc380de75aaef1d67",
          "message": "fix(docs): eliminate doc fixture git noise and enforce sync in CI (#71)\n\n- Update `generate_doc_fixtures.py` to use a static execution directory to prevent randomized `uv init` names.\n- Implement self-freezing regex logic to retain existing dependency versions and pre-commit hook revisions across script executions.\n- Override `ide_settings` in manifest generation to use generic `${workspaceFolder}` paths instead of leaking local absolute paths.\n- Strip `VIRTUAL_ENV` from `subprocess.run()` environment kwargs to prevent `uv` environment leakage in CI.\n- Add a CI check via `git diff --exit-code` on the Python 3.14 runner to fail builds that contain out-of-date documentation fixtures.\n- Update existing `docs/includes/*.md` pyproject files to use the stable `demo-project` name.",
          "timestamp": "2026-04-22T20:43:27-07:00",
          "tree_id": "5df22741c0484cc49de7eeaf3cc277caa9376501",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d99fe064a224278d43ba45abc380de75aaef1d67"
        },
        "date": 1776915867555,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 130.77,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 197.52,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "b924161b8df0c8dbcfa40b1325ad6a6bae38d7cf",
          "message": "refactor(scripts): overhaul doc fixture generation and enforce strict typing (#72)\n\n* refactor(scripts): abstract markdown file writing into unified utility\n\n* refactor(scripts): extract state-freezing regex mutations into pure functions\n\n* refactor(scripts): decouple CLI execution from artifact extraction in fixture generation\n\n* refactor(scripts): streamline table generation and code block extension mapping\n\n* build(tools): enforce strict ruff and mypy static analysis on scripts directory\n\n* fix(scripts): patch type hints, markdown extension resolution, and whitespace formatting\n\n* docs(fixtures): normalize CMakeLists markdown code block language to text",
          "timestamp": "2026-04-22T22:09:36-07:00",
          "tree_id": "8a6dabf6708ec94560b2da822a699560a0500a99",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/b924161b8df0c8dbcfa40b1325ad6a6bae38d7cf"
        },
        "date": 1776921036932,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 132.64,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 201.72,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "4750bfd2fae6663fd62ddc27a222a81c2b0b5807",
          "message": "feat(docs): automate CLI help SVG generation with custom terminal theme (#73)\n\nAutomates the generation of the CLI help menu artifact to prevent documentation drift. \n\n- Refactored `_write_markdown_snippet` to `_write_fixture` to support format-agnostic disk I/O.\n- Implemented `generate_cli_help_svg()` to parse the `argparse` AST and render a vectorized terminal window using `rich`.\n- Applied a custom `TerminalTheme` to map the SVG background and ANSI cyan/blue accents to the project's MkDocs stylesheet.\n- Added an \"Exploration & Help\" section to `getting-started.md` embedding the generated `cli_help.svg`.",
          "timestamp": "2026-04-23T22:45:46-07:00",
          "tree_id": "6b0252a9215d1ba6b5ec19bf0a06deb64e8c1460",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/4750bfd2fae6663fd62ddc27a222a81c2b0b5807"
        },
        "date": 1777009606228,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 128.48,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 193.23,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "29139614+renovate[bot]@users.noreply.github.com",
            "name": "renovate[bot]",
            "username": "renovate[bot]"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "8b7c73a2b646b78b444a432c070abe00675459cb",
          "message": "chore(deps): lock file maintenance (#56)\n\nCo-authored-by: renovate[bot] <29139614+renovate[bot]@users.noreply.github.com>",
          "timestamp": "2026-04-27T21:20:47-07:00",
          "tree_id": "6e937405074b71bd4cd9f3c8127d7ba618c43300",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/8b7c73a2b646b78b444a432c070abe00675459cb"
        },
        "date": 1777350102578,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 122.39,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 196.92,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "29139614+renovate[bot]@users.noreply.github.com",
            "name": "renovate[bot]",
            "username": "renovate[bot]"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "cd2eb7f78cdf54a15416df64c6e00dff61b206fe",
          "message": "chore(deps): pin dependencies (#57)\n\nCo-authored-by: renovate[bot] <29139614+renovate[bot]@users.noreply.github.com>",
          "timestamp": "2026-04-27T21:22:12-07:00",
          "tree_id": "3e9a044e863113b6a0f1ba5ebac77fcf09361e3e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/cd2eb7f78cdf54a15416df64c6e00dff61b206fe"
        },
        "date": 1777350186452,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 126.23,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 187.97,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "7a86abb5e49cac8f13d0f0e628386c2e451f0a03",
          "message": "fix(docs): stabilize SVG fixture generation and sync rich v15 output (#74)\n\n- Hardcoded `unique_id=\"cli_help\"` in `export_svg` to prevent randomized CSS class hashes from triggering spurious CI diff failures.\n- Regenerated `cli_help.svg` against the latest `uv.lock` to account for the new line height and text wrapping behaviors introduced in the rich v15 bump.",
          "timestamp": "2026-04-28T22:38:54-07:00",
          "tree_id": "19c9b238295ea44cc89e39d223acbd8487df8d33",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/7a86abb5e49cac8f13d0f0e628386c2e451f0a03"
        },
        "date": 1777441187614,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 114.15,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 185.64,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "8b1895eb0ecdd7de0ae6769f639ff0679ebb481e",
          "message": "feat(docs): automate init capabilities matrix and fix routing links (#75)\n\n- Replaced the static capabilities markdown table in `init.md` with an auto-generated `cli_init_help.svg`.\n- Refactored `scripts/generate_doc_fixtures.py` to support multiple SVG outputs.\n- Implemented AST inspection in the fixture script to safely capture custom Rich `Table` layouts without line-wrapping artifacts.\n- Fixed broken internal documentation routing links in `index.md` and `getting-started.md` caused by legacy directory prefixes.\n- Corrected a typo in the `getting-started.md` CLI help example.",
          "timestamp": "2026-04-29T13:19:55-07:00",
          "tree_id": "0044e2ed55796e421e9bd4fbf6a741ab4c678f9b",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/8b1895eb0ecdd7de0ae6769f639ff0679ebb481e"
        },
        "date": 1777494056880,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 113.11,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 176.44,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "1c37421de991aefcaaf6e0157349bc3d225050aa",
          "message": "chore: optimize build pipeline and refine fixture generation (#76)\n\n- build(justfile): replace manual `install` with silent `sync` prerequisite across all core targets to eliminate branch-switching dependency drift.\n- build(justfile): add `docs-fixtures-fast` recipe for iterative UI/AST testing.\n- refactor(scripts): standardize docstrings and streamline inline comments in `generate_doc_fixtures.py`.\n- feat(scripts): implement graceful SIGINT handling (exit code 130) for console interrupts.\n- feat(scripts): introduce `--fast` argparse flag to bypass expensive subprocess isolation tasks.",
          "timestamp": "2026-04-29T14:11:15-07:00",
          "tree_id": "11ced6231896333715b1fd819a9dc7f2ae423bd1",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1c37421de991aefcaaf6e0157349bc3d225050aa"
        },
        "date": 1777497129808,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 117.56,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 187.53,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "29139614+renovate[bot]@users.noreply.github.com",
            "name": "renovate[bot]",
            "username": "renovate[bot]"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "b35aaf53e65bf7a1c570ad640f05b0808bb1f5a9",
          "message": "chore(deps): update github-actions (#78)\n\nCo-authored-by: renovate[bot] <29139614+renovate[bot]@users.noreply.github.com>",
          "timestamp": "2026-05-01T13:47:58Z",
          "tree_id": "3b626f44cbd417ee907c4d90bca4b7ae15c04675",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/b35aaf53e65bf7a1c570ad640f05b0808bb1f5a9"
        },
        "date": 1777643337269,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 119.06,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 185.79,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "06544d19e42917bac4740c923c4cac5c085161fa",
          "message": "build(deps): remove redundant logo generation dependencies\n\nTransitioning the project logo from dynamic Python generation to a static\nSVG implementation has rendered several libraries obsolete. This commit\nprunes the dependency tree by removing the `logo` optional dependency\ngroup and its references, reducing the environment footprint.\n\nRemoved:\n- cairosvg\n- drawsvg\n- matplotlib\n- numpy",
          "timestamp": "2026-05-01T21:02:14-07:00",
          "tree_id": "331dc3b934b22d21a3cc2f7fe5a3ab81ac5c7b2d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/06544d19e42917bac4740c923c4cac5c085161fa"
        },
        "date": 1777694597743,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 114.02,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 179.17,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "a3662caa8d3b7208166091a317eef15e2debcb08",
          "message": "refactor(ci): extract inline benchmark parsing to dedicated script (#79)\n\nConsolidates the duplicated inline Python strings from our GitHub \nActions into a single, static-analysis-compliant script.\n\n- Implement `scripts/parse_benchmarks.py` with `argparse` and `TypedDict`\n- Update `benchmark.yml` to use the unified script for TUI vs Headless evaluation\n- Update `ci.yml` to use the script with `--gate-mode` for single-result regression checks\n- Fix 'rigerous' typo in benchmark step name",
          "timestamp": "2026-05-01T21:44:02-07:00",
          "tree_id": "f722a7b18bb63cd1e410c12386067226400aec6b",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a3662caa8d3b7208166091a317eef15e2debcb08"
        },
        "date": 1777697098496,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 113.48,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 185.23,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "96a64d5821fe477a65ec871e8c0825462eb85cb4",
          "message": "chore: bump version 0.6.0 → 0.7.0",
          "timestamp": "2026-05-02T16:56:24-07:00",
          "tree_id": "88b66691b4407270914e08701acdea5e23f36047",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/96a64d5821fe477a65ec871e8c0825462eb85cb4"
        },
        "date": 1777766249195,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 121.31,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 191.46,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "e878b06012f3257925046f5ab8a2151be5aaaed8",
          "message": "fix(ci): replace homebrew resource generator with poet pipeline",
          "timestamp": "2026-05-02T20:48:54-07:00",
          "tree_id": "000fbe72d83e0c8f283105670edd914c4cbdde10",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/e878b06012f3257925046f5ab8a2151be5aaaed8"
        },
        "date": 1777780253226,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 117.78,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 185.87,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "68aeeef7c545088a4a5aa10c718f7505a75b6ac7",
          "message": "chore: bump version 0.7.1 → 0.7.2",
          "timestamp": "2026-05-02T21:06:41-07:00",
          "tree_id": "1e8724b4fe5e1907cd86d5ad691ec8d576e69fa7",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/68aeeef7c545088a4a5aa10c718f7505a75b6ac7"
        },
        "date": 1777781265876,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 119.35,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 192.07,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "c3f90cf02753e79f8977513a09941afcfd2e26ac",
          "message": "chore: bump version 0.7.2 → 0.7.3",
          "timestamp": "2026-05-02T21:11:32-07:00",
          "tree_id": "8fa2d10cd2976bf2389c43609342e212d2e4bbd2",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/c3f90cf02753e79f8977513a09941afcfd2e26ac"
        },
        "date": 1777781567746,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 114.51,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 186.43,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "d3ad9fa5f437e2a2097b148e302b09e428922bc8",
          "message": "ci: refactor homebrew tap updates to use typed python script (#80)\n\n* Extracts Homebrew deployment logic from `release.yml` into `scripts/update_homebrew.py`.\n* Replaces `curl`, `jq`, and manual `venv` setup with Python standard library modules and `uv run`.\n* Adds comprehensive unit testing via `pytest-mock` for PyPI polling and `poet` resource generation.\n* Ensures deployment logic is now covered by strict Mypy and Ruff static analysis.",
          "timestamp": "2026-05-02T21:41:33-07:00",
          "tree_id": "ba0fd83c2f20890016b437c0691a054a5d1f8f92",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d3ad9fa5f437e2a2097b148e302b09e428922bc8"
        },
        "date": 1777783348679,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 119.01,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 185.96,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "ed31571318aa7953daef2293427574f96abcf690",
          "message": "chore: bump version 0.7.3 → 0.7.4",
          "timestamp": "2026-05-02T21:43:40-07:00",
          "tree_id": "ae90a1268009f0a05031fcdd637008829547a7c3",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/ed31571318aa7953daef2293427574f96abcf690"
        },
        "date": 1777783527160,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 113.47,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 178.21,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "d01e646ee06fb3af65002a8472f3953e3f2a4317",
          "message": "chore: bump version 0.7.4 → 0.7.5",
          "timestamp": "2026-05-02T22:34:24-07:00",
          "tree_id": "1c2f4a2aa8b105d52259965fccdbad1678188323",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d01e646ee06fb3af65002a8472f3953e3f2a4317"
        },
        "date": 1777786525943,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 119.64,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 189.55,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "f2d4b06fe81d94eecf451a78cac6339a53ddc097",
          "message": "chore: bump version 0.7.5 → 0.7.6",
          "timestamp": "2026-05-02T22:49:50-07:00",
          "tree_id": "bc07b046be9a83a0135e5922a2bdead280b850a7",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f2d4b06fe81d94eecf451a78cac6339a53ddc097"
        },
        "date": 1777787446545,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 111.67,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 175.65,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "04d7f15030aa74e302992088c76d555617c4f10a",
          "message": "chore: bump version 0.7.6 → 0.7.7",
          "timestamp": "2026-05-02T22:57:08-07:00",
          "tree_id": "1c34942996b981081e6f786906e0a645f6ea84d9",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/04d7f15030aa74e302992088c76d555617c4f10a"
        },
        "date": 1777787889658,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 114.55,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 186.72,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "f3f1cbc9dd256d5854e4f80ab2f05d5c37c25c31",
          "message": "test(scripts): update main integration test fixture for strict indentation\n\nAdjusts the dummy formula in `test_main_integration` to include the\n2-space indentation required by the recently hardened regex in\n`update_formula_url_sha`.\n\nPreviously, the fixture used zero-indentation strings which failed to\ntrigger the `re.sub` logic. This change ensures the test accurately\nsimulates a valid Homebrew formula structure and verifies the\nscript's ability to target root properties without side-effects on\ndeeply indented resource blocks.",
          "timestamp": "2026-05-02T23:02:49-07:00",
          "tree_id": "23076d5f5647a821afb4336e2428ae059e84e3cd",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f3f1cbc9dd256d5854e4f80ab2f05d5c37c25c31"
        },
        "date": 1777788229226,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 118.67,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 186.53,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "182b4bf1838100ea669e2796a72a823e2b691015",
          "message": "ci(release): promote TAG variable to job scope\n\nMoves the TAG environment variable from the 'Update Formula' step to\nthe job level. This ensures the variable is available to the\nsubsequent 'Commit and Push' step, preventing empty version strings\nin the Homebrew tap commit messages.",
          "timestamp": "2026-05-02T23:07:22-07:00",
          "tree_id": "5e2866d605802bf88205c7f44c3576ece88fc03c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/182b4bf1838100ea669e2796a72a823e2b691015"
        },
        "date": 1777788550655,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 114.93,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 183.56,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "bd688cb543d7c72216b6ff7e3da491ef974637fe",
          "message": "chore: bump version 0.7.7 → 0.7.8",
          "timestamp": "2026-05-02T23:09:34-07:00",
          "tree_id": "1eaa22c21a49057f60d1c63ffad675658f05c9f1",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/bd688cb543d7c72216b6ff7e3da491ef974637fe"
        },
        "date": 1777788698996,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 124.21,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 195.22,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "5bc8c238c70956a4429c84e36bc31004c1c3726d",
          "message": "ci: refactor homebrew release pipeline to typed python script\n\nThis refactor replaces the fragile, inline bash/sed logic in the release\nworkflow with a robust, strictly typed Python script.\n\nKey Improvements:\n- Implemented 'scripts/update_homebrew.py' using standard library networking\n  to eliminate dependencies on curl/jq.\n- Transitioned to 'homebrew-pypi-poet' for dependency resource generation,\n  orchestrated via ephemeral 'uv run' environments.\n- Added comprehensive unit tests for the release pipeline using pytest-mock.\n- Integrated the deployment logic into the project's static analysis\n  (Ruff/Mypy) suite.\n\nBug Fixes:\n- Fixed a regex 'blast radius' bug that was overwriting dependency URLs\n  with the root package URL.\n- Resolved a PyPI CDN propagation race condition by adding a retry loop\n  to the dependency resolution step.\n- Fixed a CI structural bug where 'brew audit' was evaluating a stale\n  remote clone instead of the mutated local workspace.\n- Enforced strict RuboCop-compliant indentation for Ruby resource blocks.\n\nFinal state: v0.7.8",
          "timestamp": "2026-05-02T23:28:18-07:00",
          "tree_id": "1eaa22c21a49057f60d1c63ffad675658f05c9f1",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/5bc8c238c70956a4429c84e36bc31004c1c3726d"
        },
        "date": 1777789841786,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 107.62,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 172.32,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "a311fc5c6894602a2b8a1e904a190c9ac1e1442a",
          "message": "docs: redirect ReadTheDocs links to stable build (#82)\n\nUpdates the ReadTheDocs URLs in the repository to target the `/stable/` build instead of `/latest/`.\n\n- Modifies the documentation badge and hyperlinks in `README.md`.\n- Updates the `Documentation` URL field in `pyproject.toml`.\n\nThis change ensures that visitors from GitHub and PyPI are directed to the documentation corresponding to the most recent tagged release, preventing version mismatch confusion caused by bleeding-edge changes on the main branch.",
          "timestamp": "2026-05-03T21:19:40-07:00",
          "tree_id": "9e167ac43bc778ea0a3f2683637e258a04c3f3cb",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a311fc5c6894602a2b8a1e904a190c9ac1e1442a"
        },
        "date": 1777868435376,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 117.41,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 187.64,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "b4a11e2714c4682588d0d94564e27f645c6d28e2",
          "message": "refactor(core): establish python singularity and amputate multi-language multiplexer (#83)\n\nExecutes Phase 1 of the roadmap by stripping superficial multi-language support \nand evolving Protostar into a dedicated, hyper-optimized Python engine.\n\n- chore(ci): temporarily set codecov to informational to allow massive code deletion\n- refactor(core): strip `required_languages` constraints from base abstractions\n- refactor(config): purge node and latex variables from global configuration schema\n- refactor(modules): delete Rust, Node, C++, and LaTeX modules; promote `PythonCore`\n- refactor(frontend): wire CLI and TUI wizard to bypass language selection loops\n- test: synchronize integration tests and doc fixtures with new python-only baseline",
          "timestamp": "2026-05-04T13:54:48-07:00",
          "tree_id": "e22af82fa723e968b9f913eda0b2df397635bed4",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/b4a11e2714c4682588d0d94564e27f645c6d28e2"
        },
        "date": 1777928141551,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 111.51,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 182.82,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "33ff1b7d715176a676d8e7274bf586792f8062a9",
          "message": "refactor(generators): deprecate and remove the generate subsystem entirely (#84)\n\nExecutes Phase 2 of the roadmap. Following the transition to a dedicated Python \nengine, the `generate` command has been removed to enforce a strict Unix philosophy. \nProtostar is now exclusively a high-velocity environment bootstrapper, completely \ndropping secondary file-templating responsibilities to eliminate technical debt.\n\n- refactor(generators): delete the `src/protostar/generators` directory completely\n- refactor(cli): remove the `generate` subparser, epilogs, and lazy loaders\n- refactor(frontend): remove generator routing from the interactive TUI multiplexer\n- test: purge all generator unit and integration tests\n- docs: synchronize doc fixture script to ignore deleted targets",
          "timestamp": "2026-05-04T17:12:31-07:00",
          "tree_id": "a4674d6ec7faabd1449411baae287bc54ab66877",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/33ff1b7d715176a676d8e7274bf586792f8062a9"
        },
        "date": 1777940007753,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 114.86,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 184.13,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "be680efba772c6ceee4b46c6444c0bb6ce461aab",
          "message": "refactor(core): streamline architecture for exclusive python initialization (#85)\n\nFinalizes Phase 3 of the architectural refactor, permanently removing the structural vestiges of the `generate` command and multi-language support. \n\n- Removed the `run_discovery_wizard` multiplexer TUI.\n- Rewired the CLI parser to map the bare `protostar` command directly to the `init` wizard.\n- Stripped local `.protostar.toml` parsing logic from the configuration loader, as localized AST overrides are obsolete without the `generate` pipeline.\n- Scrubbed `argparse` descriptions, CLI help text, and internal docstrings of deprecated multi-language references.",
          "timestamp": "2026-05-04T21:00:25-07:00",
          "tree_id": "f0a2280fe0d03ac2ff3487c85ac46ba884d0456b",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/be680efba772c6ceee4b46c6444c0bb6ce461aab"
        },
        "date": 1777953682151,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 112.81,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 180.36,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "0623d6124d4b3a91e9030ad25bf8ec6ac29ad4a1",
          "message": "docs: align documentation with python-exclusive architecture (#86)\n\nCompletes phase 4 of the roadmap by updating all documentation, README files, \nand contribution guidelines to reflect the removal of the `protostar generate` \ncommand and all non-Python scaffolding logic.\n\n- Removed all references to the `generate` workflow and related terminal assets.\n- Pruned non-Python parameters (e.g., node_package_manager, LaTeX styles) from config schemas.\n- Deleted the local `.protostar.toml` configuration documentation.\n- Removed legacy language comparisons (Rust, Node.js, C++) from the engine mechanics.\n- Updated `testing.md` and `CONTRIBUTING.md` to enforce the Python-only contribution boundary, swapping out legacy mocked test examples.",
          "timestamp": "2026-05-05T15:39:01-07:00",
          "tree_id": "aea63870ddc8156983dbb5400214644eb8772a8d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/0623d6124d4b3a91e9030ad25bf8ec6ac29ad4a1"
        },
        "date": 1778020805843,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 116.06,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 181.52,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "1eac60864e53695615bce4771e10744f90a23abf",
          "message": "docs: migrate developer onboarding from make to just (#87)\n\n- Added explicit system-level requirements (uv, just) to CONTRIBUTING.md.\n- Routed git hook initialization through `uv run pre-commit install` for strict isolation.\n- Replaced all legacy Makefile references in testing.md with current justfile targets.\n- Simplified `uv sync` execution in the justfile and cleaned up target comments.\n- Updated the repository URL in the git clone instructions.",
          "timestamp": "2026-05-05T16:18:24-07:00",
          "tree_id": "ede84bb47714ea0223343b927cf872b4a30a7520",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1eac60864e53695615bce4771e10744f90a23abf"
        },
        "date": 1778023154901,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 90.92,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 145.96,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "54cf66044420256808d06ff2c6620bd77be2a0c1",
          "message": "ci: delegate homebrew release to centralized tooling\n\nReplaces the hardcoded Homebrew deployment job with a reusable workflow\ncall to `ci-cd-tooling`. This delegates PyPI polling, dependency\nresolution, and formula synchronization to the centralized infrastructure,\naligning the repository with the standardized ecosystem architecture.",
          "timestamp": "2026-05-08T20:06:34-07:00",
          "tree_id": "c09e030028a856901e8178c9680d173b912ae428",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/54cf66044420256808d06ff2c6620bd77be2a0c1"
        },
        "date": 1778296056013,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 113.79,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 181.95,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "28cbab2d43ce6355dd3af326a59160be3a27d2f8",
          "message": "docs(branding): update logo typography and ensure deterministic rendering (#88)\n\n- Increased README logo width to 480px and corrected the alt text to \"Protostar Logo\".\n- Converted SVG logo text to paths via Inkscape to guarantee consistent cross-OS rendering.\n- Shrink-wrapped SVG bounding boxes with a 10px margin for tighter layout integration.\n- Backed up editable source SVGs to `docs/branding/` to preserve future editability, isolating the destructive path conversion.",
          "timestamp": "2026-05-11T00:57:38-07:00",
          "tree_id": "6ba2a3bf15b87f3a79ff985a5f1bd32f7b557616",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/28cbab2d43ce6355dd3af326a59160be3a27d2f8"
        },
        "date": 1778486313945,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 122.37,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 197.07,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "29139614+renovate[bot]@users.noreply.github.com",
            "name": "renovate[bot]",
            "username": "renovate[bot]"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "e17770c87ca959f02bb52b2b45076a90820fd0c4",
          "message": "chore(deps): update github-actions (#77)\n\nCo-authored-by: renovate[bot] <29139614+renovate[bot]@users.noreply.github.com>",
          "timestamp": "2026-06-16T05:58:57-07:00",
          "tree_id": "6596dd903a157e7e7cdcf6b80a0d05fbed264722",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/e17770c87ca959f02bb52b2b45076a90820fd0c4"
        },
        "date": 1781614804857,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 120.18,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 196.21,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "29139614+renovate[bot]@users.noreply.github.com",
            "name": "renovate[bot]",
            "username": "renovate[bot]"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "03625ea61942bc44116efd51ba22f39180948878",
          "message": "chore(deps): lock file maintenance (#81)\n\nCo-authored-by: renovate[bot] <29139614+renovate[bot]@users.noreply.github.com>",
          "timestamp": "2026-06-16T06:12:41-07:00",
          "tree_id": "a2931fe50481ae3b181e91ec973a78285ea8faf9",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/03625ea61942bc44116efd51ba22f39180948878"
        },
        "date": 1781615622847,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 113.27,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 184.25,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "df8e81172b432a961848e6e47b4990bf5220050a",
          "message": "docs: swap hero dark mode asset to favicon and remove deprecated graphic\n\nReplaces the dark-themed hero visual asset `hero-page.svg` with `favicon.svg` within `docs/index.md` to unify light/dark asset tracking, and deletes the unreferenced `docs/assets/hero-page.svg`.",
          "timestamp": "2026-06-16T15:12:59+02:00",
          "tree_id": "2db5c5fbf07e44aeb946d61dcc656ad8f2e13361",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/df8e81172b432a961848e6e47b4990bf5220050a"
        },
        "date": 1781615783367,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 119.24,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 192.68,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "39fe96cebce95d02b99bb1db33e442e1b5ffb568",
          "message": "docs: fix markdown formatting and list spacing in CONTRIBUTING.md",
          "timestamp": "2026-06-16T22:32:19+02:00",
          "tree_id": "7695cb25acd2c933b1b10776d5f2df132be839c1",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/39fe96cebce95d02b99bb1db33e442e1b5ffb568"
        },
        "date": 1781642081192,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 118.01,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 189.57,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "afe4960525230a958ec7d836c11bcb486ac0f3ce",
          "message": "chore(pre-commit): update hook versions\n\n* bump ruff-pre-commit to v0.15.20\n* bump mypy to v2.1.0\n* bump markdownlint-cli2 to v0.22.1\n* bump renovate-config-validator to v43.247.1",
          "timestamp": "2026-06-29T16:39:10+01:00",
          "tree_id": "d37a983fe8df81864d84ba438f42b2bf1f3f5eb3",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/afe4960525230a958ec7d836c11bcb486ac0f3ce"
        },
        "date": 1782749437157,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 117.5,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 189.41,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "5023ddb5822ec5c8fdf379ba411b5d136bbda057",
          "message": "refactor: establish public API facade and centralize package metadata (#90)\n\n- Expose `BootstrapModule`, `EnvironmentManifest`, and `PresetModule` via `__all__` in the root `__init__.py` to provide a clean public API for extensibility.\n- Migrate dynamic `importlib.metadata` version resolution to the package root to comply with PEP 396.\n- Refactor `cli.py` to inherit the `__version__` attribute directly from the root namespace, simplifying parser initialization.",
          "timestamp": "2026-06-30T15:20:25-07:00",
          "tree_id": "710c8528c44b607d2d8889f22bb701c8cc8b4183",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/5023ddb5822ec5c8fdf379ba411b5d136bbda057"
        },
        "date": 1782858080762,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 113.88,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 186.4,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "29139614+renovate[bot]@users.noreply.github.com",
            "name": "renovate[bot]",
            "username": "renovate[bot]"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "71475dbaeee63d023b5736b3e7487c9b2d2a1724",
          "message": "chore(deps): update github-actions to v7 (#92)\n\nCo-authored-by: renovate[bot] <29139614+renovate[bot]@users.noreply.github.com>",
          "timestamp": "2026-07-02T02:38:04Z",
          "tree_id": "c8c0a665de41dba35f19df607fa70f946741cb97",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/71475dbaeee63d023b5736b3e7487c9b2d2a1724"
        },
        "date": 1782959941668,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 125.58,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 211.16,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "8cdf789b39430908ace578ebc4917d761feadcbb",
          "message": "feat: bridge testing coverage gaps and restore codecov enforcement quality gates (#93)\n\n* chore: expand test suite to close coverage gaps in cli and tooling layers\n\n- Add robust pre-flight, collision, and build pipeline verification for DirenvModule, MarkdownLintModule, PytestModule, and PreCommitModule.\n- Add coverage for alternative Python packaging paradigms (uv vs. pip/venv environment hooks configuration).\n- Secure test coverage across argparse table help formatting execution pipelines, verbose telemetry initialization pathways, and interactive TUI routing intercept closures.\n- Fix static type tracking analysis constraints via deliberate explicit casting allocations over internal argparse choices nodes to eliminate mypy resolution issues.\n\n* chore: restore production Codecov metrics and enforcement thresholds\n\nReverts the temporary lockdown of coverage reporting used during the monolithic refactoring phase. Reactivates strict multi-layered validation metrics:\n- Re-enables project-wide baseline evaluation with an auto-target metric and a strict 2% regression constraint envelope.\n- Enforces an 80% localized threshold limit on newly injected code patches to guarantee long-term system stability.\n- Disables explicit pull-request comment noise while anchoring CI status locks onto reporting engine execution states.",
          "timestamp": "2026-07-02T07:35:23-07:00",
          "tree_id": "51fe898071db0ae703e51643a36e8db234734eaf",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/8cdf789b39430908ace578ebc4917d761feadcbb"
        },
        "date": 1783002983939,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 125.52,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 202.96,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "3dfcae4c380b364e0cd0b8bf8d6bbcda345cb330",
          "message": "docs: align README with Python-exclusive architecture\n\nRemoves references to legacy multi-language support, deprecated multi-language\nwizard steps, and the obsolete `--python` CLI flag from the primary documentation\nbenchmarks. Updates developer extension instructions to accurately reflect the\ncurrent role of `BootstrapModule` as a core tooling injection layer rather than\na language configuration layer.",
          "timestamp": "2026-07-02T15:41:35+01:00",
          "tree_id": "91e8af2cd10e8f58b429128c838399fb75a8ff32",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/3dfcae4c380b364e0cd0b8bf8d6bbcda345cb330"
        },
        "date": 1783003354955,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 113.95,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 183.8,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "e4af5e39521e4c9cf5096d3f4d22534318e907f8",
          "message": "chore: bump version 0.7.8 → 0.8.0",
          "timestamp": "2026-07-02T16:04:52+01:00",
          "tree_id": "fb9539378422812748c55230190519231aa9d467",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/e4af5e39521e4c9cf5096d3f4d22534318e907f8"
        },
        "date": 1783004754518,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 116.16,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 189.81,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "2ae67450df7249d6a989226a00d630115e44187a",
          "message": "ci(release): point homebrew sync workflow to @main\n\nUpdates the reusable workflow reference to track the main branch instead of a\npinned commit SHA. This ensures the pipeline receives infrastructure updates\nautomatically, specifically the `brew trust` patch required for CI tap\nauditing.",
          "timestamp": "2026-07-02T16:17:59+01:00",
          "tree_id": "133ea9952010a84c262c969eef4030336b45d27c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/2ae67450df7249d6a989226a00d630115e44187a"
        },
        "date": 1783005548632,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 124.54,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 210.2,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "7616e5c0fc1d108f1b93ffa61988f79926300310",
          "message": "chore: bump version 0.8.0 → 0.8.1",
          "timestamp": "2026-07-02T16:19:01+01:00",
          "tree_id": "21f6141ba8f21b3f679ae7fdd65cb48e1a68d181",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/7616e5c0fc1d108f1b93ffa61988f79926300310"
        },
        "date": 1783005717021,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 124.13,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 204.73,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "36dd9fda4e2689d56540433844df839f74047c97",
          "message": "chore: bump version 0.8.1 → 0.8.2",
          "timestamp": "2026-07-02T18:17:42+01:00",
          "tree_id": "0f94419679d12243b4b5ab858afe8ec2b4a527dd",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/36dd9fda4e2689d56540433844df839f74047c97"
        },
        "date": 1783012798361,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 121.34,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 205.76,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "8892c7b08b852bbce64058ca50706c7a709ed146",
          "message": "refactor: streamline and standardize pre-commit configuration pipeline (#94)\n\n- Strips opinionated comments and implements consistent double-newline block separation across all dynamic pre-commit hook injections.\n- Shuts down dependency inflation inside the isolated mypy hook environment by skipping the development utility group entirely and targeting core production requirements.\n- Cleanly strips out empty `additional_dependencies` blocks when tracking bare-bones workspace initializations.\n- Synchronizes documentation markdown fixtures to match production generator formatting.",
          "timestamp": "2026-07-03T03:30:24-07:00",
          "tree_id": "73afc0c3c41f622ca8b1c932c457fb6edefe3e5a",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/8892c7b08b852bbce64058ca50706c7a709ed146"
        },
        "date": 1783074680446,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 123.55,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 200.21,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "d77aadfeb3b97d6f1802401392834b19267c9cf9",
          "message": "chore(pyproject,ruff): normalize toml formatting and expand lint config\n\nUpdate pyproject.toml for consistency, readability, and a more explicit\nlint configuration.\n\n* Reformat authors and docs arrays into single-line form\n* Normalize spacing in inline table for license field\n* Standardize trailing commas and indentation in multiline arrays\n* Expand Ruff lint rule selection into explicit groups (A, B, C4, D,\n  E, F, I, N, PT, RET, RUF, SIM, T20, UP)\n* Update Ruff configuration comments and grouping for clarity\n* Reformat isort section-order for improved readability\n* Add trailing comma in pytest marker list for consistency",
          "timestamp": "2026-07-05T22:31:44+01:00",
          "tree_id": "6ba2d044d93b01f4385b186d5627f96cb02f9c80",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d77aadfeb3b97d6f1802401392834b19267c9cf9"
        },
        "date": 1783287206895,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 116.41,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 191.98,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "a9796b3d1e7c98b901d8478e7310db4ba7d28089",
          "message": "refactor: update package layout and type exports\n\n- Add py.typed to declare PEP 561 compliance.\n- Remove tests/ and scripts/ __init__.py package markers.\n- Configure explicit_package_bases and mypy_path in mypy.",
          "timestamp": "2026-07-05T22:41:05+01:00",
          "tree_id": "f35e7cd321f9524e843fd805287c86f2a81c5a41",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a9796b3d1e7c98b901d8478e7310db4ba7d28089"
        },
        "date": 1783287777458,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 113.12,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 182.18,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "1c7b80b4ec14897a5b5a56c8a3bf1cd1aa8ca016",
          "message": "refactor: update package layout and type exports\n\n- Add py.typed to declare PEP 561 compliance.\n- Remove tests/ and scripts/ __init__.py package markers.\n- Configure explicit_package_bases and mypy_path in mypy.",
          "timestamp": "2026-07-05T22:57:50+01:00",
          "tree_id": "d9a00b8cd19855463b8694c434a999e32cca7672",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1c7b80b4ec14897a5b5a56c8a3bf1cd1aa8ca016"
        },
        "date": 1783288732064,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 116.02,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 189.38,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "96084bb47cbf86d28d66eda29d669affeee5d905",
          "message": "chore: remove bump-my-version in favor of custom bump task\n\n- Delete `[tool.bumpversion]` configuration from `pyproject.toml`.\n- Remove `bump-my-version` and its unused transient trees from `pyproject.toml` and `uv.lock`.\n- Implement defensive SemVer updater script using `tomlkit` in `scripts/bump.py`.\n- Add robust `just bump <part>` recipe automating fast-forward pulls, lockfile synchronization, and atomic Git tagging/pushing.",
          "timestamp": "2026-07-06T15:04:16+01:00",
          "tree_id": "d02a0ef485c605c81a793dd4f2da338317379a97",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/96084bb47cbf86d28d66eda29d669affeee5d905"
        },
        "date": 1783347074633,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 118.24,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 190.93,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "474b2aa4a0b2f6ac9f8cd16eaebbe681df51a1ee",
          "message": "refactor(config): remove deprecated no-ruff configuration key\n\n- Removed bespoke inversion logic for the legacy `no-ruff` key in the config parser.\n- The `ruff` attribute is now handled exclusively by the generalized `typing.get_type_hints` validation pipeline.\n- Updated `DEFAULT_CONFIG_CONTENT` to use the standard `ruff = false` syntax.\n- Migrated test suite configurations to validate standard `ruff` type-checking and toggle behavior, bypassing the cache with `force_reload=True` for clean reads.",
          "timestamp": "2026-07-07T19:40:14+03:00",
          "tree_id": "4eba45049be329a390c4b4230bcc65dd6fbea2e8",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/474b2aa4a0b2f6ac9f8cd16eaebbe681df51a1ee"
        },
        "date": 1783442481832,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 111.09,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 180.93,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "2936ee0005ee72d060768ec6e8b60ec4126cd2a2",
          "message": "refactor(config): remove deprecated no-ruff configuration key\n\n- Removed bespoke inversion logic for the legacy `no-ruff` key in the config parser.\n- The `ruff` attribute is now handled exclusively by the generalized `typing.get_type_hints` validation pipeline.\n- Updated `DEFAULT_CONFIG_CONTENT` to use the standard `ruff = false` syntax.\n- Migrated test suite configurations to validate standard `ruff` type-checking and toggle behavior, bypassing the cache with `force_reload=True` for clean reads.",
          "timestamp": "2026-07-07T19:44:06+03:00",
          "tree_id": "297078834ad0fd8ae270e9bb0c56caaf0214933d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/2936ee0005ee72d060768ec6e8b60ec4126cd2a2"
        },
        "date": 1783442706860,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 123.64,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 204.96,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "59bcec3bb1ad8667b3eeb0daea26c69dc4998883",
          "message": "chore: optimize local CI pipeline and add fixture drift checks\n\n- Replaced `test-cov` with `test-unit` in the `ci` recipe to bypass\n  slow integration and exhaustive test suites locally.\n- Added a `check-fixtures` target that leverages `docs-fixtures`\n  and evaluates path divergence via `git diff --exit-code`.\n- Integrated `check-fixtures` into `just ci` to halt the pre-push\n  pipeline if auto-generated markdown assets are out of sync.",
          "timestamp": "2026-07-07T19:50:06+03:00",
          "tree_id": "3c508c289e6b9c194415c5bb5b25f5fc87def42d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/59bcec3bb1ad8667b3eeb0daea26c69dc4998883"
        },
        "date": 1783443109953,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 117.06,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 191.27,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "9a62027c890339b06155d5460eb08df0ff9b3ce8",
          "message": "ci: add python 3.13 to test matrix\n\nExpands the GitHub Actions CI matrix to explicitly test against Python\n3.13. This ensures intermediate runtime stability and guarantees coverage\nfor breaking changes or module deprecations introduced in the 3.13 cycle,\npreventing version-specific dependency resolution failures.",
          "timestamp": "2026-07-07T19:54:30+03:00",
          "tree_id": "9c52aaa7bfe230745b7c3216dc8f1ab439dd3b9c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/9a62027c890339b06155d5460eb08df0ff9b3ce8"
        },
        "date": 1783443343197,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 115.52,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 185.72,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "437fe0105d4bbfb1915493cf5d2377a6805a8f25",
          "message": "docs: remove JetBrains from documented IDE options\n\nJetBrains IDEs are not actively scaffolded by Protostar, so\nlisting them in the default config comment and Config docstring\nimplied a support level that doesn’t exist. Remove 'jetbrains'\nfrom the supported IDE string and update the corresponding\ndoc fixture to keep documentation in sync.",
          "timestamp": "2026-07-09T13:48:04+03:00",
          "tree_id": "e2f35c9def26f5408ddd29e5997fbca4aeeabf0f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/437fe0105d4bbfb1915493cf5d2377a6805a8f25"
        },
        "date": 1783594785682,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 121.29,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 193.87,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "6057526a84004c923a3de5e20c72a2467898b830",
          "message": "refactor(core): centralize exception formatting and stabilize subprocess execution (#95)\n\nResolves an issue where brittle string parsing masked network timeouts during dependency resolution. Eliminates premature `sys.exit()` calls in execution leaf nodes, establishing a unified presentation layer at the CLI entry point.\n\n- Removes brittle downstream error scraping in `system.py`.\n- Introduces `ProtostarError` and `ConfigurationError` for semantic error routing.\n- Strips presentation logic (`console.print`, `sys.exit`) from `executor.py` and `config.py`.\n- Centralizes error formatting in `cli.main()` using `rich.panel.Panel` for operational errors and `rich.traceback` for unhandled bugs.\n- Updates the test suite to achieve 100% coverage on the new centralized error architecture.",
          "timestamp": "2026-07-09T11:57:55-07:00",
          "tree_id": "64e679436ee0b1243728ba969c5fb0dc5c436fec",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/6057526a84004c923a3de5e20c72a2467898b830"
        },
        "date": 1783623532551,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 114.89,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 187.58,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "08ac692607eacf5a3e4e801ad57a450ebdd9b9c8",
          "message": "feat(tooling): migrate markdownlint to markdownlint-cli2 and update fixtures\n\nSwaps out the deprecated `markdownlint-cli` implementation for `markdownlint-cli2` within the `MarkdownLintModule`.\n\n- Updates the pre-commit hook repository reference to `DavidAnson/markdownlint-cli2` at `v0.23.0`\n- Migrates the default configuration format from `.markdownlint.yaml` to `.markdownlint-cli2.yaml`\n- Incorporates the `gitignore: true` parser option and nests the lint rules under the required `config:` block\n- Refactors collision checks and file injection bindings to target the new file layout",
          "timestamp": "2026-07-11T13:00:39+03:00",
          "tree_id": "9942a9324ffd3fc9ebecf0e5f00bd5c77a7dd375",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/08ac692607eacf5a3e4e801ad57a450ebdd9b9c8"
        },
        "date": 1783764238409,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 121.96,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 199.52,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "4b03b3e1b4fca385f9d3705f15a9f461504c7d01",
          "message": "feat(tooling): migrate markdownlint to markdownlint-cli2 and update fixtures\n\nSwaps out the deprecated `markdownlint-cli` implementation for `markdownlint-cli2` within the `MarkdownLintModule`.\n\n- Updates the pre-commit hook repository reference to `DavidAnson/markdownlint-cli2` at `v0.23.0`\n- Migrates the default configuration format from `.markdownlint.yaml` to `.markdownlint-cli2.yaml`\n- Incorporates the `gitignore: true` parser option and nests the lint rules under the required `config:` block\n- Refactors collision checks and file injection bindings to target the new file layout",
          "timestamp": "2026-07-11T13:07:27+03:00",
          "tree_id": "115460ca266cd211c6f0bbbb8ef68e804f330fd2",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/4b03b3e1b4fca385f9d3705f15a9f461504c7d01"
        },
        "date": 1783764517242,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 90.79,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 148.38,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "37054ce8f9f17b0406e383c94729d0488d4609d4",
          "message": "feat(tooling): migrate markdownlint to markdownlint-cli2 and update fixtures\n\nSwaps out the deprecated `markdownlint-cli` implementation for `markdownlint-cli2` within the `MarkdownLintModule`.\n\n- Updates the pre-commit hook repository reference to `DavidAnson/markdownlint-cli2` at `v0.23.0`\n- Migrates the default configuration format from `.markdownlint.yaml` to `.markdownlint-cli2.yaml`\n- Incorporates the `gitignore: true` parser option and nests the lint rules under the required `config:` block\n- Refactors collision checks and file injection bindings to target the new file layout",
          "timestamp": "2026-07-11T13:23:31+03:00",
          "tree_id": "c3c87aa260454e8e64ae78886fc9d86507ecf017",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/37054ce8f9f17b0406e383c94729d0488d4609d4"
        },
        "date": 1783765571323,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 113.97,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 181.77,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "d8be5886b96c362c1443e4cc57ac724a441a9b19",
          "message": "fix: update documentation link to stable URL\n\nReplace broken documentation link in README with the correct ReadTheDocs URL and\npoint it to the stable version instead of latest.",
          "timestamp": "2026-07-15T23:07:41+03:00",
          "tree_id": "f17a81cf93e0c7945ada4d530c45e07a9f00c2bd",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d8be5886b96c362c1443e4cc57ac724a441a9b19"
        },
        "date": 1784146129660,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 116.47,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 188.65,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "f5990ad6f8a72d150124ef899aa38647d66f182b",
          "message": "refactor(tooling): strip redundant ClassVar annotations from subclasses\n\nRemoves explicit `ClassVar` typing from all `BootstrapModule` subclasses\nin `src/protostar/modules/tooling_layer.py`.\n\nSince the `BootstrapModule` base class explicitly defines the type contracts\nfor `cli_flags`, `cli_help`, and `config_key`, mypy intrinsically enforces\nthese constraints down the Method Resolution Order (MRO). Repeating the\ntyping in every subclass was just adding unnecessary syntax mass without\nany functional static analysis benefit.\n\nThis change aligns the tooling modules with the preset modules, adhering to\nDRY principles and improving structural readability. (Sorry, Zen of Python,\nbut explicit is not better than implicit when it's just dead weight).",
          "timestamp": "2026-07-15T23:19:37+03:00",
          "tree_id": "27e15058d1eff684e219a4227a3d5ad482423365",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f5990ad6f8a72d150124ef899aa38647d66f182b"
        },
        "date": 1784146877868,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 115.44,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 188.91,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "0b8fa59f10abf723ff3a02c0baedf21f620e973a",
          "message": "docs: fix broken documentation links",
          "timestamp": "2026-07-17T12:09:30+01:00",
          "tree_id": "cc5153c978a4fff60dc7d18d5cb38cd5abf52445",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/0b8fa59f10abf723ff3a02c0baedf21f620e973a"
        },
        "date": 1784286662112,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 118.99,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 201.55,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "544a0458cf0b5272aeccdbb50872646405417b4a",
          "message": "feat(core): decouple developer telemetry from user-facing diagnostics (#107)\n\nRestructures the logging and notification architecture to prevent unformatted stderr leakage and enforce a clean CLI UX. \n\n- Injects a `NullHandler` to silence the root logger by default.\n- Introduces a `DiagnosticEvent` dataclass and a centralized collector in `EnvironmentManifest`.\n- Routes config fallbacks, module execution skips, and disk I/O anomalies to the diagnostic state object instead of stdout/stderr.\n- Implements a color-coded `rich.Panel` in the Orchestrator to summarize aggregated anomalies post-execution.\n- Migrates the unit test suite to utilize deterministic, state-based assertions instead of mock-based I/O intercepts.",
          "timestamp": "2026-07-17T04:14:36-07:00",
          "tree_id": "da7381f4d95207d32aa34c0936f9a6eb696f3b5c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/544a0458cf0b5272aeccdbb50872646405417b4a"
        },
        "date": 1784286930105,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 117.56,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 186.69,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "ae052cd0b289a93a6fe28b470b0dab295a1d25f9",
          "message": "chore(scripts): isolate doc fixture generation from host config\n\nInject temporary `$HOME` and `$XDG_CONFIG_HOME` paths into the isolated environment to sandbox subprocess execution, preventing local user configurations from bleeding into generated artifacts. Additionally, monkeypatch `CONFIG_FILE` and clear the `ProtostarConfig` singleton cache at runtime to ensure in-process manifest generation strictly adheres to default state.\n\nThis guarantees deterministic documentation payloads regardless of the host environment and prevents transient parsing warnings from polluting the generated markdown files.",
          "timestamp": "2026-07-17T12:26:00+01:00",
          "tree_id": "d45cff313a578cc60386da62ac20cd860f12ad56",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/ae052cd0b289a93a6fe28b470b0dab295a1d25f9"
        },
        "date": 1784287627837,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 112.31,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 178.71,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "f7b087f4d68a9ee5d25054432331fc4c40879686",
          "message": "feat: verify recommended VS Code and Cursor extensions post-install\n\nIntroduces a non-blocking diagnostic phase that check if recommended\nIDE extensions matching the active tooling modules (e.g., Ruff, Mypy,\nMarkdownLint) are installed when `config.ide` is configured.\n\n- Updates `EnvironmentManifest` to aggregate target extension IDs.\n- Hooks `MarkdownLintModule`, `RuffModule`, and `MypyModule` to register\n  their upstream extension vectors.\n- Appends `_check_ide_extensions` to the end of the `SystemExecutor`\n  pipeline, using `code` or `cursor` CLI binaries to parse installed\n  packages.\n- Adheres to the side-effect isolation guardrail by executing late in\n  the lifecycle and failing silently on system timeouts or missing CLI\n  path states, bubbling anomalies exclusively via `DiagnosticEvent`.",
          "timestamp": "2026-07-17T12:29:16+01:00",
          "tree_id": "38f4db2f9337e38555b694bbc463288442d52b63",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f7b087f4d68a9ee5d25054432331fc4c40879686"
        },
        "date": 1784287825648,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 116.5,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 190.96,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "440da5fac1a78dba4ebebf0d956829af730c7ac1",
          "message": "feat: verify recommended VS Code and Cursor extensions post-install\n\nIntroduces a non-blocking diagnostic phase that check if recommended\nIDE extensions matching the active tooling modules (e.g., Ruff, Mypy,\nMarkdownLint) are installed when `config.ide` is configured.\n\n- Updates `EnvironmentManifest` to aggregate target extension IDs.\n- Hooks `MarkdownLintModule`, `RuffModule`, and `MypyModule` to register\n  their upstream extension vectors.\n- Appends `_check_ide_extensions` to the end of the `SystemExecutor`\n  pipeline, using `code` or `cursor` CLI binaries to parse installed\n  packages.\n- Adheres to the side-effect isolation guardrail by executing late in\n  the lifecycle and failing silently on system timeouts or missing CLI\n  path states, bubbling anomalies exclusively via `DiagnosticEvent`.",
          "timestamp": "2026-07-17T12:29:52+01:00",
          "tree_id": "a108b8bf2e19cd3a2cc2d70727ad2738395a037c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/440da5fac1a78dba4ebebf0d956829af730c7ac1"
        },
        "date": 1784287856036,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 111.54,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 181.63,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "6832684861d5a716b5e6548530fbb6c0ca396506",
          "message": "feat: verify recommended VS Code and Cursor extensions post-install\n\nIntroduces a non-blocking diagnostic phase that check if recommended\nIDE extensions matching the active tooling modules (e.g., Ruff, Mypy,\nMarkdownLint) are installed when `config.ide` is configured.\n\n- Updates `EnvironmentManifest` to aggregate target extension IDs.\n- Hooks `MarkdownLintModule`, `RuffModule`, and `MypyModule` to register\n  their upstream extension vectors.\n- Appends `_check_ide_extensions` to the end of the `SystemExecutor`\n  pipeline, using `code` or `cursor` CLI binaries to parse installed\n  packages.\n- Adheres to the side-effect isolation guardrail by executing late in\n  the lifecycle and failing silently on system timeouts or missing CLI\n  path states, bubbling anomalies exclusively via `DiagnosticEvent`.",
          "timestamp": "2026-07-17T12:36:13+01:00",
          "tree_id": "9862fac8d61a4e9063bd1abbed150168c0fb6b7d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/6832684861d5a716b5e6548530fbb6c0ca396506"
        },
        "date": 1784288236511,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 116.34,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 187.28,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "127add52622920ca61252b481d65d35596364568",
          "message": "refactor: enforce strict uv architecture and remove pip support (#108)\n\nThis commit drops `pip` as a supported package manager to reduce architectural branching logic and enforce a deterministic, high-velocity execution pipeline.\n\n- Removed `python_package_manager` from `ProtostarConfig`.\n- Locked `PythonCore` to `uv init` and stripped Python/pip system requirements.\n- Removed `pip` subprocess execution, exception handling, and `requirements.txt` freezing from `SystemExecutor`.\n- Removed `.venv/pyvenv.cfg` regex fallback parsing for Python version resolution.\n- Hardcoded `uv sync` and `uv run` commands into `direnv`, `pre-commit`, and `nbdime` tooling.\n- Cleaned up obsolete `pip` branches and mocks from the test suite.",
          "timestamp": "2026-07-17T05:19:10-07:00",
          "tree_id": "f390d3085a895f1918f00110323c52146254d6d0",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/127add52622920ca61252b481d65d35596364568"
        },
        "date": 1784290803232,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 116.99,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 187.02,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "3ec25640fec8f00372b8baabba502088926e3d10",
          "message": "fix: cap GitHub issue traceback to 10 frames\n\nRestricts the serialized telemetry string used for automated GitHub\nissue generation to a maximum depth of 10 frames. This mirrors the visual\nlimit enforced by the Rich console and prevents unhandled errors with\ndeep execution stacks from generating URL query strings that exceed maximum\nbrowser or proxy length thresholds (~8KB).",
          "timestamp": "2026-07-17T13:40:41+01:00",
          "tree_id": "01b731921b25b1ee87fde6c8c334ee80c2e448b8",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/3ec25640fec8f00372b8baabba502088926e3d10"
        },
        "date": 1784292108915,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 119.68,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 198.2,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "268bb42fdaeb5b24ad00053cb7efe287c78e6baf",
          "message": "refactor: implement domain-specific exception hierarchy (#109)\n\n- Introduce typed exception subclasses for dependency, command execution, timeout, and filesystem failures.\n- Add structured 'hint' support to ProtostarError base class for consistent user-facing remediation.\n- Export expanded error vocabulary from package root for plugin stability.\n- Add comprehensive unit testing for exception metadata integrity and formatting.\n\nThis commit sets the architectural foundation for structured error handling, \nreplacing brittle, coincidental string matching of base RuntimeError/OSError \nwith explicit, domain-modeled exception types.",
          "timestamp": "2026-07-17T05:55:44-07:00",
          "tree_id": "4bf41accb8c7f3b67479bd6662e97fc845ba6bc9",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/268bb42fdaeb5b24ad00053cb7efe287c78e6baf"
        },
        "date": 1784293001621,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 126.98,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 208.95,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "5c22f0d9ef9b073b8e62adf501f912689a62903b",
          "message": "refactor: migrate subprocess runner to typed exceptions (#110)\n\n- Replace generic RuntimeError calls with CommandTimeoutError and CommandExecutionError.\n- Enforce strict exception chaining on subprocess timeouts and failure terminations.\n- Retain structural verification integrity by storing raw stdout/stderr streams.\n- Refactor test_system to evaluate explicit exception attributes instead of error strings.",
          "timestamp": "2026-07-17T06:06:14-07:00",
          "tree_id": "d17d03e728881f6bc11fcc28e662425ddf48e627",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/5c22f0d9ef9b073b8e62adf501f912689a62903b"
        },
        "date": 1784293627855,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 116.33,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 189.01,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "b6ea0fc99c61f7f6a2c90d9db3d772b9a10d8145",
          "message": "refactor: standardize pre-flight checks with MissingDependencyError (#111)\n\n* refactor: raise MissingDependencyError for absent uv binary in lang layer\n\nUpdates PythonCore.pre_flight to drop generic RuntimeError strings, raising a\nstructured MissingDependencyError instead. Isolates the binary identity, its\noperational target purpose, and terminal installation context fields.\n\n* refactor: raise MissingDependencyError for missing tools in tooling layer\n\nRefactors the pre-flight checks inside DirenvModule and PreCommitModule to\nleverage structured MissingDependencyError definitions instead of coarse\nRuntimeError statements.\n\n* test: fix pre-flight test assertions to expect MissingDependencyError\n\nRefactors existing test cases in test_modules.py that checked for legacy\nRuntimeErrors. Updates them to expect MissingDependencyError and asserts\nagainst their inner metadata attributes.",
          "timestamp": "2026-07-17T06:17:08-07:00",
          "tree_id": "1573bb5054457e2dc3224febc7d5a2468ae72452",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/b6ea0fc99c61f7f6a2c90d9db3d772b9a10d8145"
        },
        "date": 1784294278303,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 93.82,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 151.93,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "f7e348b8e77225277444a913b74411699a5cf75a",
          "message": "refactor: wrap execution mutations with contextual FileSystemError (#4) (#112)\n\n* refactor: wrap file injections and directory setup with FileSystemError\n\nIntroduces OSError try-catch defensive blocks surrounding file injections,\ndirectory construction, and pre-commit YAML scaffolding mutations. Converts\nbare system exceptions cleanly into contextual FileSystemError definitions.\n\n* refactor: secure configuration file appends and syncs via FileSystemError\n\nApplies strict exception isolation blocks across late-binding configuration\nappends, .gitignore expansions, container optimizations, and local vscode\nsettings workspace sync adjustments.\n\n* test: create executor filesystem boundary mutation test coverage\n\nAdds explicit validation checks asserting that SystemExecutor converts typical\nlow-level OSError parameters (PermissionError, space allocation faults) smoothly\ninto contextualized, structural FileSystemError variants.\n\n* docs: update fixtures\n\n* test: achieve 100% test coverage for executor I/O exceptions\n\nIntroduces comprehensive mock boundary tests mapping to every unique\nFileSystemError context string variant in executor.py. Uses pytest-mock\nto simulate systemic disk full, permission denied, and hardware I/O\nfailures across appends, workspace ignores, container definitions, and\nIDE preference layouts to satisfy codecov validation targets.",
          "timestamp": "2026-07-17T06:46:22-07:00",
          "tree_id": "c891f3ba34feddb15071d2569dbcb9ee1402f4c4",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f7e348b8e77225277444a913b74411699a5cf75a"
        },
        "date": 1784296041022,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 116.18,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 191.37,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "74b57d2813b73ffb64f81787c7edbac178c88dd3",
          "message": "refactor: wrap execution mutations with contextual FileSystemError (#112)\n\n* refactor: wrap file injections and directory setup with FileSystemError\n\nIntroduces OSError try-catch defensive blocks surrounding file injections,\ndirectory construction, and pre-commit YAML scaffolding mutations. Converts\nbare system exceptions cleanly into contextual FileSystemError definitions.\n\n* refactor: secure configuration file appends and syncs via FileSystemError\n\nApplies strict exception isolation blocks across late-binding configuration\nappends, .gitignore expansions, container optimizations, and local vscode\nsettings workspace sync adjustments.\n\n* test: create executor filesystem boundary mutation test coverage\n\nAdds explicit validation checks asserting that SystemExecutor converts typical\nlow-level OSError parameters (PermissionError, space allocation faults) smoothly\ninto contextualized, structural FileSystemError variants.\n\n* docs: update fixtures\n\n* test: achieve 100% test coverage for executor I/O exceptions\n\nIntroduces comprehensive mock boundary tests mapping to every unique\nFileSystemError context string variant in executor.py. Uses pytest-mock\nto simulate systemic disk full, permission denied, and hardware I/O\nfailures across appends, workspace ignores, container definitions, and\nIDE preference layouts to satisfy codecov validation targets.",
          "timestamp": "2026-07-17T15:03:37+01:00",
          "tree_id": "c891f3ba34feddb15071d2569dbcb9ee1402f4c4",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/74b57d2813b73ffb64f81787c7edbac178c88dd3"
        },
        "date": 1784297156719,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 116.91,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 191.66,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "d106943f6f369c923f327a859cd8f453ead3f4f3",
          "message": "refactor: finalize centralized error control, POSIX tracking, and documentation (#113)\n\n- Narrow cli.main intercept boundaries to catch ProtostarError variants exclusively.\n- Implement isolated, dim terminal block formatting for decoupled validation hints.\n- Map system failures directly onto standard UNIX constants (EX_CONFIG, EX_UNAVAILABLE, EX_IOERR).\n- Route unexpected internal crashes to EX_SOFTWARE with truncated issue URL parameters.\n- Add robust verification conditions to test_cli and document conventions in CONTRIBUTING.md.\n- Update MkDocs architectural documentation (executor.md, orchestrator.md) to reflect strict error typing.\n- Inject ProtostarError hierarchy into the auto-generated api-reference.md for plugin developers.",
          "timestamp": "2026-07-17T07:39:14-07:00",
          "tree_id": "e2821f223bfe737b18aacd0116d2f97816dd1e72",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d106943f6f369c923f327a859cd8f453ead3f4f3"
        },
        "date": 1784299215802,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 112.19,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 181.76,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "distinct": true,
          "id": "f1414571be58cb7fef2ea83a0a75fd1b0da5bbc1",
          "message": "fix: catch CommandExecutionError/CommandTimeoutError instead of RuntimeError in dependency install, surface stdout/stderr in error panel",
          "timestamp": "2026-07-17T12:38:00-04:00",
          "tree_id": "89c9537fe93aca8e7e6f223ac8b53a91ae0ec958",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f1414571be58cb7fef2ea83a0a75fd1b0da5bbc1"
        },
        "date": 1784306344833,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 116.57,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 187.28,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "67037e44b3d5116b4bd1c2966c059e142ce6a52c",
          "message": "feat: implement --from flag for portable environments and templated configurations (#114)\n\nIntroduces the ability to scaffold environments using portable TOML specifications \nvia local file paths or remote HTTPS URLs, complete with an interactive fallback \nwizard for template variables.\n\n- Expands `ProtostarConfig` schema to support `[files]` and `[variables]`.\n- Implements `network.py` to fetch remote configs, enforcing HTTPS and automating GitHub/GitLab blob-to-raw URL translation.\n- Adds `templating.py` to perform AST-safe variable interpolation for `{{placeholders}}` prior to TOML parsing.\n- Updates `cli.py` with `parse_known_args()` to capture dynamic variable overrides (e.g., `--project_name=orbit`).\n- Integrates a `questionary` wizard to prompt for unresolved variables, strictly aborting in non-interactive CI environments.\n- Bridges configuration file payloads directly into the `EnvironmentManifest` execution pipeline.\n- Expands the test suite with strict disk I/O and network boundary mocking.",
          "timestamp": "2026-07-17T19:02:39-07:00",
          "tree_id": "36e5bd7208ef24f62ae6bd6f2fd95e8bee970a04",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/67037e44b3d5116b4bd1c2966c059e142ce6a52c"
        },
        "date": 1784340213956,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 116.23,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 186.5,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jackson.ferguson0@gmail.com",
            "name": "Jackson Ferguson",
            "username": "JacksonFergusonDev"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "adee0deb40f50b0b537614fe0441b40b188dad32",
          "message": "refactor: decouple config loading from interactive wizard (#115)\n\nReplace the direct wizard call in config.py with a variable_resolver\ncallback pattern. This restores a clean layered architecture where\nthe configuration module (a pure data layer) never depends on UI code.\nThe CLI orchestrator now injects the interactive resolver, keeping the\ndependency direction one-way and enabling independent testing.",
          "timestamp": "2026-07-17T19:34:23-07:00",
          "tree_id": "ba1ab24a47c172731db0ec70d0369d9eddf432d8",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/adee0deb40f50b0b537614fe0441b40b188dad32"
        },
        "date": 1784342117987,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 123.08,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 191.25,
            "unit": "ms"
          }
        ]
      }
    ]
  }
}