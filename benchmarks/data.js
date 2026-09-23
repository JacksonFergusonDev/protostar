window.BENCHMARK_DATA = {
  "lastUpdate": 1790199457822,
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
          "id": "08bba6887435875f47f2f5fd7e332968933292da",
          "message": "build(justfile): enable strict shell options globally\n\n- Set `-e` (errexit) and `-o pipefail` in the global shell configuration\n  to ensure recipes abort on command failures and pipeline errors.\n- Remove redundant `set -euo pipefail` from the `bump` recipe since\n  the global shell now provides the strict behavior.\n\nThis improves safety and consistency across all just recipes.",
          "timestamp": "2026-07-29T15:05:17-07:00",
          "tree_id": "0fd97605a7279bf794d71926551d3715e12b434c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/08bba6887435875f47f2f5fd7e332968933292da"
        },
        "date": 1785362791995,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 127.68,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 198.67,
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
          "id": "f740866032cf870f54935f909a2af0cd36064b42",
          "message": "**chore(codecov): relax patch coverage enforcement**\n\nLower the patch coverage target and make patch coverage\ninformational to reduce friction for small PRs while keeping\ncoverage reports visible.",
          "timestamp": "2026-07-29T16:33:46-07:00",
          "tree_id": "a5b3fe89f29be344a08efd724fcf32ade40ca6f2",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f740866032cf870f54935f909a2af0cd36064b42"
        },
        "date": 1785368155396,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 122.17,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 186.96,
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
          "id": "6198e4de8f4c7dd1a3853b1d3a35ea61b0adbf2d",
          "message": "chore(codecov): relax patch coverage enforcement\n\nLower the patch coverage target and make patch coverage\ninformational to reduce friction for small PRs while keeping\ncoverage reports visible.",
          "timestamp": "2026-07-29T16:35:22-07:00",
          "tree_id": "a5b3fe89f29be344a08efd724fcf32ade40ca6f2",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/6198e4de8f4c7dd1a3853b1d3a35ea61b0adbf2d"
        },
        "date": 1785368208410,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 128.98,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 196.99,
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
          "id": "1f481a1633fcc34b8aba69c8d069865f5d0b7dfb",
          "message": "fix: expose subprocess telemetry in non-fatal diagnostic payloads (#118)\n\n- Adds `output_detail` property to `CommandExecutionError` to encapsulate stdout/stderr formatting.\n- Refactors fatal error handling in `cli.py` to use the new `output_detail` property.\n- Pipes the formatted detail payload into `add_diagnostic` during `uv add` execution failures.\n- Updates the `Orchestrator` to render the `detail` string inside the diagnostic summary panel.\n- Replaces the bare `except Exception: pass` in `_check_ide_extensions` with a logged `Severity.SKIP` diagnostic.",
          "timestamp": "2026-07-29T16:44:36-07:00",
          "tree_id": "d80ec4a495a6271748ba29a1fe519933f6619cd0",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1f481a1633fcc34b8aba69c8d069865f5d0b7dfb"
        },
        "date": 1785368733704,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 128.85,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 193.27,
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
          "id": "d2ce7bf06e47d2bb7f24c6bfaca2d8cbe5584c74",
          "message": "build(deps): replace pre-commit with prek\n\nSwap pre-commit for prek (>=0.4.11) in pyproject.toml and update uv.lock.\nprek serves as a drop-in Rust replacement to speed up hook execution and\neliminate virtualenv/cfgv/identify dependencies.",
          "timestamp": "2026-07-29T17:22:31-07:00",
          "tree_id": "f3807f831f2bc0bb325d6749a0f7a453d3ce4f46",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d2ce7bf06e47d2bb7f24c6bfaca2d8cbe5584c74"
        },
        "date": 1785371028915,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 130.02,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 206.5,
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
          "id": "ab8e71d3fbcdc4a177516642b402a78b8329970b",
          "message": "build(deps): replace pre-commit with prek\n\nSwap pre-commit for prek (>=0.4.11) in pyproject.toml, update\nCONTRIBUTING.md, and update uv.lock. prek serves as a drop-in\nRust replacement to speed up hook execution and eliminate\nvirtualenv/cfgv/identify dependencies.",
          "timestamp": "2026-07-29T17:39:29-07:00",
          "tree_id": "532d41931d76e8b840a5b11fa7387f7f7028dad6",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/ab8e71d3fbcdc4a177516642b402a78b8329970b"
        },
        "date": 1785372086235,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 122.96,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 188.38,
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
          "id": "74ed462113c11ee1ca058505cbe3ce5c32d18a98",
          "message": "feat(executor): implement logical OR fallbacks for IDE extensions (#119)\n\n* feat(executor): implement logical OR fallbacks for IDE extensions\n\nUpdates the `EnvironmentManifest` to accept tuples within the `ide_extensions`\nset, allowing modules to define acceptable alternative extensions. The\n`SystemExecutor` now evaluates tuples using an `any()` check against the\ninstalled extensions array, outputting a cleanly formatted 'or' diagnostic\nif the dependency group is unfulfilled.\n\nUpdates the `MypyModule` to accept either `ms-python.mypy-type-checker` or\nthe popular community alternative `matangover.mypy`.\n\n* test(modules): update mypy extension assertions and add fallback coverage\n\nFixes `test_mypy_module_injects_ide_extension` in `tests/test_modules.py`\nto assert against the new fallback tuple `(\"ms-python.mypy-type-checker\",\n\"matangover.mypy\")`.\n\nAdds unit tests in `tests/test_executor.py` and `tests/test_manifest.py` to:\n- Verify primary and fallback extensions satisfy the IDE check in `SystemExecutor`.\n- Ensure unfulfilled extension tuples generate a formatted diagnostic using 'or'.\n- Confirm `EnvironmentManifest` accepts both string and tuple extension types.",
          "timestamp": "2026-07-29T17:56:39-07:00",
          "tree_id": "0886606a12c2cd4f0f8640fd75adc56ffe17e430",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/74ed462113c11ee1ca058505cbe3ce5c32d18a98"
        },
        "date": 1785373056580,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 126.92,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 193.14,
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
          "id": "e53dcbed4a120364c425f9be3ec26deecc0ac7d1",
          "message": "fix(cli): allow trailing global flags and correct help menu capitalization (#120)\n\nExtracted global flags (`--version`, `--verbose`) into a shared `base_parser` \nand inherited them across the root parser and all subparsers. This resolves \nthe argparse limitation where global flags placed after a subcommand throw \nan 'unrecognized arguments' error. The `default=argparse.SUPPRESS` kwarg \nwas also applied to prevent subparsers from inadvertently overwriting the \nparsed root namespace.\n\nAdditionally, updated the custom Rich table formatter to explicitly \ncapitalize the default argparse 'options' group, restoring visual parity \nbetween the root and subcommand help menus. Test coverage was expanded \nto explicitly validate the positional independence of global flags.",
          "timestamp": "2026-07-29T18:22:49-07:00",
          "tree_id": "ed17c85d29fdc1fb093727e34a0788270e699cb2",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/e53dcbed4a120364c425f9be3ec26deecc0ac7d1"
        },
        "date": 1785374627753,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 125.74,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 189.95,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "198982749+Copilot@users.noreply.github.com",
            "name": "Copilot",
            "username": "Copilot"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "a60356a689f163aa719c31d2badf73a54da69290",
          "message": "refactor: adopt atomic file writes (#121)\n\nCo-authored-by: copilot-swe-agent[bot] <198982749+Copilot@users.noreply.github.com>",
          "timestamp": "2026-07-29T22:34:14-07:00",
          "tree_id": "a656a5971bd2a376523c095e53ca3daddb5e93df",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a60356a689f163aa719c31d2badf73a54da69290"
        },
        "date": 1785389710107,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 124.28,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 193.25,
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
          "id": "974cde1706702421e154cb0ab5a1dabf47caad9f",
          "message": "chore(deps): pin dependencies (#91)\n\nCo-authored-by: renovate[bot] <29139614+renovate[bot]@users.noreply.github.com>",
          "timestamp": "2026-07-30T20:29:38Z",
          "tree_id": "08fa9f113f7fd4008a4a205896faba2fa77ff268",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/974cde1706702421e154cb0ab5a1dabf47caad9f"
        },
        "date": 1785443433577,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 127.89,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 193.2,
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
          "id": "b8c1b85a7e5f7b66bf6b4f3f84eaaa4b0564fcdb",
          "message": "refactor: enforce strict configuration schema validation (#122)\n\nReplaces the permissive warning-and-fallback mechanism in ProtostarConfig with strict schema enforcement, aligning with the fail-loud architectural principle.\n\n- Removed `_parsing_warnings` from `ProtostarConfig`.\n- Config parser now raises `ConfigurationError` on type mismatches, unknown root keys, and unexpected parsing errors.\n- Removed obsolete warning evaluation from the Orchestrator lifecycle.\n- Rewrote config tests to assert strict exception raising and fixed non-deterministic set ordering in regex assertions.\n- Replaced warning transfer test in orchestrator with a pristine execution test.",
          "timestamp": "2026-07-30T21:44:56-07:00",
          "tree_id": "77564546984a2ad4cc03c391ba8577c3009783d7",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/b8c1b85a7e5f7b66bf6b4f3f84eaaa4b0564fcdb"
        },
        "date": 1785473159271,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 139.56,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 204.26,
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
          "id": "86242d341b98b9e89c16e5a6265b3034d778989d",
          "message": "feat(cli): add `--reset` flag with confirmation prompt to `protostar config` (#123)\n\nAllows users to reset their global configuration file (~/.config/protostar/config.toml)\nto its default state via `protostar config --reset`.\n- Prompt user for confirmation before resetting existing configuration data.\n- Support `-f`/`--force` flag on `protostar config` to bypass confirmation prompt.\n- Add unit test suite in `tests/test_cli.py` covering prompt confirmation, cancellation, and force flag behavior.",
          "timestamp": "2026-07-30T22:05:24-07:00",
          "tree_id": "115b762086d810653d18cff0d03fc3b1ec7a54af",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/86242d341b98b9e89c16e5a6265b3034d778989d"
        },
        "date": 1785474379382,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 121.75,
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
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "96dd770d18ec461f4923c36a33a76885462ca077",
          "message": "docs: synchronize documentation with codebase and fix drift (#124)\n\n- Added missing `REST API` and `CLI Application` presets to the README.md\n- Removed deprecated `--python` flag from documentation examples and CLI epilog, as Python is now an implicitly loaded mandatory layer\n- Removed the deprecated \"Generating Boilerplate\" section and `generate` subcommand references from getting-started.md",
          "timestamp": "2026-07-30T22:46:45-07:00",
          "tree_id": "f576185317fad938a9ce2fc37100c8eedde1a9aa",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/96dd770d18ec461f4923c36a33a76885462ca077"
        },
        "date": 1785476866803,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 126.11,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 193.07,
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
          "id": "d1989bc8140ee03bbcb60ca2514bf16bc4d8db3a",
          "message": "chore(deps): update davidanson/markdownlint-cli2-action action to v24 (#125)\n\nCo-authored-by: renovate[bot] <29139614+renovate[bot]@users.noreply.github.com>",
          "timestamp": "2026-08-01T10:02:41Z",
          "tree_id": "c6302c95517d82e8fbc5750f31685d64656519af",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d1989bc8140ee03bbcb60ca2514bf16bc4d8db3a"
        },
        "date": 1785578607656,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 98.47,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 149.62,
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
          "id": "6e1c86b681721f81c79310ae5fc8ba2c65b1e689",
          "message": "chore: bump version to 0.8.3",
          "timestamp": "2026-08-09T19:02:04-07:00",
          "tree_id": "414db6b85aa0bb8ded8e03b5727fcdd2e8ead97d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/6e1c86b681721f81c79310ae5fc8ba2c65b1e689"
        },
        "date": 1786327380145,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 123.07,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 190.34,
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
          "id": "20adfb3e62056a4cc664280050e10d7773bd1d0d",
          "message": "chore: remove redundant local update_homebrew script\n\nEliminates `scripts/update_homebrew.py` and its corresponding\nunit test module. Release pipelines now exclusively delegate\nHomebrew formula synchronization to the reusable\n`update-homebrew.yml` workflow provided by\n`JacksonFergusonDev/ci-cd-tooling`.",
          "timestamp": "2026-08-10T10:45:15-07:00",
          "tree_id": "ebc2b24a945e66808e4c7aa880c42603c3664835",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/20adfb3e62056a4cc664280050e10d7773bd1d0d"
        },
        "date": 1786384061754,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 135.69,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 207.63,
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
          "id": "8c63821be3d66b6d8fe379986add8d2515d07330",
          "message": "chore: delegate version bumping to remote ci-cd-tooling script\n\nRemoves the local `scripts/bump.py` and updates the `justfile` bump\nrecipe to invoke the centralized script directly from\n`JacksonFergusonDev/ci-cd-tooling` via `uv run`.",
          "timestamp": "2026-08-10T11:00:10-07:00",
          "tree_id": "b3a13eed95b720eeb380748b253a557f20518422",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/8c63821be3d66b6d8fe379986add8d2515d07330"
        },
        "date": 1786384915299,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 142.06,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 222.49,
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
          "id": "f71295b7bd50fe8b05bac859c870b0d442d71029",
          "message": "docs(config): document portable configurations and --from flag (#126)\n\n- Add Portable Configurations usage guide and template authoring specs to docs/usage/configuration.md\n- Add internal mechanics documentation in docs/mechanics/portable_configurations.md explaining remote fetching, dynamic templating, and AST config merging\n- Update mkdocs.yml navigation tree to expose Portable Configurations under Mechanics",
          "timestamp": "2026-08-11T16:05:01-07:00",
          "tree_id": "a6434257f8dd3db11154c9ffd84fd01badbcd97c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f71295b7bd50fe8b05bac859c870b0d442d71029"
        },
        "date": 1786489568721,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 132.91,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 202.99,
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
          "id": "7cdd790f2f9c0f12de2b0d0686339522af191a6b",
          "message": "feat(templates): implement opinionated templates and tri-state CLI toggling (#128)\n\n- Add `--template` flag for built-in turnkey environments (astro, cli)\n- Add interactive TUI prompt for template selection in `wizard.py`\n- Add `active_presets` parsing with strict validation in `config.py` to prevent global contamination\n- Refactor CLI booleans to `BooleanOptionalAction` to support template overriding via `--no-<flag>`\n- Rename `templating.py` to `interpolation.py` to prevent namespace collision\n- Document templates across README, usage, and mechanics for all user personas\n- Remove `{{VAR}}` interpolation footgun from `astro.toml`\n- Sync test suites and `docs/includes` fixtures",
          "timestamp": "2026-08-11T20:59:41-07:00",
          "tree_id": "a2ce6f93e2f4f46918515b768804237a98449a16",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/7cdd790f2f9c0f12de2b0d0686339522af191a6b"
        },
        "date": 1786507239628,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 129.82,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 193.3,
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
          "id": "90a63f667400005aa93bf870ba32fecdf4bc4100",
          "message": "refactor(interpolation): disambiguate load-time config variable syntax from late-binding tokens (#129)\n\n* Fix #127: Disambiguate interpolation syntax for config variables vs. late-binding tokens\n\n* Fix tests for new interpolation syntax",
          "timestamp": "2026-08-11T21:18:29-07:00",
          "tree_id": "8fb9aafec843e9880963b5edfa204e8ad0d12d70",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/90a63f667400005aa93bf870ba32fecdf4bc4100"
        },
        "date": 1786508361357,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 103.29,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 160.78,
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
          "id": "61e58c82d55bf19288486b290d9ed5f41bbf8472",
          "message": "fix(tests): isolate subprocess environment from CI leaks in integration tests\n\nPopped `VIRTUAL_ENV`, `XDG_CACHE_HOME`, `PRE_COMMIT_HOME`, and `GIT_CONFIG_*`\nfrom the mocked environment in the `run_cli` test fixture.\n\nThis resolves transient failures in `test_pre_commit_lifecycle_integration`\ncaused by parallel CI runners sharing the global pre-commit cache, which\nled to race conditions and corrupted `.pre-commit-hooks.yaml` reads during\n`uv run pre-commit autoupdate`. This also resolves the `uv` warnings about\nmismatched active virtual environments.",
          "timestamp": "2026-08-11T21:27:44-07:00",
          "tree_id": "5892358b1964795d51c31c7ead80eb1d68fc5b37",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/61e58c82d55bf19288486b290d9ed5f41bbf8472"
        },
        "date": 1786508923754,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 125.41,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 191.5,
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
          "id": "5004a28f6de8d05e658aa1ca947a6a22f796ef36",
          "message": "feat: expand --from flag support to Bitbucket, Codeberg, and Sourcehut (#130)\n\n* feat: add Bitbucket, Codeberg, and Sourcehut to fetch_remote_config\n\n* test: add tests for Bitbucket, Codeberg, and Sourcehut url translation\n\n* docs: document supported git providers for the --from flag",
          "timestamp": "2026-08-11T21:40:06-07:00",
          "tree_id": "29cad4166647310c26720ce53a07f6e5aa56bbd7",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/5004a28f6de8d05e658aa1ca947a6a22f796ef36"
        },
        "date": 1786509666997,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 135.89,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 210.34,
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
          "id": "7496fabdc2f0f1ff0e0f76f0d1c3254be26a955f",
          "message": "refactor: remove redundant ignore = [] from Ruff configuration\n\nRuff's default value for `ignore` is already an empty list, making explicit assignment unnecessary.\n\nThis commit cleans up the default `pyproject.toml` generated by the tooling layer, updates the corresponding documentation examples, and removes the outdated key assertion from the executor tests.",
          "timestamp": "2026-08-11T21:48:47-07:00",
          "tree_id": "24557a7e14041e59c7e8e109e919755f5ce32fe3",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/7496fabdc2f0f1ff0e0f76f0d1c3254be26a955f"
        },
        "date": 1786510186782,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 99.7,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 152.51,
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
          "id": "f0940c6f6c2fb38c764ce2a58a6492faa25ad376",
          "message": "docs: document missing CLI flags and config commands\n\nDocument previously undocumented and weakly documented features across\nthe README and official documentation:\n- Document `protostar config --reset` and `--force` in configuration.md\n- Document `--crash-test` telemetry simulation flag in testing.md\n- Document `--force` / `-f` headless collision bypass in README.md and init.md\n- Document `--python-version` CLI overrides in README.md and init.md\n- Document `--verbose` / `-v` global debug flag in README.md and init.md",
          "timestamp": "2026-08-11T22:05:02-07:00",
          "tree_id": "4e9484e15c258ff4570f2d6a0ad1cbfea28656a4",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f0940c6f6c2fb38c764ce2a58a6492faa25ad376"
        },
        "date": 1786511163013,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 130.2,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 197.51,
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
          "id": "90ee7842f9ff4b47b22f0b646559821ee149169e",
          "message": "fix: address core engine findings, edge cases, and test isolation (#131)\n\nAddress correctness bugs, edge cases, and test isolation issues:\n\n- Fix TOML escaping bug in template interpolation (`re.sub` lambda replacement)\n- Prevent config cache poisoning when loading override targets\n- Programmatically format pre-commit YAML dependency lists with explicit indentation\n- Switch .gitignore and .dockerignore deduplication to line-by-line matching\n- Impose 1MB read limit defense on remote config fetcher\n- Remove PYTEST_CURRENT_TEST check in orchestrator and fix global pathlib mocking\n- Document private argparse API usage in CLI help formatter\n- Raise test coverage enforcement threshold to 90% in pyproject.toml",
          "timestamp": "2026-08-11T22:38:47-07:00",
          "tree_id": "39529d77e7b5d4cb9289842017195407a9f4712d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/90ee7842f9ff4b47b22f0b646559821ee149169e"
        },
        "date": 1786513185058,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 128.47,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 196.2,
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
          "id": "ae2adc1561e3910ef6b3f2c94fa6fb3fb87d5def",
          "message": "docs(architecture): add high-level decision comments and fix placeholder docstrings\n\n- Add architectural block comment in executor.py for tomlkit AST merging & scalar purging.\n- Document deterministic pipeline execution sequence in executor.py.\n- Document pre-parser sys.argv interception and POSIX exit code mappings in cli.py.\n- Outline 4-tier configuration precedence cascade in presets/base.py.\n- Fix extract_variables docstring placeholder syntax to <% var %> and document regex escaping strategy in interpolation.py.",
          "timestamp": "2026-08-11T22:49:15-07:00",
          "tree_id": "443151341a091e7b7aaaffab66fe164431723f86",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/ae2adc1561e3910ef6b3f2c94fa6fb3fb87d5def"
        },
        "date": 1786513831885,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 106.29,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 159.74,
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
          "id": "a9d616d3d948cfc8c8c6bb096d59d14443926edd",
          "message": "docs: fix incorrect interpolation syntax in mechanics documentation\n\n- Updates `docs/mechanics/portable_configurations.md` to correctly reference ERB-style `<% variable %>` placeholders instead of Jinja-style `{{ variable }}`.\n- Resolves a contradiction with `docs/usage/configuration.md` and aligns the mechanics documentation with the actual regex parsing implementation in `interpolation.py`.",
          "timestamp": "2026-08-11T22:59:05-07:00",
          "tree_id": "f033a926f2ffc7532f34a56ab2bad729f1abdbee",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a9d616d3d948cfc8c8c6bb096d59d14443926edd"
        },
        "date": 1786514417130,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 142.11,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 223.86,
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
          "id": "fc176210ef438da6d656f1a3ee4dccfe20495ed9",
          "message": "chore(deps): bump pre-commit hooks to latest versions\n\n- ruff: v0.15.20 → v0.16.2\n- mypy: v2.1.0 → v2.3.0\n- markdownlint-cli2: v0.22.1 → v0.23.2\n- renovate-config-validator: v43.247.1 → v44.24.3",
          "timestamp": "2026-08-11T23:23:19-07:00",
          "tree_id": "01a16fafaf0e6de3a6afb2bc4506c6c95d7cfe65",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/fc176210ef438da6d656f1a3ee4dccfe20495ed9"
        },
        "date": 1786515863438,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 129.08,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 196.72,
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
          "id": "4d4c15bd7eaf66f045a5da5a18ef435911b2f22b",
          "message": "feat: add prek as an alternative git hook manager (#132)\n\n* feat: add PrekModule and manifest support for prek\n\n* feat: add CLI validation for mutually exclusive pre-commit and prek flags\n\n* test: add unit and CLI tests for prek integration\n\n* fix: resolve CLI unit test mocking error for prek integration\n\n* fix: generate pre-commit config file when prek is requested\n\n* docs: add prek documentation and design decision note\n\n* docs: update fixtures",
          "timestamp": "2026-08-12T11:33:59-07:00",
          "tree_id": "f00ecbaf6f2c15b6e0f412e35131590c97ac38c0",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/4d4c15bd7eaf66f045a5da5a18ef435911b2f22b"
        },
        "date": 1786559698762,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 129.48,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 195.21,
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
          "id": "3cec27b57e24513ab558f44c8f6c1e41159b2fac",
          "message": "docs: use prek instead of pre-commit for generating doc fixtures\n\nUpdate the CLI execution matrix in `generate_doc_fixtures.py` to use `--prek`\ninstead of `--pre-commit`, and update the regenerated `cli_pyprojecttoml.md`\nfixture accordingly.",
          "timestamp": "2026-08-12T11:38:40-07:00",
          "tree_id": "7bc5c15f383ecbf2d3279cdce120e516ef5ae1b8",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/3cec27b57e24513ab558f44c8f6c1e41159b2fac"
        },
        "date": 1786559987132,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 138.83,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 213.7,
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
          "id": "3a3a94114ce76629881510f3b246f6bb2e45b015",
          "message": "feat: inject project metadata and add visual separators to pyproject.toml scaffolding (#133)\n\n* feat: add pyproject.toml section and tool headers\n\n* feat: prompt for project metadata in interactive wizard\n\n* feat: inject project metadata into pyproject.toml\n\n* fix: resolve pyproject.toml idempotency issue and update docs fixture\n\n* fix: protect [project] root table from scalar purging during OVERWRITE strategy",
          "timestamp": "2026-08-12T14:44:43-07:00",
          "tree_id": "01a2e40c0e17d47d2bb667e70ae4d5c0e05fcbb6",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/3a3a94114ce76629881510f3b246f6bb2e45b015"
        },
        "date": 1786571143620,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 123.38,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 189.37,
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
          "id": "f8cacf567c4ab5a7188215044bbb690ab9ce73ca",
          "message": "feat(presets): scaffold README.md for CLI and API presets\n\n- Introduce `default_files` property on `PresetModule` to allow presets to scaffold files.\n- Process `default_files` and `files` overrides during manifest realization.\n- Add an empty `README.md` file to `CliPreset` and `ApiPreset` defaults.\n- Update CLI directory tree documentation snippet to include `README.md`.",
          "timestamp": "2026-08-12T14:50:18-07:00",
          "tree_id": "fef51960a58b0d0bb6ca52cde061fbaa0c30d325",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f8cacf567c4ab5a7188215044bbb690ab9ce73ca"
        },
        "date": 1786571490077,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 131.16,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 196.85,
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
          "id": "122a1ad59f390e0195a25eddf2c886dcf9304acd",
          "message": "chore(docs): fix non-deterministic sorting in doc fixtures generation\n\nForces the `tree` command to use the `C` locale (`LC_ALL=C`) when generating directory structures in `scripts/generate_doc_fixtures.py`.\n\nPreviously, `tree` would rely on the host machine's default locale, resulting in case-insensitive sorting locally (MacOS) and case-sensitive sorting in CI (Ubuntu), which caused GitHub Actions to report the fixtures as out-of-date.\n\nAdditionally passes `--charset=utf-8` to ensure `tree` continues to output Unicode box-drawing characters despite being in the `C` locale.",
          "timestamp": "2026-08-12T16:51:07-07:00",
          "tree_id": "e7ed180226f6f971157c7f08c3dd063701bbeeba",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/122a1ad59f390e0195a25eddf2c886dcf9304acd"
        },
        "date": 1786578732372,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 133.67,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 201.83,
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
          "id": "d2276b923e49b72675c48062cf86ef90abe1e98f",
          "message": "feat: add commitizen version bumping scaffolding (#134)\n\n* feat(config): add commitizen field to ProtostarConfig\n\n* feat(modules): add CommitizinModule to tooling_layer\n\n* feat(modules): register CommitizinModule in TOOLING_MODULES\n\n* feat(templates): enable commitizen in cli template\n\n* test(modules): add unit tests for CommitizinModule\n\n* test(config): add commitizen config parsing tests\n\n* fix(modules): add commit-msg hook installation, changelog stub, and TOML formatting\n\n* docs: update fixtures",
          "timestamp": "2026-08-12T17:31:36-07:00",
          "tree_id": "0c25fe7ecc95277da4aed72cbfdf3c41b225a628",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d2276b923e49b72675c48062cf86ef90abe1e98f"
        },
        "date": 1786581156680,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 142.08,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 218.57,
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
          "id": "68fd8825efbdbd1a7a1095c8fe57b0c409d50430",
          "message": "fix(executor): position [dependency-groups] above tool configuration header\n\nReorder `_install_dependencies` before `_append_files` in `SystemExecutor.execute` so `uv add` populates `[dependency-groups]` before tooling sections and headers are appended. Also update documentation example artifacts to reflect the updated section ordering in `pyproject.toml`.",
          "timestamp": "2026-08-12T17:45:50-07:00",
          "tree_id": "2862d582c22d29ffaf5fdd042cc98a2c994c1e4d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/68fd8825efbdbd1a7a1095c8fe57b0c409d50430"
        },
        "date": 1786582021672,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 129.2,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 197.06,
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
          "id": "3cd2f3f5bc5dd7469cef60f651f8aa52d2a9bfd2",
          "message": "chore(mypy): enable strict mode and resolve type errors (#135)\n\n* chore(mypy): enable strict mode in pyproject.toml\n\n* fix(mypy): resolve strict mode type errors across codebase",
          "timestamp": "2026-08-12T18:26:38-07:00",
          "tree_id": "dd4386acaa606a7b795b51ac141a8c64833265bd",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/3cd2f3f5bc5dd7469cef60f651f8aa52d2a9bfd2"
        },
        "date": 1786584456804,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 133.31,
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
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "1029d98d0bbb5b72e8ef72bf0c43901962f4ed15",
          "message": "feat(templates): overhaul CLI template and update base tooling configs (#136)\n\n* feat(executor): add __replace__ marker support for TOML tables\n\n* feat(modules): update base tooling configs for Ruff, Mypy, and Pytest\n\n* feat(templates): update cli.toml tooling configs and switch to prek\n\n* test: update Pytest, Ruff, and Mypy config tests and add __replace__ test\n\n* test: remove unused mypy ignore on fixture and add pytest to hook\n\n* docs: update fixtures\n\n* test: remove pytest-cov from base integration test expectation",
          "timestamp": "2026-08-12T20:20:44-07:00",
          "tree_id": "0db4d181e61adaa2d4f6d37e761791149eba2dc4",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1029d98d0bbb5b72e8ef72bf0c43901962f4ed15"
        },
        "date": 1786591301197,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 131.86,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 201.19,
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
          "id": "16f98124c4e17ebfa64a607b504ac7a8fbe6488d",
          "message": "feat: scaffold Astral's ty typechecker (#137)\n\n* feat: scaffold Astral's ty typechecker\n\n* fix: populate tool.ty.rules with baseline configuration\n\n* fix: add heading to ty pyproject configuration\n\n* fix: add Ty visual separator to pyproject.toml injections\n\n* docs: update fixtures",
          "timestamp": "2026-08-12T20:57:28-07:00",
          "tree_id": "64e14ec2899a8089c5c070d5a7606641cfe48a9a",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/16f98124c4e17ebfa64a607b504ac7a8fbe6488d"
        },
        "date": 1786593515044,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 135.4,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 207.72,
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
          "id": "ace5ef1ddd0ca981cadee308e6dd7a29e2bda032",
          "message": "feat: scaffold Pyrefly type checker module (#138)\n\n* feat: scaffold PyreflyModule in tooling layer\n\n* feat: register PyreflyModule in module registry\n\n* feat: add Pyrefly to tool config visual headers\n\n* docs: update fixtures",
          "timestamp": "2026-08-12T21:14:37-07:00",
          "tree_id": "d6c9324352e91406174937708e0217ceea22ecbf",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/ace5ef1ddd0ca981cadee308e6dd7a29e2bda032"
        },
        "date": 1786594537540,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 132.38,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 201.11,
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
          "id": "90058bbdf1a2e21e64af9880c9b192a226f0a1ea",
          "message": "chore(deps): improve renovate config defaults\n\n- Switch schedule from monthly to weekly (Monday) to reduce\n  compounding delay with the 2-week minimumReleaseAge buffer\n- Remove prCreation: immediate to defer to config:best-practices\n  not-pending default (creates PRs only after CI passes)\n- Remove lockFileMaintenance from minimumReleaseAge filter since\n  it is housekeeping, not a package release",
          "timestamp": "2026-08-12T21:25:11-07:00",
          "tree_id": "fddf0fcec7dee22308635bb2489517da1b71c1ed",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/90058bbdf1a2e21e64af9880c9b192a226f0a1ea"
        },
        "date": 1786595317908,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 133.65,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 203.81,
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
          "id": "f8db61f0e4e75d0d0838294cc17bcfe9c5751f3a",
          "message": "feat(modules): add RenovateModule for Renovate dependency update scaffolding (#139)\n\n* feat(modules): add RenovateModule for Renovate dependency update scaffolding\n\n- Implement RenovateModule to scaffold .github/renovate.json with optimal defaults\n- Register renovate-config-validator pre-commit hook (rev 44.24.3)\n- Register RenovateModule in TOOLING_MODULES and update config comments\n\nCloses #105\n\n* test(modules): add unit tests for RenovateModule\n\n- Add test for RenovateModule properties (name, cli_flags, config_key, collision_markers)\n- Add test for file injection of .github/renovate.json\n- Add test for pre-commit validator hook injection\n- Add test for diagnostic skip when .github/renovate.json already exists\n\n* docs(templates): add renovate tooling to templates and update documentation fixtures\n\n- Enable renovate = true in CLI application template (cli.toml)\n- Regenerate documentation fixtures including table_tooling.md, default_config.md, and cli_init_help.svg",
          "timestamp": "2026-08-12T21:40:50-07:00",
          "tree_id": "dd827799f248d8a479fe2d9109ddc3256c131852",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f8db61f0e4e75d0d0838294cc17bcfe9c5751f3a"
        },
        "date": 1786596110592,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 135.45,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 204.09,
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
          "id": "d1436a2f585d26c1ee5a4bc81381a2f1f6bac74b",
          "message": "feat(modules): scaffold opinionated Codecov configuration (#140)\n\n* feat(config): add codecov configuration toggle to ProtostarConfig\n\n* feat(modules): implement CodecovModule for scaffolding opinionated codecov.yml\n\n* docs: update documentation and generated fixtures for codecov module (resolves #106)",
          "timestamp": "2026-08-12T22:09:46-07:00",
          "tree_id": "c54aeccd4f67fce28284357b4a8538b340b26d89",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d1436a2f585d26c1ee5a4bc81381a2f1f6bac74b"
        },
        "date": 1786597846185,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 133.84,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 200.1,
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
          "id": "9ae1254471e03dd9233d46f987e0f6c381981a4c",
          "message": "docs: document error handling architecture and POSIX exit codes (#141)\n\nAdd comprehensive documentation for Protostar's error handling paradigm, exception hierarchy, POSIX exit code mappings, and contributor rules.\n\nKey Updates:\n- docs/mechanics/error_handling.md: New mechanics guide covering fail-fast pre-flight checks, Rich terminal panels, stdout/stderr captured telemetry, POSIX exit code matrix (78, 69, 74, 70, 1), and GitHub crash report generation.\n- mkdocs.yml: Registered Error Handling in navigation under Mechanics.\n- docs/mission-control/api-reference.md: Added docstrings for all 5 exception subclasses in protostar.errors (ConfigurationError, MissingDependencyError, CommandExecutionError, CommandTimeoutError, FileSystemError).\n- docs/mechanics/orchestrator.md: Updated Mermaid flowchart exit nodes with explicit POSIX exit codes.\n- CONTRIBUTING.md: Expanded Rule 6 (Structural Error Handling Paradigm) with exception subclass definitions, POSIX compliance rules, and decoupled hint conventions.",
          "timestamp": "2026-08-12T22:24:53-07:00",
          "tree_id": "d5b5d09eadc9b88e127789f84aa3fb872e70bf55",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/9ae1254471e03dd9233d46f987e0f6c381981a4c"
        },
        "date": 1786598754147,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 131.6,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 200.58,
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
          "id": "f918d9f47e6913e88d7baa3f875211230555fc68",
          "message": "docs: update site_url to ReadTheDocs stable URL\n\nThe site_url now points to the official ReadTheDocs documentation.",
          "timestamp": "2026-08-13T11:16:54-07:00",
          "tree_id": "231178c8dbd3784030396d9548abdbbe9d70dc12",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f918d9f47e6913e88d7baa3f875211230555fc68"
        },
        "date": 1786645088158,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 132.71,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 202.24,
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
          "id": "976c579d42c664091cdfdfc24e4b1bf2c800c7f0",
          "message": "feat(modules): scaffold zensical documentation framework (#142)\n\n* feat(manifest): add docs_dependencies field\n\n* feat(executor): support docs_dependencies and PROJECT_NAME interpolation\n\n* feat(modules): add ZensicalModule implementation\n\n* test(executor): update expected pyproject parse error message\n\n* fix(zensical): fix array merging and wiring dev group\n\n* fix(zensical): use file injection for mkdocs and interpolate PROJECT_NAME\n\n* docs: update fixtures",
          "timestamp": "2026-08-13T11:36:58-07:00",
          "tree_id": "ed8ba98e05dd9112a90e0a52da86a18cfdfead65",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/976c579d42c664091cdfdfc24e4b1bf2c800c7f0"
        },
        "date": 1786646276129,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 134.08,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 201.87,
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
          "id": "9bc856468952a39ec84c5ed06d1b13b923db3a2d",
          "message": "feat(wizard): add global config fallbacks and enhanced pyproject metadata (#143)\n\n* feat(config): add author and github global configuration fields\n\n* feat(wizard): add git config fallback and explicitly prompt for python/os in cli template\n\n* feat(core): generate pyproject.toml classifiers and github urls based on wizard metadata\n\n* fix(wizard): leave author name and email empty by default if not found in git config\n\n* feat(wizard): allow empty metadata and add global config hint\n\n* docs: update fixtures\n\n* test: temporarily drop test coverage requirements to 85%\n\n* fix(core): restore default placeholders for description and authors if skipped\n\n* docs: update manifest fixture",
          "timestamp": "2026-08-13T13:00:08-07:00",
          "tree_id": "608bb2d2b1fc2719ad6b3c4bdf314a75a087fb5e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/9bc856468952a39ec84c5ed06d1b13b923db3a2d"
        },
        "date": 1786651267123,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 134.3,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 201.85,
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
          "id": "7837b6395ad9df792781c67503f3d10f2d838539",
          "message": "feat: scaffold baseline CI/CD workflows (#99) (#144)\n\n* feat(metadata): add centralized MetadataField registry and resolve_metadata() function\n\nThis commit also adds supported_os field to ProtostarConfig to support CI generation.\n\n* feat(manifest): add metadata dict, ci_flags set, ci_steps list, wants_ci and wants_release fields\n\n* feat(base): add required_metadata and optional_metadata ClassVars to BootstrapModule\n\n* feat(orchestrator): inject resolved metadata into manifest before build phase\n\n* refactor(wizard): replace hardcoded prompts with centralized resolve_metadata()\n\n* refactor(cli): add metadata resolution to handle_init flags path\n\n* refactor(lang_layer): read metadata from manifest; extract version range to utils\n\n* feat(tooling): add ci_step/ci_flag contributions to existing modules\n\n* feat(ci): add CIModule and ReleaseModule\n\n* feat(executor): assemble and write ci.yml and release.yml from manifest state\n\n* test(cli): fix test_handle_init_template_resolution to expect multiple config load calls\n\n* test: unit tests for metadata resolver, CIModule, ReleaseModule, executor CI assembly\n\n* fix(executor): resolve ci generator newline bug and setup-uv action version\n\n* fix(ci): add required_metadata to CIModule\n\n* fix(ci): add blank lines between ci.yml steps\n\n* fix(metadata): enforce deterministic prompt ordering\n\n* feat(ci): enhance codecov integration with test analytics upload\n\n* fix(ci): refine ruff output format and setup-uv python matrix injection\n\n* test(ci): add coverage tests for pytest ci assembly branches\n\n* docs: update fixtures\n\n* fix(types): resolve mypy type check errors in cli and metadata",
          "timestamp": "2026-08-13T15:48:06-07:00",
          "tree_id": "346c0c9cff3e0e05851516ddc09aa0dfb4edaebe",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/7837b6395ad9df792781c67503f3d10f2d838539"
        },
        "date": 1786661346349,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 140.11,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 213.36,
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
          "id": "b56ee98702ba0bbfedf8990bb4544ecdc5d4bba6",
          "message": "docs: add module-level docstrings to core modules\n\nAdd descriptive docstrings to cli.py, config.py, metadata.py, and system.py\nto improve code documentation and clarify each module's responsibility.",
          "timestamp": "2026-08-13T16:15:53-07:00",
          "tree_id": "46363bb9499220e6e9eb9b876a55fcc7dbb81391",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/b56ee98702ba0bbfedf8990bb4544ecdc5d4bba6"
        },
        "date": 1786663005636,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 77.87,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 117.59,
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
          "id": "cd72addfc3998d1ce7b90a4bcfe637ebb1925b31",
          "message": "feat(presets): scaffold src/<package_name> and starter Typer boilerplate in CLI preset (#145)\n\n* feat(utils): add sanitize_package_name and resolve_package_name utilities\n\n* feat(executor): add PACKAGE_NAME template interpolation support\n\n* feat(preset): support metadata fields on PresetModule base class\n\n* feat(presets): scaffold src/<package_name> and starter Typer boilerplate in CliPreset\n\n* docs: update documentation fixtures for CLI package scaffolding\n\n* feat(presets): update cli __init__.py with metadata version resolution and optional description docstring\n\n* feat(presets): update starter cli.py with version callback and help metadata",
          "timestamp": "2026-08-13T17:58:56-07:00",
          "tree_id": "b3c8f017617ea6ab7f13383456b52a8a2637da34",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/cd72addfc3998d1ce7b90a4bcfe637ebb1925b31"
        },
        "date": 1786669198253,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 137.61,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 208.22,
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
          "id": "cd72addfc3998d1ce7b90a4bcfe637ebb1925b31",
          "message": "feat(presets): scaffold src/<package_name> and starter Typer boilerplate in CLI preset (#145)\n\n* feat(utils): add sanitize_package_name and resolve_package_name utilities\n\n* feat(executor): add PACKAGE_NAME template interpolation support\n\n* feat(preset): support metadata fields on PresetModule base class\n\n* feat(presets): scaffold src/<package_name> and starter Typer boilerplate in CliPreset\n\n* docs: update documentation fixtures for CLI package scaffolding\n\n* feat(presets): update cli __init__.py with metadata version resolution and optional description docstring\n\n* feat(presets): update starter cli.py with version callback and help metadata",
          "timestamp": "2026-08-13T17:58:56-07:00",
          "tree_id": "b3c8f017617ea6ab7f13383456b52a8a2637da34",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/cd72addfc3998d1ce7b90a4bcfe637ebb1925b31"
        },
        "date": 1786669762991,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 137.57,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 207.18,
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
          "id": "cd72addfc3998d1ce7b90a4bcfe637ebb1925b31",
          "message": "feat(presets): scaffold src/<package_name> and starter Typer boilerplate in CLI preset (#145)\n\n* feat(utils): add sanitize_package_name and resolve_package_name utilities\n\n* feat(executor): add PACKAGE_NAME template interpolation support\n\n* feat(preset): support metadata fields on PresetModule base class\n\n* feat(presets): scaffold src/<package_name> and starter Typer boilerplate in CliPreset\n\n* docs: update documentation fixtures for CLI package scaffolding\n\n* feat(presets): update cli __init__.py with metadata version resolution and optional description docstring\n\n* feat(presets): update starter cli.py with version callback and help metadata",
          "timestamp": "2026-08-13T17:58:56-07:00",
          "tree_id": "b3c8f017617ea6ab7f13383456b52a8a2637da34",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/cd72addfc3998d1ce7b90a4bcfe637ebb1925b31"
        },
        "date": 1786673446094,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 108.37,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 164.52,
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
          "id": "f50e46fd2c00b85ebc7fba3fb75d51fd77f02805",
          "message": "ci: add Ruff GitHub annotations and split linting steps\n\n- Install pytest-github-actions-annotate-failures to enable failure annotations\n- Use --output-format=github for ruff check and ruff format\n- Separate lint and format steps for clearer job output",
          "timestamp": "2026-08-13T18:00:51-07:00",
          "tree_id": "d38d046de5fb1fac5180fd64c5d5c33a274a9d1e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f50e46fd2c00b85ebc7fba3fb75d51fd77f02805"
        },
        "date": 1786673650385,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 137.1,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 203.45,
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
          "id": "cdae094ba32c0df518958092796b1fca3235c437",
          "message": "ci: use --only-group for dependency installation in workflows\n\nSwitch from `uv sync --group <group>` to `--only-group` in CI and\nReadTheDocs builds to prevent the default `dev` group from being\nincluded. This reduces unnecessary packages (e.g., mkdocs, prek) in\ntest and benchmark jobs, speeding up installation and keeping\nenvironments lean.",
          "timestamp": "2026-08-13T19:24:58-07:00",
          "tree_id": "3c13e8d69feff314ea3494edee57910135924bc9",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/cdae094ba32c0df518958092796b1fca3235c437"
        },
        "date": 1786674360314,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 131.09,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 197.05,
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
          "id": "1b2f028be9785e578e3190c7aee4411b189a4650",
          "message": "feat: scaffold justfile by default (#146)\n\n* feat: add justfile attributes to EnvironmentManifest\n\n* feat: assemble and write dynamic justfile in executor\n\n* feat: integrate justfile scaffolding into tooling modules\n\n* feat: simplify pytest recipes in scaffolded justfile\n\n* docs: update fixtures",
          "timestamp": "2026-08-13T21:01:06-07:00",
          "tree_id": "e17292e851b17ee11fb89d737586344e2f5c19e4",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1b2f028be9785e578e3190c7aee4411b189a4650"
        },
        "date": 1786680127787,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 134.16,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 199.03,
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
          "id": "68dbe54f44498443a71f2483dd556fbd98478a71",
          "message": "feat(modules): add readthedocs scaffolding and zensical dependency validation (#147)\n\n* feat(modules): add ReadTheDocsModule for Read the Docs scaffolding\n\n* feat(config): add readthedocs configuration option\n\n* feat(cli): enforce zensical dependency validation for readthedocs\n\n* docs: update tooling table and default config fixtures for readthedocs",
          "timestamp": "2026-08-13T21:22:51-07:00",
          "tree_id": "c744993cee1fcfc50dc96734a6f25c6d84deb859",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/68dbe54f44498443a71f2483dd556fbd98478a71"
        },
        "date": 1786681429681,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 134.28,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 197.34,
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
          "id": "04f8531e605c4afc13bf1533e4e6e9e477f5a732",
          "message": "chore(pre-commit): migrate Python toolchain to local uv system hooks\n\nReplace external ruff and mypy pre-commit repository hooks with\nlocal system hooks running via `uv run`.\n\n- Align ruff and mypy versions with lockfile definitions in `uv.lock`\n- Enable mypy to resolve all project dependencies inside `.venv` without\n  manually syncing `additional_dependencies`\n- Execute `ruff check --fix` and `ruff format` using local environment binaries",
          "timestamp": "2026-08-13T21:24:36-07:00",
          "tree_id": "a5f23daa415fb3347c54f2b52f69db90857caa58",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/04f8531e605c4afc13bf1533e4e6e9e477f5a732"
        },
        "date": 1786681688965,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 139.59,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 218.75,
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
          "id": "d612a88f42429f7623e0b4fc9fd8bec8e80c68b3",
          "message": "refactor: eliminate utils.py junk drawer (#148)\n\n* refactor: extract workspace utilities from utils and executor\n\n* refactor: remove utils.py junk drawer\n\n* test: fix mock for is_interactive in integration suite",
          "timestamp": "2026-08-13T21:46:50-07:00",
          "tree_id": "d0b91bc3123fa9ffe25766613f640cd0d5505539",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d612a88f42429f7623e0b4fc9fd8bec8e80c68b3"
        },
        "date": 1786682874844,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 140.36,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 211.9,
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
          "id": "c6990439beac4e3f01d55566b7e843c78838e5b1",
          "message": "refactor: resolve DRY violations and centralize boilerplate (#149)\n\n* refactor: centralize task deduplication and diagnostic skips in manifest\n\n* refactor: eliminate boilerplate loops in executor\n\n* refactor: adopt interpolation engine over inline replacements\n\n* refactor: clean up module boilerplate and centralize git init\n\n* fix: ignore late binding variables during config parsing",
          "timestamp": "2026-08-13T22:21:25-07:00",
          "tree_id": "a112f5e560b7a21d8cc9d959e1f280f9230d8b11",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/c6990439beac4e3f01d55566b7e843c78838e5b1"
        },
        "date": 1786684938172,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 104.39,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 157.32,
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
          "id": "91d26e1864ed713970dc43db7e5851d4a95000a8",
          "message": "feat(docker): scaffold multi-stage Dockerfile and container runtime environment (#150)\n\n* feat(metadata): add docker metadata configuration and wizard options\n\n* feat(executor): scaffold multi-stage Dockerfile with dynamic preset awareness\n\n* test(cli): add unit test for --docker CLI option\n\n* docs: update documentation and fixtures for Dockerfile scaffolding",
          "timestamp": "2026-08-14T10:58:07-07:00",
          "tree_id": "5a1d73daca34b146e035675387c03c5ab76f5838",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/91d26e1864ed713970dc43db7e5851d4a95000a8"
        },
        "date": 1786730346166,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 123.7,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 183.96,
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
          "id": "946957548a6b40e1b68810b3e098d4c61ee73a23",
          "message": "refactor(metadata): decouple domain metadata resolution from questionary presentation layer (#151)\n\n* refactor(metadata): isolate domain metadata resolution from presentation layer\n\n* refactor(wizard): introduce prompt_metadata for interactive metadata collection\n\n* refactor(cli): transition headless init to resolve_auto_metadata",
          "timestamp": "2026-08-14T11:18:43-07:00",
          "tree_id": "00fa6b274862d74cb67290e5acd0f7082b549131",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/946957548a6b40e1b68810b3e098d4c61ee73a23"
        },
        "date": 1786731580375,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 132.19,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 198.98,
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
          "id": "5bcc33a448848b2c8e4fc01aad94c3f9a1b763c9",
          "message": "refactor(manifest): import dataclass directly from dataclasses module",
          "timestamp": "2026-08-14T11:20:39-07:00",
          "tree_id": "63fbd8c0e30700f74d43d5bf9eea5d4b39011384",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/5bcc33a448848b2c8e4fc01aad94c3f9a1b763c9"
        },
        "date": 1786731760211,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 131.66,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 197.95,
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
          "id": "6acffdad945122c2c8cda5bc17132ccd1202f3d3",
          "message": "refactor(imports): hoist unnecessary lazy imports to module level (#152)\n\n* refactor(wizard): hoist importlib.resources and metadata imports to module level\n\n* refactor(cli): hoist wizard and metadata helper imports to module level\n\n* refactor(executor): hoist generate_python_version_range import to module level\n\n* refactor(modules): remove redundant ProtostarConfig import in lang_layer",
          "timestamp": "2026-08-14T11:33:41-07:00",
          "tree_id": "50c5927862477423ac196dbe84f5d6d6da3be266",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/6acffdad945122c2c8cda5bc17132ccd1202f3d3"
        },
        "date": 1786732477496,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 133.28,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 197.09,
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
          "id": "ac2912bacf7712cc3bfaa65b2a807d05440f37d3",
          "message": "feat: implement interactive TUI prompt for __replace__ template collisions (#153)\n\n* feat: add ExecutionAbortedError\n\n* feat: replace --force with --force-merge and --force-replace\n\n* test: add TUI tests for __replace__ collisions\n\n* chore: fix --force usage in generate_doc_fixtures.py and regenerate fixtures\n\n* test: fix --force usage in test_integration.py",
          "timestamp": "2026-08-14T12:04:35-07:00",
          "tree_id": "d57a9079ff24cdfbf349f5b21bfd21dfef461182",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/ac2912bacf7712cc3bfaa65b2a807d05440f37d3"
        },
        "date": 1786734335246,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 132.51,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 197.96,
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
          "id": "b231141cf024aa254650d4824fed4f720b8d61fb",
          "message": "refactor: unify interactive prompt aborts with ExecutionAbortedError (#154)\n\n* refactor(orchestrator): raise ExecutionAbortedError on collision strategy abort\n\n* refactor(wizard): raise ExecutionAbortedError on prompt cancellation\n\n* refactor(cli): handle ExecutionAbortedError and clean up manual sysexits\n\n* test: expand coverage for wizard and CLI error routing",
          "timestamp": "2026-08-14T12:30:53-07:00",
          "tree_id": "d1f816e761f8a7308b4b4554f9948876e9a81ddf",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/b231141cf024aa254650d4824fed4f720b8d61fb"
        },
        "date": 1786735916759,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 140.63,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 216.48,
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
          "id": "4cf0c90be4cc878d1a327be71b025dc45367d0e6",
          "message": "ci: update Codecov configuration to ignore non-source paths\n\n- Set `if_not_found: success` for project coverage to prevent CI failures\n  when coverage data is missing for certain files.\n- Add `ignore` block to exclude `tests/`, `docs/`, `scripts/`, and all\n  `__init__.py` files from coverage calculations, ensuring metrics reflect\n  only the actual application source code.",
          "timestamp": "2026-08-14T12:33:04-07:00",
          "tree_id": "cc64d67ddcaf70c82802b8daaec5c03d554674d4",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/4cf0c90be4cc878d1a327be71b025dc45367d0e6"
        },
        "date": 1786736061040,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 145.41,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 221.31,
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
          "id": "ad5e26c2f3b114ec193ce931c49c0d60d22af3d4",
          "message": "feat(tooling): scaffold local toolchain pre-commit hooks via uv run (#155)\n\n* feat(manifest): add support for local pre-commit hooks in EnvironmentManifest\n\n* feat(modules): update ruff and mypy modules to scaffold local toolchain pre-commit hooks\n\n* feat(executor): scaffold unified repo local block in pre-commit config\n\n* docs: update documentation and fixtures for local pre-commit toolchain\n\n* feat(modules): update ty and pyrefly modules to scaffold local toolchain pre-commit hooks",
          "timestamp": "2026-08-14T13:02:14-07:00",
          "tree_id": "49ea452c3eb6c899539ba1595730d3845defcadd",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/ad5e26c2f3b114ec193ce931c49c0d60d22af3d4"
        },
        "date": 1786737786389,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 109.21,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 167.06,
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
          "id": "2f8a63b71e528a360bfca5b92833b12e690ec990",
          "message": "feat(templates): enhance CLI template tooling and expand ProtostarConfig schema (#156)\n\n* feat(config): add missing tooling fields to ProtostarConfig schema\n\n* feat(templates): enable just, zensical, ci, release, readthedocs, and markdownlint in cli template\n\n* docs: update default config documentation fixture",
          "timestamp": "2026-08-14T13:17:12-07:00",
          "tree_id": "b209781dc315ac09e52361fb57a2a16fb1563440",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/2f8a63b71e528a360bfca5b92833b12e690ec990"
        },
        "date": 1786738685763,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 105.77,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 162.36,
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
          "id": "fa1c89ee55e6033d61c2af65fe53bbb4db933914",
          "message": "feat(tooling): add category header comments to pre-commit configuration (#157)\n\n* feat(executor): add category header comments to base and local pre-commit hooks\n\n* feat(modules): add category header comments to tooling layer pre-commit hooks\n\n* chore: update repository pre-commit config and documentation snippet",
          "timestamp": "2026-08-14T13:23:21-07:00",
          "tree_id": "7e884a494f8a30d3df82c66117daaedec1902b9f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/fa1c89ee55e6033d61c2af65fe53bbb4db933914"
        },
        "date": 1786739062280,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 129.42,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 190.53,
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
          "id": "0a1b1229ed265f310f7a56dcf279c6df74b2663b",
          "message": "refactor(config): split ProtostarConfig into UserConfig and TemplateBlueprint (#158)\n\n* refactor: extract UserConfig and TemplateBlueprint from ProtostarConfig\n\n* refactor: update cli.py to use UserConfig and TemplateBlueprint\n\n* refactor: update orchestrator.py to use UserConfig and TemplateBlueprint\n\n* refactor: update wizard, metadata, and executor to use UserConfig\n\n* refactor: update lang_layer and presets base to use UserConfig\n\n* test: update test suite for ProtostarConfig separation\n\n* fix: update lingering references to ProtostarConfig\n\n* fix(test): correct global config payload in test_orchestrator_idempotency",
          "timestamp": "2026-08-14T16:33:15-07:00",
          "tree_id": "9e69c656d2408f653117312edfefdaccf759351c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/0a1b1229ed265f310f7a56dcf279c6df74b2663b"
        },
        "date": 1786750466229,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 130.95,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 196.8,
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
          "id": "5ed42fd3518889a2ab8d221cd2210d7fcb0de986",
          "message": "feat(core): implement security sandbox for template execution (#159)\n\n* feat(core): add SecurityViolationError domain exception\n\n* feat(core): implement safe zip extraction with path traversal protection\n\n* feat(core): enforce path jail and binary safelist in SystemExecutor\n\n* test(security): add comprehensive path jail and binary safelist tests\n\n* feat(core): add direnv to executor binary safelist",
          "timestamp": "2026-08-14T16:57:45-07:00",
          "tree_id": "c6c4838f2cc6870b05b6a4fc93a36b7e81440b5a",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/5ed42fd3518889a2ab8d221cd2210d7fcb0de986"
        },
        "date": 1786751923947,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 135.34,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 202.02,
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
          "id": "2b9cdc66403070d505f6c09b1a3b2148c24828a7",
          "message": "feat: dual-mode template resolution and archive unpacker (#160)\n\n* feat: support raw rendering in render_template without TOML escaping\n\n* feat: add template archive fetching and URL translation to network utilities\n\n* feat: add template directory walking and variable scanning to config\n\n* test: add tests for blueprint loader and archive translation\n\n* fix: use safe_extract_zip and ensure tempdir cleanup in config",
          "timestamp": "2026-08-14T17:38:47-07:00",
          "tree_id": "466aee5ef826b1074eb7e93e18571d9644f24d00",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/2b9cdc66403070d505f6c09b1a3b2148c24828a7"
        },
        "date": 1786754388721,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 133.83,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 202.14,
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
          "id": "2bb0920c6f04f61ef2b7e59837455aff5d6a9db8",
          "message": "refactor(core): migrate from python presets to declarative TOML templates (#161)\n\n* feat(templates): migrate python preset logic to declarative TOML templates\n\n* feat(orchestrator): map TemplateBlueprint structural fields to EnvironmentManifest\n\n* refactor: purge python preset layer and pivot interfaces to template-first model\n\n* refactor(config): parse template blueprint fields and purge preset test remnants\n\n- Add root-level structural field parsing (dependencies, directories, ignores, tasks) to `TemplateBlueprint._parse`\n- Update CLI template resolution tests to assert blueprint payload dependencies\n- Remove `active_presets` and `DummyPreset` test fixtures across config and orchestrator suites\n\n* docs(fixtures): migrate documentation generator and fixtures to built-in templates\n\n- Update `generate_doc_fixtures.py` to use `--template <name>` flags instead of purged preset CLI flags\n- Replace the hardcoded presets capability matrix with a dynamic built-in templates table\n- Update `generate_manifest_state()` to load and apply `astro.toml` via `TemplateBlueprint`\n- Regenerate documentation fixtures, tables, SVGs, and pyproject.toml snippets\n\n* test(exhaustive): migrate preset orthogonality suite to isolated template checks\n\n- Replace combinatorial preset pair tests with parameterized single-template scaffolding checks\n- Assert runtime dependency presence across all built-in templates\n- Expand malformed argument tests to cover invalid templates and flag collisions\n\n* chore(templates): remove lingering preset terminology and update docs\n\n- Remove obsolete `active_presets` keys from `cli.toml` and `astro.toml`\n- Update `protostar init` CLI epilog to use `--template` instead of purged preset flags\n- Update `README.md` examples and documentation to reflect the new template-first architecture\n\n* docs(core): align architecture guides and tutorials with new template engine\n\n- Rename `presets.md` to `templates.md` and update navigation hierarchy\n- Replace legacy domain CLI flags (e.g., `--astro`) with `--template <name>` across all tutorials\n- Remove obsolete documentation for `PresetModule`, `active_presets`, and `[presets.xyz]` overrides\n- Update Mermaid architecture diagrams in `modules.md` and `api-reference.md` to remove the 4th layer preset abstraction\n- Update `testing.md` to reflect the new exhaustive template merge orthogonality checks",
          "timestamp": "2026-08-14T22:12:21-07:00",
          "tree_id": "eb4598bd5c338554b905d77ef592403d1b86a992",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/2bb0920c6f04f61ef2b7e59837455aff5d6a9db8"
        },
        "date": 1786770802210,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 141.11,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 219.04,
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
          "id": "f5ac02e4fbdbc41905eae841000aebe3e533b7af",
          "message": "feat: finalize template transition with alias registry, precedence cascade, and trust dialog (#162)\n\n* feat: expand config schema for template aliasing and tooling overrides\n\n* feat: implement template alias resolution and configuration cascade\n\n* feat: implement explicit trust dialog for external templates\n\n* refactor: modernize TUI wizard to support template blueprints\n\n* test: add coverage for template aliases, overrides, and trust verification\n\n- Add unit tests for UserConfig parsing and validation of the [templates] table\n- Add tests verifying TemplateBlueprint tooling overrides extraction\n- Add tests for Orchestrator remote trust dialog behavior across interactive,\n  non-interactive, and aliased scenarios\n- Add CLI routing tests for global template alias resolution and error handling\n\n* docs: update fixtures\n\n* ci: install direnv on runners to allow testing to pass",
          "timestamp": "2026-08-15T14:50:21-07:00",
          "tree_id": "6d9e85a557eef2322b8f94d59cb889fa5f678414",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f5ac02e4fbdbc41905eae841000aebe3e533b7af"
        },
        "date": 1786830679245,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 118.02,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 176.18,
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
          "id": "1d018586264f8ba9c27ac975d370539c7ec28c9b",
          "message": "docs: comprehensive overhaul for template architecture, alias registry, and security model (#163)\n\n* chore: standardize built-in templates and add dynamic schema generator\n\n- Format all built-in TOML templates with consistent visual comment headers\n- Add `generate_template_schema_fixture` to fixture generation script\n- Introspect `TemplateBlueprint` and `TOOLING_MODULES` to automatically\n  generate the `template_schema.md` documentation snippet\n\n* docs: introduce dedicated templates guide and update core usage docs\n\n- Create `docs/usage/templates.md` as the definitive masterclass for\n  built-in templates, external sources, global aliases, and the security model\n- Streamline `init.md` to highlight templates and tri-state CLI toggles\n- Update `configuration.md` to document the new `[templates]` alias registry\n- Update `mkdocs.yml` navigation structure to prominently feature the new guide\n\n* docs: purge legacy preset architecture references\n\n- Remove outdated `PresetModule` references from module architecture\n  and API reference documentation\n- Delete obsolete `portable_configurations.md` (superseded by `templates.md`)\n- Delete obsolete `presets.md`\n- Update Mermaid diagrams to accurately reflect the strict OS -> Language -> Tooling layer stack\n\n* docs: update README to highlight templates, tri-state toggles, and alias registry\n\n* fix(ci): use native package managers to install direnv",
          "timestamp": "2026-08-15T16:16:30-07:00",
          "tree_id": "89a37529568a6aaf90bb248d42af5cf1d2eb9cd9",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1d018586264f8ba9c27ac975d370539c7ec28c9b"
        },
        "date": 1786835851380,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 135.59,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 199.61,
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
          "id": "8899e3686c3b3e008eec2352500f399fa2a75e2c",
          "message": "fix(executor): make TOML AST table replacement deterministic (#164)\n\n* refactor(executor): make TOML AST table replacement deterministic\n\n* test(executor): update AST table replacement unit tests\n\n* docs: removed unnecessary flag and update fixtures",
          "timestamp": "2026-08-16T03:22:33-07:00",
          "tree_id": "f8de81e46e6cb40a7b442803560e93655337efc1",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/8899e3686c3b3e008eec2352500f399fa2a75e2c"
        },
        "date": 1786875816171,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 133.16,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 200.76,
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
          "id": "fcd758c5c3c9c907c1b7dfaa59a730c406e1da70",
          "message": "fix(cli): route SecurityViolationError to POSIX EX_NOPERM status code\n\nPreviously, when a template triggered a path traversal or binary safelist\nviolation, the CLI would gracefully print the error panel but fall through\nto a generic sys.exit(1) status code.\n\nThis explicitly maps SecurityViolationError to os.EX_NOPERM (77) in the\nmain CLI exception router. This ensures strict POSIX compliance and allows\nautomated shell scripts or CI/CD runners to programmatically differentiate\nbetween a generic operational failure and a hard security constraint block.",
          "timestamp": "2026-08-16T03:38:26-07:00",
          "tree_id": "7864b253260dd93bba1ae5d4a6c13f69f1808b4e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/fcd758c5c3c9c907c1b7dfaa59a730c406e1da70"
        },
        "date": 1786876772176,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 128.54,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 192.79,
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
          "id": "2545e0a14f0a00cbb256c33d4f534dbfe079334d",
          "message": "fix(executor): format pyproject.toml with deterministic table ordering and Pytest/Coverage grouping (#165)\n\n* fix(executor): format pyproject.toml with deterministic table ordering and Pytest/Coverage grouping\n\n* test(executor): add unit tests for deterministic pyproject.toml ordering and formatting\n\n* docs(includes): update cli pyproject.toml fixture with properly ordered coverage section\n\n* fix(executor): preserve trailing empty line at the end of formatted pyproject.toml\n\n* test(executor): add comprehensive e2e and edge-case tests for pyproject.toml formatting",
          "timestamp": "2026-08-16T03:58:36-07:00",
          "tree_id": "ab7f0dd2cd86a351e3227b889cba45647cf498d0",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/2545e0a14f0a00cbb256c33d4f534dbfe079334d"
        },
        "date": 1786877976512,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 128.57,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 195.05,
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
          "id": "d3aa56821c5737855889643e21a32b9311535aa4",
          "message": "feat(cli): add template listing flag and contextual help for template selection (#166)\n\n* feat(cli): add template listing flag and contextual help for template selection\n\n- Add `--list-templates` flag to `protostar init` for template discovery\n- Configure `--template` with `nargs=\"?\"` to catch bare flag invocations\n- Render a Rich table of built-in templates and global aliases on demand\n- Preserve fast-path CLI startup latency by isolating I/O from parser generation\n- Add test coverage for `--list-templates` and empty `--template` error handling\n\n* docs: update fixtures",
          "timestamp": "2026-08-16T15:09:29-07:00",
          "tree_id": "cf06d788fa3e684fa6fb5493202137b33ebd328e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d3aa56821c5737855889643e21a32b9311535aa4"
        },
        "date": 1786918231345,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 139.87,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 210.18,
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
          "id": "14cf23af6f2ff76f9f91fd335027fedb3ebb5940",
          "message": "fix(executor): import tomlkit Table and AoT items explicitly\n\nImport `Table` and `AoT` directly from `tomlkit.items` within\n`_format_pyproject_toml` to resolve static type analysis errors\nin Pyright/Pylance when referencing unexported module attributes.",
          "timestamp": "2026-08-16T15:10:35-07:00",
          "tree_id": "176215beb10cd0e24d010f8b92b90ae208076760",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/14cf23af6f2ff76f9f91fd335027fedb3ebb5940"
        },
        "date": 1786918300976,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 135.28,
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
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "630e843e13ce0163d6021d762b4fa6e36d2a4a1a",
          "message": "feat: upgrade domain templates and introduce generalized file append API (#167)\n\n- Introduced a generalized `[appends]` API to the template engine for injecting raw text into any file.\n- Upgraded the string execution engine to use extension-aware comment markers (e.g., `#`, `//`, `<!--`), guaranteeing idempotent, syntax-safe file injections.\n- Removed legacy global configuration overrides (`global_dev_dependencies`, `pyproject_injections`, etc.) in favor of strictly deterministic template boundaries.\n- Upgraded `api.toml` with a robust FastAPI router architecture, Pydantic settings, and Docker wiring.\n- Upgraded `ml.toml` with Cookiecutter Data Science structures, `nbdime`, and Jupyter notebook linting via Ruff.\n- Upgraded `dsp.toml` for audio processing pipelines and explicit uncompressed media `.gitignore` rules.\n- Upgraded `embedded.toml` for MicroPython development, leveraging the new `[appends]` API to inject `mpremote` deploy recipes into the justfile.\n- Deleted `scientific.toml` to eliminate overlap with `ml.toml` and `astro.toml`.\n- Standardized tooling opinions across all templates, explicitly enabling `just` and `markdownlint` while toggling `prek` and `ci` based on domain relevance.",
          "timestamp": "2026-08-16T16:19:42-07:00",
          "tree_id": "259de12c20297031abec861fff83df1f0b00dcf5",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/630e843e13ce0163d6021d762b4fa6e36d2a4a1a"
        },
        "date": 1786922437622,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 131.14,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 197.5,
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
          "id": "032f1595e71bfb45e284911825a9bf70f0797b3d",
          "message": "refactor(errors): decompose ConfigurationError and harden error architecture (#168)\n\n* refactor(executor): eliminate bare ValueError in IDE settings writer\n\n* fix(fs): wrap atomic write serialization and disk errors in FileSystemError\n\n* feat(errors): add NetworkFetchError and TemplateResolutionError exception subclasses\n\n* refactor(network): decompose ConfigurationError into NetworkFetchError and TemplateResolutionError\n\n* feat(cli): map NetworkFetchError and TemplateResolutionError to POSIX exit codes\n\n* docs: document NetworkFetchError, TemplateResolutionError, and POSIX exit code matrix",
          "timestamp": "2026-08-16T16:36:11-07:00",
          "tree_id": "3c7da181e2e0d38eed6831d4c3ce036bffd84d52",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/032f1595e71bfb45e284911825a9bf70f0797b3d"
        },
        "date": 1786923428286,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 125.68,
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
          "id": "551ae5b9129cbd2e69b88774d85ab28f6c5c1d2f",
          "message": "feat: add isolated macOS and Linux sandbox test harnesses (#169)\n\n* feat: add isolated macOS and Linux sandbox test harnesses to justfile\n\n- Add `just sandbox` for ephemeral, local macOS testing with mocked $HOME, isolated $PATH, and forced wheel rebuilds.\n- Add `just sandbox-linux` and `just sandbox-linux-build` for zero-overhead containerized Linux testing via OrbStack/Docker.\n- Pre-bake inspection utilities (`eza`, `bat`, `ripgrep`, `fd`, `markdownlint-cli2`) and native shell aliases into the Linux test harness.\n\n* docs: document macOS and Linux sandbox test harnesses in contributing guide\n\nAdd guidance under Running Tests & Tooling for `just sandbox` and `just sandbox-linux` to facilitate isolated manual testing without host configuration bleed.",
          "timestamp": "2026-08-16T17:50:19-07:00",
          "tree_id": "052a4b68f62a8827c4ed3be776daea1870ba3b25",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/551ae5b9129cbd2e69b88774d85ab28f6c5c1d2f"
        },
        "date": 1786927877459,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 138.09,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 200.26,
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
          "id": "cbf6a08205da8bd0605f1ab21c719492bea0582b",
          "message": "feat(licenses): add license scaffolding with bundled templates and pyproject metadata (#172)\n\n* feat(executor): add CURRENT_YEAR and AUTHOR_NAME to interpolation context\n\n* feat(templates): add Protostar interpolation tokens to license templates\n\n* feat(config): add license configuration option\n\n* feat(cli): add license prompt with select support\n\n* feat(lang): scaffold LICENSE file and pyproject.toml classifiers\n\n* fix(cli): remove text highlighting from license select prompt",
          "timestamp": "2026-08-16T18:28:36-07:00",
          "tree_id": "dfccd515b8c42f58ac8777a7485cf52cf755cfb6",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/cbf6a08205da8bd0605f1ab21c719492bea0582b"
        },
        "date": 1786930175228,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 130.57,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 197.39,
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
          "id": "0d3b8ec4718f70740f834dcf1d72b6e3c1333825",
          "message": "chore(deps): update astral-sh/setup-uv action to v9 (#171)\n\nCo-authored-by: renovate[bot] <29139614+renovate[bot]@users.noreply.github.com>",
          "timestamp": "2026-08-17T01:29:14Z",
          "tree_id": "e2064f5620d60282363326d681bcdd21986966b9",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/0d3b8ec4718f70740f834dcf1d72b6e3c1333825"
        },
        "date": 1786930210602,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 130.22,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 195.54,
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
          "id": "31579cce9b9d8bed9ef44d3f8cc304213a0b4cfd",
          "message": "feat(errors): add graceful interrupt handling and partial execution reporting (#173)\n\n* fix(fs): clean up temporary files on interrupt in atomic_write_text\n\n* feat(errors): introduce PartialExecutionAbortedError and manifest touch ledger\n\n* feat(executor): record touched paths across filesystem mutations\n\n* feat(orchestrator): catch execution interrupts and report modified paths\n\n* test: add unit tests for graceful interrupt handling and partial execution reporting\n\n* docs: update error handling guide with PartialExecutionAbortedError\n\n* docs: update fixtures",
          "timestamp": "2026-08-16T18:58:53-07:00",
          "tree_id": "d217a0440725981fe7c2c3c998a8b427464745f9",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/31579cce9b9d8bed9ef44d3f8cc304213a0b4cfd"
        },
        "date": 1786931995264,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 147.76,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 222.85,
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
          "id": "b944cf0ac3e653739c06c7ca417f608424aad83f",
          "message": "chore: streamline pre-commit hooks\n\n- use prek built-in hooks\n- add TOML and merge-conflict checks\n- run Ruff across the entire project",
          "timestamp": "2026-08-16T19:51:09-07:00",
          "tree_id": "c1aade573ee7ed193c4444037bd7a00c5af7a96e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/b944cf0ac3e653739c06c7ca417f608424aad83f"
        },
        "date": 1786935122381,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 104.23,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 154.2,
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
          "id": "15a262e7bcd1358cd568579a79b05504c31c63c0",
          "message": "refactor(docs): migrate documentation fixtures into an IDE-native snapshot harness (#174)\n\n* refactor(scripts): output ide-native raw fixtures in scenario partitions\n\n* build(tooling): update justfile and ci workflows for docs fixtures directory\n\n* docs: update snippet includes and configuration for raw fixtures\n\n* chore(fixtures): migrate documentation fixtures to ide-native snapshot directory\n\n* fix(scripts): ensure target parent directories exist before atomic writes in fixtures\n\n* fix: normalize trailing newlines in pyproject formatting and templates and exclude docs from pre-commit hooks\n\n* build(pre-commit): scope docs exclusion strictly to local python tooling hooks\n\n* fix(scripts): include .gitignore and .gitattributes in doc fixture generation\n\n* docs(config): configure link validation ignore rules in mkdocs.yml for raw fixture doc previews\n\n* fix(tooling): clean up scaffolded readthedocs starter docs and restore strict link validation\n\n* docs: update fixtures",
          "timestamp": "2026-08-17T12:21:03-07:00",
          "tree_id": "00f21047e296ad09d374559350b275716cba6900",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/15a262e7bcd1358cd568579a79b05504c31c63c0"
        },
        "date": 1786994518677,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 130.12,
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
          "id": "8b7d837b06e0dd6f66922a2204060ff1139c3de2",
          "message": "refactor(executor): extract self-contained security, dependencies, and IDE utilities (PR 1) (#175)\n\n* refactor(security): extract path jail and binary safelist to security module\n\n* refactor(dependencies): extract dependency installation logic\n\n* refactor(ide): extract ide extension check and settings writing",
          "timestamp": "2026-08-17T13:57:15-07:00",
          "tree_id": "cf740d76db7315835110d4d84468a0a8edb8da71",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/8b7d837b06e0dd6f66922a2204060ff1139c3de2"
        },
        "date": 1787000293749,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 137.42,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 208.24,
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
          "id": "b33a9c7d9896bdc33c7dfa1d618dafda41e10fbd",
          "message": "refactor(executor): extract TOML AST engine and marker-block file appends (PR 2) (#176)\n\n* refactor(toml): extract TOML AST merging and formatting to toml_ast module\n\n* refactor(appends): extract comment markers and generic marker-block appending to appends module\n\n* refactor(executor): delegate _append_files to toml_ast and appends modules",
          "timestamp": "2026-08-17T14:34:06-07:00",
          "tree_id": "6dc6a340845864a4be1ddd874ed3a5eb30d7e891",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/b33a9c7d9896bdc33c7dfa1d618dafda41e10fbd"
        },
        "date": 1787002502579,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 135.56,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 198.01,
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
          "id": "b4a9814d10f10cac54120b6136f5be786cc868c1",
          "message": "refactor(executor): extract workflow and boilerplate generators (PR 3) (#177)\n\n* refactor(workflows): create pure string generators for workflows and boilerplate files\n\n* refactor(executor): delegate workflow and boilerplate writing to workflows module",
          "timestamp": "2026-08-17T14:45:40-07:00",
          "tree_id": "1eecb1e78f3a65ceaa000740c52079b38c166766",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/b4a9814d10f10cac54120b6136f5be786cc868c1"
        },
        "date": 1787003204834,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 150.17,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 222.55,
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
          "id": "cabd51e571c09aa8ac0aec1fa4a0db588e9d4f42",
          "message": "refactor(executor): finalize thin orchestrator, standardize path jail and exports (#178)",
          "timestamp": "2026-08-17T15:01:18-07:00",
          "tree_id": "a7f30fc21bbba1e678938b049ca9990f52b217e6",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/cabd51e571c09aa8ac0aec1fa4a0db588e9d4f42"
        },
        "date": 1787004135699,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 141.59,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 207.25,
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
          "id": "0c0ed875447b7408c53a51d5edda14d5ceb87ee6",
          "message": "refactor: executor cleanup and boundary type hardening (PR 5) (#179)\n\n* refactor(executor): consolidate task execution logic and update documentation\n\n* refactor(typing): harden type boundaries in codegen and manifest\n\n* chore: accept fixture drift due to SystemTask attribute ordering",
          "timestamp": "2026-08-17T15:28:59-07:00",
          "tree_id": "725fc5c254f7d955f742321dee657ed6ddd0aede",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/0c0ed875447b7408c53a51d5edda14d5ceb87ee6"
        },
        "date": 1787005802338,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 145.2,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 211.96,
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
          "id": "dc99ce70ab6763c7c1818efbb07e5f97d82d204d",
          "message": "refactor(manifest): slice EnvironmentManifest into domain dataclasses (#180)",
          "timestamp": "2026-08-17T17:17:55-07:00",
          "tree_id": "2a4fba34f2239e573931ef9e4a782929f96e6865",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/dc99ce70ab6763c7c1818efbb07e5f97d82d204d"
        },
        "date": 1787012340421,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 143.5,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 209.57,
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
          "id": "66e106a10686a7e9cd1dc32f460e0b492afa5a33",
          "message": "docs(manifest): align documentation with domain slice architecture, add security flowcharts, and fix late-binding variable resolution (#181)\n\n* docs(manifest): update documentation to reflect domain slice architecture and namespaces\n\n* docs(diagrams): add visual scaffolding for remote trust boundary and AST deep merging\n\n* fix: resolve CLI flags, late-binding parsing, Commitizen typo, and docs drift",
          "timestamp": "2026-08-17T18:13:32-07:00",
          "tree_id": "29e012ab057ab67d7035381156d720dc69bbb33b",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/66e106a10686a7e9cd1dc32f460e0b492afa5a33"
        },
        "date": 1787015676442,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 148.37,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 218.45,
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
          "id": "c4a01c01bed1ac5dfffaa7be9cbbed8bb0fcec31",
          "message": "fix(config): align tooling comments and group direnv in default config",
          "timestamp": "2026-08-17T18:43:41-07:00",
          "tree_id": "af015f4a1ca8f34e51378a32c19431f6c3920702",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/c4a01c01bed1ac5dfffaa7be9cbbed8bb0fcec31"
        },
        "date": 1787017501095,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 157.43,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 227.69,
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
          "id": "3c5c9c99cce7abcef012000fdb9ef9cb2b05807c",
          "message": "docs(config): remove outdated dev overrides section from configuration guide",
          "timestamp": "2026-08-17T20:54:12-07:00",
          "tree_id": "f2b586a8701be1d80a95de8487aea0936fa24cf1",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/3c5c9c99cce7abcef012000fdb9ef9cb2b05807c"
        },
        "date": 1787025337635,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 141.47,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 207.07,
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
          "id": "869339082964c28f2c5d09b8b297ad17c247bdb9",
          "message": "chore(docs): exclude uv.lock from documentation fixtures\n\nExclude uv.lock files during doc fixture extraction to eliminate\narbitrary diff churn caused by upstream PyPI dependency updates during\nCI fixture drift checks.",
          "timestamp": "2026-08-17T21:10:38-07:00",
          "tree_id": "aa7d6571373f6000429aa9db87f5db0e616e85f4",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/869339082964c28f2c5d09b8b297ad17c247bdb9"
        },
        "date": 1787026322314,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 161.1,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 238.21,
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
          "id": "0ca0dcaea2b6a7c008074d27c4fd05e53481daa4",
          "message": "docs: add dedicated guide for authoring custom templates\n\n- Add `docs/usage/authoring-templates.md` detailing single-file TOML specifications, multi-file repository archives, variable interpolation, local testing, and security boundaries.\n- Register the new page under the Usage section in `mkdocs.yml`.",
          "timestamp": "2026-08-17T21:26:32-07:00",
          "tree_id": "1c39847e7aa2eee056626a66765aa32f4fadc41d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/0ca0dcaea2b6a7c008074d27c4fd05e53481daa4"
        },
        "date": 1787027257364,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 144.86,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 208.79,
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
          "id": "676df000e31643c1ef7e367e785094069a5843a6",
          "message": "docs: expand documentation fixtures and integrate missing footprints (#182)\n\n* refactor(lang): extract LICENSE_MAP to module level\n\n* feat(docs): add generators for config help SVG, metadata and license tables, and diagnostic panel SVG\n\n* docs(init): add api, dsp, and embedded footprints, task runner orchestration, and metadata reference\n\n* docs(config): embed config help SVG and add supported licenses table\n\n* docs(orchestrator): add diagnostic telemetry summary section and panel SVG",
          "timestamp": "2026-08-17T21:41:50-07:00",
          "tree_id": "9640b209f2092b03d9026584d09321f54de483fa",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/676df000e31643c1ef7e367e785094069a5843a6"
        },
        "date": 1787028176989,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 151.16,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 220.61,
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
          "id": "a8883b21272824f8270c3f026a5eeaf9bbc7e1c5",
          "message": "docs: audit CLI flags, document aliases, and standardize tooling options (#183)\n\n* refactor(modules): remove short flag from MarkdownLintModule\n\n* docs(mechanics): align collision bypass flag references\n\n* docs(init): document -t alias and --list-templates flag\n\n* docs(cli): sync python version example to 3.13 in cli help\n\n* chore(docs): regenerate doc fixtures with updated flags and help output\n\n* docs: link to authoring-templates.md",
          "timestamp": "2026-08-17T21:59:15-07:00",
          "tree_id": "3bf421ba4cf39f71c63b4af8e6265dba1d614980",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a8883b21272824f8270c3f026a5eeaf9bbc7e1c5"
        },
        "date": 1787029216830,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 144.83,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 210.22,
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
          "id": "ed077a122536c9077b5a9186af7e0ab747fbd91b",
          "message": "feat(cli): Add documentation deep-linking to error outputs (#184)\n\n* test(ci): Add docs link validation script and CI step\n\n* feat(errors): Extend ProtostarError with docs deep-linking\n\n* feat(cli): Add InvalidUsageError and subcommand-aware doc routing\n\n* test(cli): Update tests for InvalidUsageError and doc links",
          "timestamp": "2026-08-17T22:32:13-07:00",
          "tree_id": "2eea5137478e80303cf15b282c52a2bac7d7ffee",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/ed077a122536c9077b5a9186af7e0ab747fbd91b"
        },
        "date": 1787031184862,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 120.9,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 182.48,
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
          "id": "1134473e912e90ffeac78622339a5b06d2b280aa",
          "message": "meta: add MIT license classifier to pyproject.toml",
          "timestamp": "2026-08-19T18:33:42-07:00",
          "tree_id": "bf7ccfaeff092095eddcdcff56c7fb25c6caddcc",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1134473e912e90ffeac78622339a5b06d2b280aa"
        },
        "date": 1787189700587,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 144.52,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 206.37,
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
          "id": "bba6a9df7d40e37a043e376821de62cc68bc98bd",
          "message": "refactor(metadata): introduce strong typing for metadata, licensing, and target OS (#185)\n\n- Add domain enums PromptType, MetadataKey, TargetOS, and LicenseType in enums.py\n- Type MetadataField and METADATA_FIELDS with PromptType and MetadataKey\n- Replace static LICENSE_MAP and OS string mappings with enum properties\n- Update BootstrapModule metadata annotations and CIWorkflowSpec supported_os typing\n- Add unit tests for enum resolution and metadata properties",
          "timestamp": "2026-08-22T13:02:34-07:00",
          "tree_id": "5e8cb675eddaf058c59d4dafbd580fa7b91180f3",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/bba6a9df7d40e37a043e376821de62cc68bc98bd"
        },
        "date": 1787429022477,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 153.01,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 226.95,
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
          "id": "ac4b81c1c96aa4161afeae07df32f6a1c87c46f6",
          "message": "refactor(ide): introduce strong typing for IDE choices and diagnostic phases (#186)\n\n- Add IDEType and DiagnosticPhase enums to enums.py\n- Use IDEType.binary_name property in check_ide_extensions\n- Type UserConfig.ide and DiagnosticEvent.phase with domain enums\n- Update SystemExecutor diagnostic event dispatches to use DiagnosticPhase\n- Add unit test coverage for IDEType and DiagnosticPhase enums",
          "timestamp": "2026-08-22T13:19:32-07:00",
          "tree_id": "f9aefa050372054867ea02cdfaed5fe2524f6271",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/ac4b81c1c96aa4161afeae07df32f6a1c87c46f6"
        },
        "date": 1787430035031,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 156.06,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 228.41,
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
          "id": "d498d4414769d61d22dc074598460df58994abe1",
          "message": "chore(deps): lock file maintenance (#89)\n\nCo-authored-by: renovate[bot] <29139614+renovate[bot]@users.noreply.github.com>",
          "timestamp": "2026-08-22T13:21:15-07:00",
          "tree_id": "0a271e2f26342a8e0e9e2a0878a06efcd1c1c781",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d498d4414769d61d22dc074598460df58994abe1"
        },
        "date": 1787430138805,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 155.3,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 222.74,
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
          "id": "cfd7964b85d2fa5515ca48ded80fb018722d7915",
          "message": "refactor(cicd): introduce strong typing for CI feature flags, dependency groups, and security safelist (#187)\n\n- Add CIFlag, DependencyGroup, and SafelistBinary enums in enums.py\n- Use DependencyGroup properties in dependency installation logic\n- Use CIFlag in CI workflow generation and Justfile assembly\n- Initialize ALLOWED_BINARIES security safelist from SafelistBinary\n- Add test coverage for new domain enums",
          "timestamp": "2026-08-22T13:29:06-07:00",
          "tree_id": "db42eb2934ed48537fcab364746041c305a60630",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/cfd7964b85d2fa5515ca48ded80fb018722d7915"
        },
        "date": 1787430608596,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 151.34,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 219.64,
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
          "id": "bb04d1c047cb26e1ef6bd0a8d7c025d1fd0d7766",
          "message": "refactor(workspace): introduce PythonVersion, PackageName, and ProjectName value objects (#188)\n\n* feat(workspace): introduce PythonVersion, PackageName, and ProjectName domain value objects\n\n- Implement PythonVersion with parsing, semantic ordering, Trove classifiers, and range generation\n- Implement PackageName and ProjectName with validation and PEP 8 sanitization\n- Refactor workspace resolution functions to leverage the new value objects\n\n* refactor(workflows): adopt PythonVersion and naming value objects in workflow specifications\n\n- Type CIWorkflowSpec with PythonVersion | str\n- Type DockerfileSpec with PythonVersion, ProjectName, and PackageName\n- Update matrix fallback to preserve string serialization of version objects\n\n* refactor(lang_layer): use PythonVersion trove classifiers in PythonCore module\n\n- Resolve Python Trove classifiers directly from PythonVersion.trove_classifier\n- Generate version range using PythonVersion.range_to()\n\n* test(workspace): add test suite for PythonVersion, PackageName, and ProjectName value objects\n\n- Test PythonVersion parsing, ordering, Trove classifiers, and range generation\n- Test PackageName PEP 8 validation and sanitization\n- Test ProjectName empty validation and package derivation",
          "timestamp": "2026-08-22T13:35:40-07:00",
          "tree_id": "5f39e168107c7d50f79c71c35a3e3e4f0b09b595",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/bb04d1c047cb26e1ef6bd0a8d7c025d1fd0d7766"
        },
        "date": 1787431005481,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 156.24,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 226.88,
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
          "id": "4a016695735bb3ef4a33d7cd25f49657c3e15fde",
          "message": "refactor(network, fs): introduce ArchiveFormat and GitHost enums with unified archive extraction (#189)\n\n* feat(enums): add ArchiveFormat and GitHost domain enums\n\n- Introduce ArchiveFormat enum for ZIP, TAR, TAR_GZ, TAR_BZ2, and TAR_XZ\n- Provide path/URL detection and extension resolution on ArchiveFormat\n- Introduce GitHost enum for GitHub, GitLab, Bitbucket, Codeberg, and SourceHut\n- Export ArchiveFormat and GitHost in __init__.py\n\n* feat(fs): add safe_extract_tar and safe_extract_archive utilities\n\n- Implement safe_extract_tar with Tar Slip protection\n- Implement safe_extract_archive with ArchiveFormat dispatching\n- Export new safe extraction functions in fs.py\n\n* refactor(network): use ArchiveFormat and safe_extract_archive for remote template fetching\n\n- Utilize ArchiveFormat.from_path for archive format detection and validation\n- Delegate extraction to safe_extract_archive\n- Refactor remote template resolution to use ArchiveFormat\n\n* test(network, fs): add test coverage for ArchiveFormat, GitHost, and safe archive extraction\n\n- Add test coverage for ArchiveFormat detection and is_tar property\n- Add test coverage for GitHost URL pattern identification\n- Test safe_extract_tar and safe_extract_archive with valid archives and Zip/Tar Slip security enforcement",
          "timestamp": "2026-08-22T14:21:30-07:00",
          "tree_id": "8fa9aea028657b82435a3d15f92bff022cbf6e87",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/4a016695735bb3ef4a33d7cd25f49657c3e15fde"
        },
        "date": 1787433756287,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 139.27,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 197.6,
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
          "id": "99f70e43409371bb9f40d49947c7d8bc88824a06",
          "message": "refactor(architecture): colocate domain enums with feature modules and remove enums.py (#190)\n\n* refactor(ide, security, dependencies): colocate IDEType, SafelistBinary, and DependencyGroup enums\n\n- Move IDEType to ide.py\n- Move SafelistBinary to security.py\n- Move DependencyGroup to dependencies.py\n\n* refactor(fs, network): colocate ArchiveFormat and GitHost enums\n\n- Move ArchiveFormat to fs.py\n- Move GitHost to network.py and import ArchiveFormat from fs.py\n\n* refactor(architecture): colocate remaining domain enums and eliminate enums.py\n\n- Move TargetOS and CIFlag to workflows.py\n- Move DiagnosticPhase and modernize Severity in manifest.py\n- Move MetadataKey, PromptType, and LicenseType to metadata.py\n- Update internal module imports to source from respective domain modules\n- Re-export all domain types through top-level protostar facade\n- Remove enums.py module\n\n* test(refactor): update test suite imports for domain enum colocation\n\n- Update test imports to source enums from feature domain modules\n- Update mock patch targets in test_metadata.py\n\n* refactor(metadata): resolve circular dependency by deferring UserConfig loading\n\n- Place UserConfig under TYPE_CHECKING in metadata.py\n- Lazily import UserConfig in resolve_auto_metadata\n\n* fix(typing): add future annotations to avoid runtime NameError on Python <3.14\n\n- Add from __future__ import annotations to metadata.py and module layer files\n- Remove quoted string annotations to satisfy ruff UP037",
          "timestamp": "2026-08-22T14:47:28-07:00",
          "tree_id": "562b3f8d312f73715fb8175e3b24bee510eed25d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/99f70e43409371bb9f40d49947c7d8bc88824a06"
        },
        "date": 1787435311438,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 141.31,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 203.44,
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
          "id": "35f9e3f8831dbff58cd5d6f83e497753a0974b02",
          "message": "chore(renovate): ignore docs, scripts, src, and tests paths",
          "timestamp": "2026-08-22T14:54:04-07:00",
          "tree_id": "50e1abd44c6bd88aa4d90eb531cdc815be46f10b",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/35f9e3f8831dbff58cd5d6f83e497753a0974b02"
        },
        "date": 1787435774591,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 151.15,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 219.26,
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
          "id": "fb0a45657af4c231a0114a276a0b815f73e0c096",
          "message": "refactor(orchestrator): encapsulate orchestrator flags into OrchestratorOptions dataclass (#191)\n\n* refactor(orchestrator): extract data clump into OrchestratorOptions dataclass\n\n- Define OrchestratorOptions dataclass to encapsulate blueprint, docker, force flags, metadata, and trust flags\n- Update Orchestrator.__init__ signature to accept options parameter instead of data clump arguments\n\n* refactor(cli): pass OrchestratorOptions when instantiating Orchestrator\n\n- Instantiate OrchestratorOptions in handle_init and interactive wizard execution flows\n- Pass typed options instance to Orchestrator\n\n* docs(orchestrator): add OrchestratorOptions to API reference\n\n- Include mkdocstrings block for OrchestratorOptions in architecture documentation\n\n* test(orchestrator): update orchestrator tests for OrchestratorOptions\n\n- Update CLI mocking assertions to verify OrchestratorOptions\n- Update test cases to construct OrchestratorOptions where options are specified\n- Add unit tests for default and customized OrchestratorOptions instantiation",
          "timestamp": "2026-08-22T15:05:06-07:00",
          "tree_id": "89bcaec05e9f2f6d12a4d9504dbf8fb636842946",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/fb0a45657af4c231a0114a276a0b815f73e0c096"
        },
        "date": 1787436370523,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 154.11,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 226.55,
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
          "id": "23e18d7d7ccd070699e482e74ff81041a4dce04a",
          "message": "refactor(wizard): replace untyped dictionary return with WizardSelections dataclass (#192)\n\n* refactor(wizard): introduce WizardSelections dataclass for interactive initialization results\n\n- Define WizardSelections dataclass encapsulating modules, docker, project metadata, blueprint, and trust flags\n- Update run_init_wizard return type and implementation to return WizardSelections\n- Re-export WizardSelections from top-level protostar package\n\n* refactor(cli): consume WizardSelections dataclass in interactive wizard handler\n\n- Replace dictionary key lookups and get defaults with typed attribute accesses on WizardSelections\n- Pass typed attributes directly when constructing OrchestratorOptions\n\n* test(wizard, cli): update test suite for WizardSelections dataclass\n\n- Assert WizardSelections instance type and attribute values in test_run_init_wizard_success\n- Mock WizardSelections instance in test_intercept_interactive_wizards_success",
          "timestamp": "2026-08-22T15:10:46-07:00",
          "tree_id": "b714686dbff1f53f2a1c8ca0b9f901d1494c0a53",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/23e18d7d7ccd070699e482e74ff81041a4dce04a"
        },
        "date": 1787436708301,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 153.05,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 223.16,
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
          "id": "99b05b8ccac132b197e48f82e58a505a7576c905",
          "message": "refactor(engine): establish headless engine bulkhead with plan and execute lifecycle (#194)\n\n* feat(errors): add WorkspaceCollisionError; tighten PartialExecutionAbortedError\n\n- Introduce WorkspaceCollisionError(paths: frozenset[Path]) as a structured\n  domain exception raised by plan() when collision markers exist without a\n  force flag. The paths field allows callers to present or handle collisions\n  programmatically.\n- Update PartialExecutionAbortedError.touched_paths from set[str] to\n  frozenset[str] to match the immutable ExecutionResult.touched_paths type\n  introduced in the next commit.\n\n* feat: introduce models.py with InitRequest and ExecutionResult\n\nAdd a dedicated models.py to define the two public boundary types that\ncross the engine/CLI interface:\n\n- InitRequest: dataclass representing caller intent (template, flags,\n  metadata). python_version is included as a documentation field for\n  future MCP callers; the modules list is already resolved before the\n  orchestrator is constructed.\n- ExecutionResult: frozen dataclass representing the observed outcome of\n  a successful or partial execution (touched_paths, diagnostics).\n\n* refactor(orchestrator,cli): replace run() with plan() and execute(); wire CLI boundary\n\nSplit Orchestrator.run() into two pure phases:\n- plan(request) -> EnvironmentManifest: evaluates collision markers, runs\n  pre_flight/build, injects the blueprint. Raises WorkspaceCollisionError\n  when markers exist without a force flag. Never touches the filesystem.\n- execute(manifest) -> ExecutionResult: realizes the pre-built manifest via\n  SystemExecutor. Wraps KeyboardInterrupt as PartialExecutionAbortedError.\n\nRemove OrchestratorOptions (replaced by InitRequest from models.py).\nRemove _evaluate_collisions() and _prompt_remote_trust() — all questionary,\nrich rendering, and is_interactive() logic moves to cli.py.\n\nCLI changes:\n- Add _run_engine(engine, request) helper that owns the full plan → collision\n  prompt loop → trust boundary → execute → diagnostic rendering pipeline.\n- handle_init() and intercept_interactive_wizards() both delegate to\n  _run_engine() instead of engine.run().\n- Add is_interactive() guard before questionary in the collision handler to\n  abort cleanly in headless environments.\n\nTest changes:\n- test_orchestrator.py fully rewritten against plan()/execute() API.\n- test_cli.py: replace Orchestrator.run mocks with _run_engine / plan+execute.\n- test_interrupts.py: use frozenset for PartialExecutionAbortedError; update\n  interrupt tests to use plan()/execute().\n\n* refactor(engine): purge rich from executor.py and dependencies.py\n\n- Remove Console from executor.py, replace console.status() with logger.info()\n- Remove Console from dependencies.py, replace console.status() with logger.info()\n- Update tests to assert on logger.info() instead of console.status()\n\n* feat(__init__): export InitRequest, ExecutionResult, WorkspaceCollisionError\n\n* feat(cli): wire engine logs to rich spinner\n\nAdd SpinnerHandler to route engine INFO logs back to the CLI presentation layer,\nrestoring the execution spinner that was removed during the engine bulkhead refactoring.\n\n* test(integration): patch is_interactive on cli module instead of orchestrator\n\n* docs(api): update API reference to document InitRequest, ExecutionResult, and WorkspaceCollisionError\n\n* docs: document engine bulkhead architecture in CONTRIBUTING.md and docs",
          "timestamp": "2026-08-24T15:47:23-07:00",
          "tree_id": "17f2305edd6ea66f4812443f5f6df248a47deffa",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/99b05b8ccac132b197e48f82e58a505a7576c905"
        },
        "date": 1787611708917,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 149.21,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 212,
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
          "id": "d1566466c74ae3dffcacfa0b7e097fbf86b472e0",
          "message": "chore(deps): lock file maintenance (#193)\n\nCo-authored-by: renovate[bot] <29139614+renovate[bot]@users.noreply.github.com>",
          "timestamp": "2026-08-24T15:47:40-07:00",
          "tree_id": "32e1098780f3c9ed1807553942e7afc4bbf80994",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d1566466c74ae3dffcacfa0b7e097fbf86b472e0"
        },
        "date": 1787611724950,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 153.59,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 217.16,
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
          "id": "67a8c14bbfd0625ef026ccfa2dcb1bb17b984d32",
          "message": "refactor(engine): enforce read-only blueprint invariants by purifying manifest (#195)\n\n- Remove touched_paths and record_touch() from FilesystemManifest\n- Remove diagnostics and add_diagnostic() from EnvironmentManifest\n- Simplify EnvironmentManifest.should_skip_file() to a pure boolean evaluation\n- Shift execution tracking (touched_paths, diagnostics) to SystemExecutor\n- Update Orchestrator.execute() to scrape execution state directly from SystemExecutor\n- Update callers and documentation to align with read-only manifest invariants",
          "timestamp": "2026-08-24T15:58:35-07:00",
          "tree_id": "986819fc099261628d8098ed243a9c21f4c1d838",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/67a8c14bbfd0625ef026ccfa2dcb1bb17b984d32"
        },
        "date": 1787612378994,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 150.53,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 216.77,
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
          "id": "e33456f208debe6b47a202645ed28423aedc94e7",
          "message": "feat(cli): introduce experimental machine interface (--json, --dry-run, export-schema) (#196)\n\n* feat(errors): add hint param to SecurityViolationError\n\nExtends SecurityViolationError with an optional hint keyword argument,\nmatching the pattern already established by ConfigurationError,\nNetworkFetchError, and MissingDependencyError.\n\nThis is a backward-compatible change; all existing call sites continue to\nwork unchanged. The hint parameter allows the JSON error envelope emitted\nin --json mode to carry an actionable remediation message alongside the\nmachine-readable error type and docs URL.\n\n* feat(manifest): add to_dict() serialization to EnvironmentManifest and sub-manifests\n\nImplements deterministic JSON-safe serialization across the full manifest\nhierarchy. Each dataclass gains a to_dict() method following consistent\nserialization rules:\n\n- Sets become sorted lists (directories, vcs_ignores, ci_flags, etc.)\n- Ordered lists preserve semantic insertion order (dependencies, hooks, steps)\n- Enums are coerced to their string .value (CollisionStrategy, CIFlag)\n- SystemTask objects are serialized as explicit {command, description, timeout}\n  dicts rather than flat strings, giving agents full visibility into the\n  exact shell commands that would be executed\n- IDE extension tuples are converted to lists for JSON compatibility\n\nThis serialization layer is the foundation for the --dry-run planned state\noutput and the success payload returned by --json init execution.\n\n* feat(models): add to_dict() serialization to ExecutionResult\n\nProvides a JSON-safe serialization method for the execution outcome returned\nby Orchestrator.execute(). Key serialization choices:\n\n- touched_paths (frozenset[str]) becomes a sorted list for deterministic output\n- Each DiagnosticEvent is serialized as an explicit dict with phase, message,\n  severity (as string value), and an optional detail field that is omitted\n  entirely when None to keep payloads compact\n\nThis method is called by handle_init() to construct the JSON success envelope\nemitted when --json is active after a successful scaffolding run.\n\n* feat(cli): add CLI_API_VERSION, is_json_mode flag, and emit_json() emitter\n\nEstablishes the core JSON mode infrastructure in cli.py:\n\n- CLI_API_VERSION = 0: canonical experiment marker. Increment when the\n  schema stabilises and a compatibility commitment is made.\n- is_json_mode: evaluated eagerly from sys.argv at import time, before\n  argparse runs, guaranteeing position-independence (protostar --json init\n  is equivalent to protostar init --json).\n- emit_json(payload): sole stdout exit path for machine-readable output.\n  Serializes the payload with sorted keys and flushes immediately. Callers\n  must call sys.exit() immediately after.\n- _stderr_console: dedicated Rich Console(stderr=True) used by all JSON-mode\n  output paths to keep stdout clean.\n- configure_logging(): routes the RichHandler to _stderr_console when\n  is_json_mode is active, so --verbose logs never contaminate stdout.\n\n* feat(cli): add JsonAwareParser and pre-parser dispatcher for --json interception\n\nAdds the argparse integration layer for JSON mode:\n\nJsonAwareParser:\n- Subclasses ArgumentParser and overrides error() to emit a structured\n  JSON error envelope (status: error, type: InvalidUsageError) when\n  is_json_mode is active, then exits with os.EX_USAGE. Falls through to\n  the standard argparse error path in human mode.\n- Used for both base_parser and the root parser in build_parser() to\n  ensure all subparsers inherit the behaviour.\n\n_build_capabilities_schema():\n- Introspects the fully-built parser to produce a JSON-serializable map\n  of all subcommands and their flags. Used by the pre-parser dispatcher\n  to self-document the CLI to agents without executing any command.\n\n_dispatch_preparser_flags():\n- Runs in main() after build_parser() but before any parsing or wizard\n  logic. Intercepts three JSON-mode cases:\n  - '--version --json' (any order): emits {version, status, api_version}\n  - '--help --json', '--json --help', or bare '--json': emits the\n    capabilities schema\n  - Falls through for all other invocations\n\n_print_templates_and_exit():\n- Updated to emit a structured list of template objects when is_json_mode,\n  instead of rendering a Rich table to stdout.\n\n* feat(cli): route stdout purity, error envelopes, and crash payloads in JSON mode\n\nEnforces strict JSON mode invariants across the execution pipeline:\n- _run_engine now returns ExecutionResult and immediately re-raises collisions\n  in JSON mode.\n- Untrusted remote templates raise SecurityViolationError without prompting in JSON mode.\n- The Rich spinner is bypassed in JSON mode.\n- ProtostarError handler in main() emits structured JSON error payloads containing\n  type, message, hint, docs_url, and collision paths if applicable.\n- Unhandled Exception handler emits an InternalError JSON envelope and routes\n  the traceback to stderr.\n- KeyboardInterrupt routing sends the abort message to stderr.\n\n* feat(cli): add --dry-run to init subparser with planned state output\n\n- Adds --dry-run argument to the 'init' command.\n- Intercepts execution after engine construction in handle_init.\n- Emits the full, serialized EnvironmentManifest as a JSON envelope in JSON mode.\n- Prints a human-readable diagnostic summary table in interactive mode.\n- Bypasses disk mutations completely.\n\n* feat(cli): add export-schema subcommand for TOML template JSON Schema export\n\n- Adds 'export-schema' subparser to the CLI.\n- Prints the official JSON Schema for Protostar TOML templates to stdout.\n- Uses compact formatting in JSON mode and pretty-printed indenting in human mode.\n\n* test(cli): add JSON mode and dry-run operational invariant tests\n\n- Adds test_agent_roundtrip.py to verify end-to-end flow of agent discovery, planning, and execution.\n- Adds test cases in test_cli.py for JSON output of export-schema and list-templates.\n- Verifies that workspace collisions bubble up correctly into JSON error envelopes.\n\n* fix(cli): register --json argument and bypass interactive wizards\n\n- Registers '--json' in base_parser to prevent InvalidUsageError on parse_known_args().\n- Adds an explicit guard in intercept_interactive_wizards() to never hijack execution when in JSON mode.\n\n* test(cli): fix test failures by using valid template and fixing exception asserts\n\n* docs: update fixtures\n\n* feat(cli): display full dependency, task, and filesystem tree in dry run\n\n* style(cli): refine dry-run output formatting\n\n- Removes descriptions from the dry-run tasks output to show purely the commands.\n- Removes generic emojis from the filesystem tree output and instead uses bold blue coloring with trailing slashes for directories.\n\n* style(cli): unify dry-run output into styled panels with minimal color palette\n\n* feat(cli): add syntax highlighting for human-readable export-schema output\n\n- Uses rich.json.JSON.from_data() in handle_export_schema() when running without --json.\n- Preserves raw compact JSON emission in --json mode.\n\n* docs: document agent interface, dry-run simulation, and JSON schema export\n\n- Adds dedicated 'Agent & Machine Interface' documentation page (docs/usage/agent-interface.md).\n- Updates mkdocs.yml navigation with new agent interface page.\n- Documents --dry-run and --json in docs/usage/init.md and README.md.\n- Documents protostar export-schema in docs/usage/authoring-templates.md.\n- Documents manifest.to_dict() deterministic serialization in docs/mechanics/manifest.md.\n- Documents structured JSON error envelopes in docs/mechanics/error_handling.md.\n\n* docs(contributing): add machine & agent interface invariants and design rules\n\n- Documents strict stdout purity and stderr routing in JSON mode.\n- Documents position-independent --json flag evaluation.\n- Documents zero interactive prompt trapping in machine mode.\n- Documents deterministic .to_dict() state serialization rules.\n- Documents protocol envelopes and api_version contract.\n\n* test(cli): mock subprocesses and dependency installation in agent roundtrip test",
          "timestamp": "2026-08-25T12:54:21-07:00",
          "tree_id": "b8b5447b2b50dd6d4e62f24dd65336ca266af83f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/e33456f208debe6b47a202645ed28423aedc94e7"
        },
        "date": 1787687728299,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 154.24,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 224.87,
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
          "id": "68d4fddcd1f75a8ba318ba4a767fc7a1c58e8dd7",
          "message": "fix(cli): centralize argument parser errors into InvalidUsageError (#197)\n\nOverride JsonAwareParser.error to raise InvalidUsageError rather than delegating\nto super().error in human mode. This routes all argparse parsing failures\n(invalid subcommands, missing required arguments, bad choices) through the\ncentralized ProtostarError handler, ensuring uniform Rich error panel presentation\nin human mode, structured error payloads in JSON mode, and consistent POSIX EX_USAGE\nexit codes across all CLI usage errors.",
          "timestamp": "2026-08-25T13:04:53-07:00",
          "tree_id": "47d27cf3653a0e0c92d4b67a60c5bdc6f8190ef5",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/68d4fddcd1f75a8ba318ba4a767fc7a1c58e8dd7"
        },
        "date": 1787688352837,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 150.34,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 213.18,
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
          "id": "56110c410edaf5cab9e3192679e1758d916c6a93",
          "message": "docs: add cli dry run fixture and svg preview (#198)",
          "timestamp": "2026-08-25T13:30:32-07:00",
          "tree_id": "805b1f9faa33cc661e08654ce8e41e3edd36567d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/56110c410edaf5cab9e3192679e1758d916c6a93"
        },
        "date": 1787689884534,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 119.23,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 169.48,
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
          "id": "f556ae49742416c30d86ca0fc22ce39b3575729e",
          "message": "docs: simplify agent lifecycle sequence diagram and fix rendering padding",
          "timestamp": "2026-08-25T14:06:20-07:00",
          "tree_id": "51289f9e4a4556fad2c6d9f9609fc89d1a7e1df4",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f556ae49742416c30d86ca0fc22ce39b3575729e"
        },
        "date": 1787692051923,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 153.26,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 217.74,
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
          "id": "f5c0f5617102d8047e3779a2af82df59407881de",
          "message": "refactor(docs): robust introspection-driven template schema fixture generation (#199)\n\n- Refactor generate_template_schema_fixture in scripts/generate_doc_fixtures.py to use tomlkit AST generation rather than manual string concatenation.\n- Dynamically introspect TemplateBlueprint dataclass fields to ensure 100% schema coverage and prevent documentation drift.\n- Add mock examples and documentation comments for missing fields (dev_dependencies, appends).\n- Format static file and AST injections with multiline literal strings (''') for clean TOML formatting.\n- Regenerate docs/fixtures/template_schema.toml.",
          "timestamp": "2026-08-25T15:18:47-07:00",
          "tree_id": "eed1fff48ed7c3277343a9efac476a79b0e2bb24",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f5c0f5617102d8047e3779a2af82df59407881de"
        },
        "date": 1787696382799,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 126.63,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 182.85,
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
          "id": "f1f219275f81d6f070c0da31b7a64a10674713c9",
          "message": "refactor: establish single source of truth for template schema (#200)\n\n* feat(schema): add ssot metadata to TemplateBlueprint\n\n* refactor(docs): derive toml schema fixture from TemplateBlueprint metadata\n\n* refactor(cli): dynamically generate json schema from TemplateBlueprint\n\n* fix(cli): correct schema types and dev nesting in export-schema\n\n* docs(readme): add template schema export and validation section",
          "timestamp": "2026-08-25T16:45:19-07:00",
          "tree_id": "cc01d0e8ef9a90996257a9deb3f71515f130071f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f1f219275f81d6f070c0da31b7a64a10674713c9"
        },
        "date": 1787701583070,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 151.07,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 212.56,
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
          "id": "bc4194c38c7a5a29b1f5a6c220fd02de32cba22d",
          "message": "refactor: import tomlkit items directly in doc fixture generator",
          "timestamp": "2026-08-25T16:56:10-07:00",
          "tree_id": "43d5ae1b81a557225d466c158990953d2172f10c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/bc4194c38c7a5a29b1f5a6c220fd02de32cba22d"
        },
        "date": 1787702245727,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 144.78,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 206.91,
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
          "id": "4ac82de7ae4bf0ceefbf5903279017cbab7a3e23",
          "message": "fix(cli): support json mode for help subcommand and scoped capabilities\n\n- Add JSON mode support to dispatch_help for 'protostar help [topic] --json'\n\n- Support command-scoped schema generation in _build_capabilities_schema\n\n- Refactor capability emission into reusable emit_capabilities helper\n\n- Add unit tests for help command in JSON mode",
          "timestamp": "2026-08-25T20:36:36-07:00",
          "tree_id": "b8101fcfb1efb4447b64e6b9a089707a40bd4b99",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/4ac82de7ae4bf0ceefbf5903279017cbab7a3e23"
        },
        "date": 1787715472869,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 148.99,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 212.15,
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
          "id": "8f038db00a96ce1064d5104e07c117bb31483012",
          "message": "fix(wizard): handle missing template aliases gracefully to prevent KeyError",
          "timestamp": "2026-08-25T20:50:36-07:00",
          "tree_id": "64298ed55abb2aa721da6a146cb310c95bf8dc3f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/8f038db00a96ce1064d5104e07c117bb31483012"
        },
        "date": 1787716607990,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 115.71,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 167.94,
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
          "id": "928583f49455551fd151f9edb493ee7842c6f018",
          "message": "fix: eliminate trailing whitespace and formatting friction in generated templates",
          "timestamp": "2026-08-25T22:43:29-07:00",
          "tree_id": "7115d00b5ed3dbe1da4839d165321ec3c36980ea",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/928583f49455551fd151f9edb493ee7842c6f018"
        },
        "date": 1787723092232,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 153.58,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 218.15,
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
          "id": "a427eefa3eb851633d4de0df06c72ce70f8a9b08",
          "message": "fix: eliminate trailing whitespace and formatting friction in generated templates",
          "timestamp": "2026-08-25T22:51:48-07:00",
          "tree_id": "e7374f9060acb02dbe94296eddf7be8ca05221a3",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a427eefa3eb851633d4de0df06c72ce70f8a9b08"
        },
        "date": 1787723568843,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 134.79,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 190.42,
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
          "id": "0061e62933272f8902c48a2de77435f8c835b91c",
          "message": "fix: eliminate trailing whitespace and formatting friction in generated templates",
          "timestamp": "2026-08-25T22:59:25-07:00",
          "tree_id": "c8124dd365fb3539227fadb2706f92782d3818c7",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/0061e62933272f8902c48a2de77435f8c835b91c"
        },
        "date": 1787724049208,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 158.17,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 227.91,
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
          "id": "074327aaab1a3840df3ecddb4c691a378f0b69e8",
          "message": "ci: enforce serial execution for python toolchain\n\nSet `require_serial: true` across `ruff-check`, `ruff-format`, and `mypy`\nto prevent multi-process oversubscription and avoid cache lock collisions.\nDrop redundant `pass_filenames` declarations to rely on the default behavior.",
          "timestamp": "2026-08-25T23:01:58-07:00",
          "tree_id": "6ea14c391af845eecec2cf6bcf409fff174428e0",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/074327aaab1a3840df3ecddb4c691a378f0b69e8"
        },
        "date": 1787724214498,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 151.17,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 218.55,
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
          "id": "496263896fedb57060c359636d8517daddcd4334",
          "message": "feat(tooling): update and split pre-commit and prek scaffolded hooks\n\n- Update generic hooks order and add case-conflict, symlinks, json, and shebang checks\n- Split generic hooks configuration between prek (builtin) and pre-commit (v6.0.0)\n- Add uv-lock-check local hook and gitleaks secrets scanner by default\n- Enforce require_serial for mypy and remove pass_filenames\n- Update fixtures and test suite",
          "timestamp": "2026-08-26T12:01:46-07:00",
          "tree_id": "032b9a7f959e6bf53358738e791126c19dc029b9",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/496263896fedb57060c359636d8517daddcd4334"
        },
        "date": 1787771015653,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 127.45,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 185.6,
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
          "id": "5e3953e21bdbc1aa4e71a8388eea53da983befc6",
          "message": "feat(tooling): update and split pre-commit and prek scaffolded hooks\n\n- Update generic hooks order and add case-conflict, symlinks, json, and shebang checks\n- Split generic hooks configuration between prek (builtin) and pre-commit (v6.0.0)\n- Add uv-lock-check local hook and gitleaks secrets scanner by default\n- Enforce require_serial for mypy and remove pass_filenames\n- Update fixtures and test suite",
          "timestamp": "2026-08-26T12:23:34-07:00",
          "tree_id": "ca6fc41fa42074a89b4bcfee43f6138a140f524b",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/5e3953e21bdbc1aa4e71a8388eea53da983befc6"
        },
        "date": 1787772293298,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 167.81,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 241.99,
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
          "id": "ec681ce3584beb5e7d7ee6b66ce7278eb77bb40a",
          "message": "fix(docs): rename pre-commit config fixtures to prevent hook collisions\n\n- Output pre-commit config fixtures as pre-commit-config.fixture.yaml\n- Prevent prek and pre-commit from treating fixture templates as repository configs\n- Retain YAML syntax highlighting in editors\n- Update snippet inclusion in docs/usage/init.md",
          "timestamp": "2026-08-26T12:24:51-07:00",
          "tree_id": "6ebec6b01bf2ffac87503f2ba1bef24761bb7035",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/ec681ce3584beb5e7d7ee6b66ce7278eb77bb40a"
        },
        "date": 1787772491342,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 150.34,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 213.75,
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
          "id": "f5429ac267ca6f5a1f427932621ae0bbab15343c",
          "message": "feat(tooling): group remote repo pre-commit hooks after local python tooling\n\n- Enforce deterministic pre-commit hook ordering: builtin -> python tooling -> remote repos\n- Move gitleaks to the beginning of the remote repositories section\n- Update fixtures and test suite with structural ordering assertions",
          "timestamp": "2026-08-26T12:32:52-07:00",
          "tree_id": "9ad58e21c7692a4372dbd23bf908106c926762c2",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f5429ac267ca6f5a1f427932621ae0bbab15343c"
        },
        "date": 1787772862669,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 112.03,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 162.4,
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
          "id": "41450151adf039856a55a43ecb8e127a25ecf4f9",
          "message": "feat(tooling): add default install hook types header for commit-msg hooks (#201)\n\n* feat(tooling): add default hook types header for commit-msg hooks\n\n- Add pre_commit_install_hook_types to ToolingManifest for declarative Git hook lifecycle registration\n- Register commit-msg hook type in CommitizenModule\n- Update generate_pre_commit_config to prepend default_install_hook_types and default_stages when commit-msg is required\n- Simplify pre-commit and prek install post-install tasks to standard install commands\n- Update tests and regenerate documentation fixtures\n\n* docs: document git hook lifecycle declaration and header injection",
          "timestamp": "2026-08-26T12:54:50-07:00",
          "tree_id": "6009813b9cc8881582021523d263eb52c3581b7d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/41450151adf039856a55a43ecb8e127a25ecf4f9"
        },
        "date": 1787774154503,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 152.92,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 217.59,
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
          "id": "e91fe3ee195865ad08c5ce36eef728dacf419076",
          "message": "fix(lint): configure ruff bandit rules and resolve diagnostics (#202)\n\n- Enable flake8-bandit (S) rule family in Ruff lint configuration\n- Ignore S603 (untrusted subprocess audit) and S607 (partial executable path) globally\n- Explicitly mark md5 hashing with usedforsecurity=False in appends.py (S324)\n- Narrow broad exception suppression to concrete exceptions in cli.py, wizard.py, and workspace.py (S110)\n- Enforce HTTPS protocol validation in network.py and add inline noqa S310 annotations (S310)\n- Add unit tests verifying rejection of non-HTTPS schemes",
          "timestamp": "2026-08-26T13:02:57-07:00",
          "tree_id": "90a09b96fb1a8a5d3374cd575590624e6e3c8b98",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/e91fe3ee195865ad08c5ce36eef728dacf419076"
        },
        "date": 1787774642374,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 156.49,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 225.38,
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
          "id": "497f8adeb6f0cd0704e6979c6d6d665951998e28",
          "message": "perf(docs): optimize doc fixture generation with host uv cache and parallelization",
          "timestamp": "2026-08-26T14:00:23-07:00",
          "tree_id": "f81ca16d90f28df8d161641a5bde26e0a3b2ecf3",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/497f8adeb6f0cd0704e6979c6d6d665951998e28"
        },
        "date": 1787778199786,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 151.42,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 215.15,
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
          "id": "87cb0678bc271579a426b911451f2de069377b43",
          "message": "refactor(tooling): consolidate documentation fixture recipes into check-fixtures",
          "timestamp": "2026-08-26T14:03:51-07:00",
          "tree_id": "280a6726189fd002db321c94a2bb876d5a2b1fd2",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/87cb0678bc271579a426b911451f2de069377b43"
        },
        "date": 1787778315903,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 178.14,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 245.77,
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
          "id": "7b2f36cb42815d5b68ace7cb9d9db8463400c477",
          "message": "perf(tooling): share host uv cache in macos sandbox and persistent volume in linux sandbox",
          "timestamp": "2026-08-26T14:05:42-07:00",
          "tree_id": "11e6a44e7749326b1ef67e6a052fb7b8de4a4541",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/7b2f36cb42815d5b68ace7cb9d9db8463400c477"
        },
        "date": 1787778563329,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 155.89,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 217.56,
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
          "id": "1067b607197d59f429601864e5d09e3706dbe4f0",
          "message": "feat: migrate to asynchronous static hook registry (#203)\n\n* feat: migrate to asynchronous static hook registry\n\n* test: update tests for async hook registry migration\n\n* docs: document async hook registry architecture\n\n* docs: update fixtures",
          "timestamp": "2026-08-27T14:22:29-07:00",
          "tree_id": "1068bc36acef3247acb258fed89208ddf95a8250",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1067b607197d59f429601864e5d09e3706dbe4f0"
        },
        "date": 1787865818002,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 166.18,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 232.08,
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
          "id": "e6b7faeda321f50e5694d2dae581fd84e1381bed",
          "message": "chore: automate registry fallbacks synchronization for releases (#204)\n\n* refactor: extract default revisions to _fallbacks.py for automated syncing\n\n* chore: automate registry fallbacks synchronization for releases\n\n* fix: resolve mypy error by importing DEFAULT_REVISIONS from _fallbacks in tests\n\n* docs: clarify that offline fallbacks are auto-synced prior to each release",
          "timestamp": "2026-08-27T14:48:10-07:00",
          "tree_id": "d35ba79d3bb14196a5f72528038ad1974741180c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/e6b7faeda321f50e5694d2dae581fd84e1381bed"
        },
        "date": 1787867354878,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 160.21,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 229.31,
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
          "id": "541cbfbadd35324bdfe7b7d8b52cb28bcc975772",
          "message": "perf(demo): transition terminal demo pipeline to asciinema and agg (#205)\n\n* feat(demo): replace VHS pipeline with asciinema and agg recorder\n\n* docs(demo): embed interactive asciinema player and update demo assets",
          "timestamp": "2026-08-27T18:48:39-07:00",
          "tree_id": "83953972b55e5b5aee3efae4da9d4c2a15e7ff98",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/541cbfbadd35324bdfe7b7d8b52cb28bcc975772"
        },
        "date": 1787881781097,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 158.39,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 219.31,
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
          "id": "e53d2c1456813f86e57203b8715e5131b7e50af8",
          "message": "perf(registry): defer remote hook resolution and skip retrieval when unused (#206)\n\n- Introduce RemoteHook.placeholder and HookRegistry.resolve_placeholders() to resolve hook revisions lazily at config generation time\n- Prevent eager HTTP requests during orchestrator.plan() across all tooling modules\n- Bypass remote registry network requests completely when git hooks are disabled or when no remote hooks are present in the workspace\n- Add unit tests verifying zero-network planning and selective placeholder resolution",
          "timestamp": "2026-08-27T19:15:26-07:00",
          "tree_id": "e74db9b4c98320bc7f5e8bfcb07ed28b7910fbd4",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/e53d2c1456813f86e57203b8715e5131b7e50af8"
        },
        "date": 1787883388667,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 151.31,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 215.58,
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
          "id": "ecace03e647164660eea84c1ef790fe99e74541f",
          "message": "perf: lazy import urllib.request to improve CLI startup time",
          "timestamp": "2026-08-27T19:21:32-07:00",
          "tree_id": "9aa25d62786a90d4b7ebfdc07bb70af2a54ec22f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/ecace03e647164660eea84c1ef790fe99e74541f"
        },
        "date": 1787883803473,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 116.21,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 176.52,
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
          "id": "e6014889773729c6b3f2f19ae7646fb16ea4f70f",
          "message": "refactor(errors): abstract POSIX exit codes to cross-platform Enum (#207)\n\n* refactor(errors): abstract POSIX exit codes into ExitCode IntEnum\n\nThis abstracts os.EX_* into an internal enum for better cross-platform support and testability, specifically targeting Windows compatibility. Includes CI updates.\n\n* fix(ci): use bash shell for direnv mock on Windows runners\n\n* chore(scripts): fix mypy unused-ignore cross-platform strictness\n\n* fix(tests): resolve windows specific test failures\n\nThis addresses various windows specific test failures:\n- Adds direnv.cmd to mock step\n- Sets PYTHONIOENCODING=utf-8\n- Skips local blueprint tests on Windows (illegal characters in paths)\n- Normalizes paths for executor assertions\n\n* fix(tests): decode subprocess output as utf-8 on Windows\n\nThis addresses the charmap UnicodeDecodeError in tests/test_exhaustive.py\n\n* fix(windows): resolve executable paths explicitly for subprocess\n\nWindows CreateProcess doesn't always resolve files without extensions from PATH, so we use shutil.which explicitly before delegating to subprocess.run.\n\n* fix(tests): update test_system.py for subprocess mock\n\nSince execute_subprocess now resolves paths explicitly via shutil.which and passes encoding=utf-8, we need to mock shutil.which in tests and update the subprocess.run assertion.\n\n* fix: copy command list in execute_subprocess to avoid mutating caller tasks\n\n* fix(tests): mock shutil.which globally in test_system.py\n\nexecute_subprocess calls shutil.which on the first command argument, which can resolve to absolute paths on runners. We mock it globally for this test module to keep the assertion arguments deterministic.\n\n* docs: clarify cross-platform Windows support\n\n* refactor(system): remove redundant local shutil import",
          "timestamp": "2026-08-27T23:56:48-07:00",
          "tree_id": "33c8a4b3a218ce69da65e8778ecbc23a1b1b5c6c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/e6014889773729c6b3f2f19ae7646fb16ea4f70f"
        },
        "date": 1787900263364,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 111,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 164.28,
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
          "id": "4b12c8d66b02b90315722fbf7f5cd83800e9418c",
          "message": "perf(core): optimize regex evaluation and tar streaming memory (#208)\n\n- Pre-compile static regex patterns at module level in interpolation.py and toml_ast.py\n- Refactor render_template to use single-pass regex replacement instead of multi-pass iteration\n- Stream tar archive members lazily in safe_extract_tar to avoid buffering TarInfo objects\n- Add unit tests for unmatched template placeholders, multiple occurrences, and multi-file tar extraction",
          "timestamp": "2026-08-28T00:05:49-07:00",
          "tree_id": "2f7b66206036f314ac3b1abb03367148ad1c9c6b",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/4b12c8d66b02b90315722fbf7f5cd83800e9418c"
        },
        "date": 1787900815210,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 157.51,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 236.33,
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
          "id": "55772eae2ba2b4a66d79ec9e5368a1c595818404",
          "message": "perf(network): implement connection reuse and regex pre-compilation (#209)",
          "timestamp": "2026-08-28T00:18:38-07:00",
          "tree_id": "20826857718b1febb56e12ddd2a1a37c301808c1",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/55772eae2ba2b4a66d79ec9e5368a1c595818404"
        },
        "date": 1787901580270,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 145.3,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 212.23,
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
          "id": "4991639916ee9a7ad737ae5db02d3367e3aab3ad",
          "message": "ci: optimize workflows with locked dependencies and leaner installations\n\n- Add `--locked` to `uv sync` steps to enforce lockfile consistency across CI\n- Switch benchmark installations to `--no-dev` to only install production\n  dependencies (mirroring real-world CLI usage)\n- Remove explicit `cache-dependency-glob` from setup-uv (action handles this\n  automatically with sensible defaults)\n- Drop `uv run` wrapper in release workflow – `sync_registry_fallbacks.py` uses\n  only the standard library and loads source directly via `sys.path`",
          "timestamp": "2026-08-28T13:33:39-07:00",
          "tree_id": "ad0dbee2b32144dd80481f6cccbb9a133c2f26d2",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/4991639916ee9a7ad737ae5db02d3367e3aab3ad"
        },
        "date": 1787949298147,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 164.13,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 250.89,
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
          "id": "550398a50de69e1b13310cec6b53b3ce7968779b",
          "message": "ci: optimize Windows runner performance and balance matrix load",
          "timestamp": "2026-08-28T13:53:02-07:00",
          "tree_id": "2ec14c2c2a234d8ff63ef15ee138d4bfe4b09512",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/550398a50de69e1b13310cec6b53b3ce7968779b"
        },
        "date": 1787950455194,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 121.01,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 177.16,
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
          "id": "12aced6cb67787350ae6b64fa57947304cd764ab",
          "message": "feat: restrict scaffolded static analysis steps to primary CI runner",
          "timestamp": "2026-08-28T14:02:18-07:00",
          "tree_id": "85c62f2fa0ee79237f95c4faef2ddfed75e0be3f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/12aced6cb67787350ae6b64fa57947304cd764ab"
        },
        "date": 1787951108635,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 116.29,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 170.81,
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
          "id": "64a6bb0816d0c7a4407e88a2765a18bab76c7863",
          "message": "docs: add 'Why Protostar?' comparison guide against Copier and Cookiecutter (#210)\n\nIntroduce a prominent comparison guide and README section articulating Protostar's Python-specialized value proposition over general-purpose template tools.\n\n- Add docs/why-protostar.md featuring MkDocs Material grid cards, interactive tabs, schema tooltips, and comparison matrices\n- Detail template authoring benefits (JSON Schema-backed TOML, zero-logic toggles, zero-overhead Gist sharing) vs Jinja2 syntax limitations\n- Explain non-destructive AST deep-merging vs 3-way Git merge conflicts\n- Update mkdocs.yml navigation and docs/index.md flight paths\n- Feature a condensed 'Why Protostar?' section front-and-center in README.md",
          "timestamp": "2026-08-28T14:29:17-07:00",
          "tree_id": "fbe7b56d8f4ea8e532dac5fe00e4d3ccdefa995d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/64a6bb0816d0c7a4407e88a2765a18bab76c7863"
        },
        "date": 1787952617734,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 144.83,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 212.13,
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
          "id": "d79813207feb16b8722ec69b83b281937143e8e0",
          "message": "chore: harden remote registry client and sync script",
          "timestamp": "2026-08-28T14:36:35-07:00",
          "tree_id": "e49b7d893777aaeeb0e92968c66ddf24456b9fc5",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d79813207feb16b8722ec69b83b281937143e8e0"
        },
        "date": 1787953083773,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 146.31,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 222.65,
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
          "id": "6e3f7e10ca54aa845b2f4df8aa31bdde77c56dc7",
          "message": "ci: lock scaffolded dependencies and omit redundant cache glob",
          "timestamp": "2026-08-28T14:41:22-07:00",
          "tree_id": "4f4cced1671524da6e4706fed0d42d07acad2266",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/6e3f7e10ca54aa845b2f4df8aa31bdde77c56dc7"
        },
        "date": 1787953364190,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 141.61,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 215.91,
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
          "id": "dd182e8a9b6db1befe8be2db374d40aec160cf49",
          "message": "docs: resolve relative link paths and update theme toggle names (#211)\n\n- Correct relative link paths in index.md and getting-started.md from '../' to './'\n- Update palette toggle descriptions in mkdocs.yml to standard light/dark mode terminology and icons",
          "timestamp": "2026-08-29T17:16:32-07:00",
          "tree_id": "645c719a832b86e8915bc8b417085f5ff8d6eecd",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/dd182e8a9b6db1befe8be2db374d40aec160cf49"
        },
        "date": 1788049054868,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 147.62,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 224,
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
          "id": "a560335b34d679c506d71c4e769b7cb37f8bccfa",
          "message": "docs: restructure navigation hierarchy and consolidate tooling matrix (#212)\n\n- Consolidate 'flags/templates.md' and 'flags/tooling.md' into 'usage/tooling-matrix.md'\n- Rename and relocate 'mission-control/' docs to 'developer/'\n- Reorganize mkdocs.yml navigation into User Guide, Mechanics, and Developer Guide\n- Update internal cross-references and links across all docs and README",
          "timestamp": "2026-08-29T17:30:05-07:00",
          "tree_id": "0bbb6694497a5ef744ececce3ee726a97bdc8eac",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a560335b34d679c506d71c4e769b7cb37f8bccfa"
        },
        "date": 1788049864902,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 144.27,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 211.3,
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
          "id": "02647a35e6e4dae3069b76779937091618172d9b",
          "message": "docs: add CLI reference, troubleshooting guide, and expand user guide navigation (#213)\n\n- Add 'usage/cli-reference.md' detailing all subcommands, global options, tri-state flags, and POSIX exit codes\n- Add 'usage/troubleshooting.md' with remediation steps for missing dependencies, collisions, security prompts, and IDE schema setup\n- Update mkdocs.yml User Guide navigation and getting-started.md next steps",
          "timestamp": "2026-08-29T17:40:26-07:00",
          "tree_id": "4dc6d02302e1faa65aaa8f4b82d65bceda3e9663",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/02647a35e6e4dae3069b76779937091618172d9b"
        },
        "date": 1788050485907,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 148.31,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 221.58,
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
          "id": "bbabc041ca05b659bf90f0f2b5c691236048ff9c",
          "message": "ci: inline just benchmark commands in workflows",
          "timestamp": "2026-08-29T18:11:21-07:00",
          "tree_id": "d13f44563d0a29dddd210b9e5e0509adce6017a3",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/bbabc041ca05b659bf90f0f2b5c691236048ff9c"
        },
        "date": 1788052384833,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 142.94,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 210.1,
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
          "id": "58a43a56c012eb0024cc237b4709a77074714113",
          "message": "chore(deps): update astral-sh/setup-uv action to v10 (#214)\n\nCo-authored-by: renovate[bot] <29139614+renovate[bot]@users.noreply.github.com>",
          "timestamp": "2026-08-31T05:53:06Z",
          "tree_id": "e8389e418921ccbc36b545256b609bb13b5f9e05",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/58a43a56c012eb0024cc237b4709a77074714113"
        },
        "date": 1788155649502,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 144.43,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 211.99,
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
          "id": "542221563f2384d2b4d4432e8f728704a9604600",
          "message": "chore(deps): lock file maintenance (#215)\n\nCo-authored-by: renovate[bot] <29139614+renovate[bot]@users.noreply.github.com>",
          "timestamp": "2026-08-31T12:30:17-07:00",
          "tree_id": "1065360c42a6888772c3497b9177cf6480dda3a1",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/542221563f2384d2b4d4432e8f728704a9604600"
        },
        "date": 1788204682625,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 151.04,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 218.42,
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
          "id": "a32c4068e703ad76eb0e64e0a46fe4c6c5e88c83",
          "message": "docs: overhaul documentation styling, frontmatter, and mermaid diagrams (#216)\n\n* Standardize code and terminal blocks with dark theme, cyan borders, 0.68rem typography, and restored hover copy buttons.\n* Constrain hero asciinema demo max-width and fix sticky header title fallback on scroll.\n* Add descriptive SEO frontmatter across all major documentation pages.\n* Refactor dense Mermaid diagrams with LR topologies, condensed edge labels, and responsive horizontal scrolling.",
          "timestamp": "2026-08-31T22:23:35-07:00",
          "tree_id": "a291c6e7c1cbc82f3181441ab92f1ff58d5d7c14",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a32c4068e703ad76eb0e64e0a46fe4c6c5e88c83"
        },
        "date": 1788240283102,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 161.44,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 246.08,
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
          "id": "8d59abfea3600b12a3eb0869a662b582701a9656",
          "message": "docs: add cross-linking and next steps navigation across documentation",
          "timestamp": "2026-08-31T22:34:31-07:00",
          "tree_id": "eabdd5a89c2d960aff578d1abda894d0f62f4e9c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/8d59abfea3600b12a3eb0869a662b582701a9656"
        },
        "date": 1788240947603,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 144.33,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 211.11,
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
          "id": "a47c2b6d2b4b7f34726b1e8ea401e41cc125250a",
          "message": "docs: standardize documentation tone to direct address (\"you\")",
          "timestamp": "2026-08-31T22:38:39-07:00",
          "tree_id": "aac7791791079fe378d98000840e0761df78ed8e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a47c2b6d2b4b7f34726b1e8ea401e41cc125250a"
        },
        "date": 1788241197514,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 147.65,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 215.31,
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
          "id": "38a9a177d6685139da4f5aadf9ff14498bb4d219",
          "message": "docs: add best practices section to authoring templates guide",
          "timestamp": "2026-08-31T22:41:45-07:00",
          "tree_id": "84a57164278e5494af0ad5f9f10c4b8ef09c11d0",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/38a9a177d6685139da4f5aadf9ff14498bb4d219"
        },
        "date": 1788241383598,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 147.47,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 218.06,
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
          "id": "2652fffac5a0ad062b1488e69652aca66fbb6cd1",
          "message": "docs: add design principles page explaining core architectural concepts",
          "timestamp": "2026-08-31T22:52:44-07:00",
          "tree_id": "5e4565cf7da5ace897af5b955b178ef041f3f5c8",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/2652fffac5a0ad062b1488e69652aca66fbb6cd1"
        },
        "date": 1788242040893,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 143.48,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 209.68,
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
          "id": "943b3aa25e8aa07641cc8273dc43b251caf222cc",
          "message": "feat(docs): introduce granular documentation linking and registry (#217)\n\n* docs: link to github issues and discussions in troubleshooting guide\n\n* feat(docs): introduce granular documentation linking and registry\n\n- Add central DocsPage registry for all documentation URLs\n- Link MissingDependencyError to troubleshooting anchor\n- Add anchor support for all ProtostarError types\n- Use difflib to suggest close matches for invalid CLI commands\n- Never default to root index.md; fallback to getting-started.md\n\n* fix(ci): support url anchor fragments in check_doc_links script",
          "timestamp": "2026-09-01T11:09:46-07:00",
          "tree_id": "c32eb1a242bf3d5704ed3a4a4f22341ad83625eb",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/943b3aa25e8aa07641cc8273dc43b251caf222cc"
        },
        "date": 1788286231671,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 87.42,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 130.22,
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
          "id": "87d4d6d4a517fd4cc83796ccc91ff7b07c1bee90",
          "message": "style(docs): strengthen hero title contrast and normalize divider lines to grey",
          "timestamp": "2026-09-01T13:52:56-07:00",
          "tree_id": "f472e54299eaf8c3ae14952d27b0132293282d4e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/87d4d6d4a517fd4cc83796ccc91ff7b07c1bee90"
        },
        "date": 1788296089189,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 112.6,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 173.39,
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
          "id": "57089672fa07209aec7d9ee48783e4fd000a1464",
          "message": "docs: replace CLI reference tables with auto-generated fixtures (#218)\n\n- Generate CLI reference tables dynamically in scripts/generate_doc_fixtures.py:\n  - table_cli_global.md for global options\n  - table_cli_init_core.md for core initialization flags\n  - table_cli_tooling_flags.md from registered TOOLING_MODULES\n  - table_cli_config.md for configuration commands\n  - table_cli_export_schema.md for export schema options\n  - table_exit_codes.md for POSIX exit code mappings\n- Update docs/usage/cli-reference.md to embed fixtures via pymdownx snippets\n- Add test_cli_reference_fixture_tables unit test in tests/test_cli.py",
          "timestamp": "2026-09-01T13:59:30-07:00",
          "tree_id": "8ca36686497ca22bf499ffc16bfbed38374fe889",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/57089672fa07209aec7d9ee48783e4fd000a1464"
        },
        "date": 1788296434420,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 147.89,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 215.88,
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
          "id": "0db2d8da7552b203f8d052b2e592f04dd0e41320",
          "message": "docs: replace hardcoded configuration and agent JSON payloads with dynamic fixtures",
          "timestamp": "2026-09-01T14:42:16-07:00",
          "tree_id": "2313aac62e74c694273cb5803003c8df89856ffa",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/0db2d8da7552b203f8d052b2e592f04dd0e41320"
        },
        "date": 1788299083659,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 159.48,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 236.7,
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
          "id": "812b73874dd4b3bf003472b5e5947b0c86b6b2cc",
          "message": "refactor: standardize template dev_dependencies and remove unused module aliases",
          "timestamp": "2026-09-01T15:23:48-07:00",
          "tree_id": "a7ec01350dfbf4166f4699cf135557e2bf899759",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/812b73874dd4b3bf003472b5e5947b0c86b6b2cc"
        },
        "date": 1788301490119,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 94.23,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 136.14,
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
          "id": "e466e6ff8b0856b27a5dd89c4893e84ff1c8b721",
          "message": "docs: address feedback from documentation review",
          "timestamp": "2026-09-01T20:44:32-07:00",
          "tree_id": "ab74c67df175bff89d08b4ba5022bb19fb49e31f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/e466e6ff8b0856b27a5dd89c4893e84ff1c8b721"
        },
        "date": 1788320742160,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 143.04,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 210.19,
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
          "id": "b3aae605f4ca8807cc1eeda621767ed5d80f0e1b",
          "message": "style(docs): make mermaid diagrams transparent with no border",
          "timestamp": "2026-09-01T21:04:22-07:00",
          "tree_id": "e5ab99e58bab3f237b5468a9ad596426b90f1015",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/b3aae605f4ca8807cc1eeda621767ed5d80f0e1b"
        },
        "date": 1788321947189,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 145.85,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 213.88,
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
          "id": "87c69b90b8c1d33a7b03c3278beea80f9162dd27",
          "message": "docs: streamline documentation by removing excessive grid cards and consolidating nested tabs\n\n- Removed redundant grid cards in docs/design-principles.md and other docs.\n- Consolidate template fixture sub-tabs in docs/usage/init.md.\n- Replaced multiple 'Before'/'After' fixture tabs with dynamic unified diff blocks.\n- Added automated unified diff fixture generation to scripts/generate_doc_fixtures.py.",
          "timestamp": "2026-09-01T21:47:23-07:00",
          "tree_id": "1d30b57c543967ec107361c64b9fbb2191227a84",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/87c69b90b8c1d33a7b03c3278beea80f9162dd27"
        },
        "date": 1788324590635,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 145.71,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 213.92,
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
          "id": "09f565133367c10d205be05caa1f16b8ad017303",
          "message": "chore(docs): remove obsolete old-mkdocs.yml",
          "timestamp": "2026-09-01T21:50:16-07:00",
          "tree_id": "aca86a24cb9b409cd33ba8f2b979b2f9cdeee3e0",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/09f565133367c10d205be05caa1f16b8ad017303"
        },
        "date": 1788324765767,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 147.23,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 218.12,
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
          "id": "9e88d5f10d819243e1b78ce05464ffae16e64b19",
          "message": "docs: update site_url path in zensical.toml",
          "timestamp": "2026-09-01T21:52:09-07:00",
          "tree_id": "4715594d98e6e51af6e2191830675461e37c8f61",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/9e88d5f10d819243e1b78ce05464ffae16e64b19"
        },
        "date": 1788324800201,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 143.17,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 209.87,
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
          "id": "71f666e30f7d7107d62fc685f4e569bdc48aa852",
          "message": "docs: clean up unused zensical features and remove legacy toc css",
          "timestamp": "2026-09-02T10:01:40-07:00",
          "tree_id": "258f1052ddb4ca23f4a1378fae8241d5491525d7",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/71f666e30f7d7107d62fc685f4e569bdc48aa852"
        },
        "date": 1788368787941,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 147.15,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 216.52,
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
          "id": "fc7758407089da190cc1b7f862dc9cc07b8e7606",
          "message": "docs: inline hero copy button script on homepage and remove protostar.js",
          "timestamp": "2026-09-02T10:06:52-07:00",
          "tree_id": "990697c28b6f3c33b9ae3da3892ce89a910e909c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/fc7758407089da190cc1b7f862dc9cc07b8e7606"
        },
        "date": 1788369009469,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 139.33,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 207.25,
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
          "id": "2a85f26aeb99ab905f4d09e50e534f646db196c8",
          "message": "docs: align light and dark mode hero styling and remove unused css",
          "timestamp": "2026-09-02T10:16:36-07:00",
          "tree_id": "91de02ccfe2a369776e417904e2ff92585e5abc7",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/2a85f26aeb99ab905f4d09e50e534f646db196c8"
        },
        "date": 1788369523727,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 157.36,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 235.36,
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
          "id": "a5a8524f0a43e6fbe5aa9ba0b0db49e8e1fdea3c",
          "message": "style(docs): enable light and dark mode switching for code and install boxes",
          "timestamp": "2026-09-02T10:47:43-07:00",
          "tree_id": "160dfb981ee8a9220bb4e96c876dab00539959d8",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a5a8524f0a43e6fbe5aa9ba0b0db49e8e1fdea3c"
        },
        "date": 1788371366194,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 143.8,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 210.18,
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
          "id": "d3a4da5a97b070924cfa712adb88f16b135eee59",
          "message": "docs: clean up unused and redundant custom css",
          "timestamp": "2026-09-02T10:55:23-07:00",
          "tree_id": "78441bcc16bd3d71471a28a63a607c7e14371890",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d3a4da5a97b070924cfa712adb88f16b135eee59"
        },
        "date": 1788371831531,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 144.68,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 213.61,
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
          "id": "973d0b934cc5b5164298e1ebdeba1e3c67473d5c",
          "message": "docs: move getting started ahead of why protostar in nav",
          "timestamp": "2026-09-02T11:01:04-07:00",
          "tree_id": "b8a7ca7fc245cdceb56223a951adfed2a67d42bc",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/973d0b934cc5b5164298e1ebdeba1e3c67473d5c"
        },
        "date": 1788372239284,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 111.22,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 165.13,
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
          "id": "a27b6732b264c08de8e8fb9e7d1aacfb63240077",
          "message": "docs: remove redundant kickers from why protostar and design principles",
          "timestamp": "2026-09-02T11:03:22-07:00",
          "tree_id": "0ce24c5ec845558862305040efffac997fc07103",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a27b6732b264c08de8e8fb9e7d1aacfb63240077"
        },
        "date": 1788372277442,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 126.11,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 188.64,
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
          "id": "534139b5216b2375c02b05ff1fd55285f556467b",
          "message": "refactor(docs): simplify custom css and streamline documentation layout (#219)\n\n* docs: resolve phantom css variables and redundant fallbacks\n\n* docs: remove protostar-terminal wrapper and clean up code block styles\n\n* docs: consolidate duplicate card implementations\n\n* docs: move typography and footer layout out of dark mode block\n\n* docs: clean up heading styles, syntax overrides, and spacer markup",
          "timestamp": "2026-09-02T14:33:58-07:00",
          "tree_id": "e02bbb9ce03545336bcab4c481ede5fe23db97e1",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/534139b5216b2375c02b05ff1fd55285f556467b"
        },
        "date": 1788384904622,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 155.4,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 232.52,
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
          "id": "41037302effa425814fd3dba7929e526e49f9865",
          "message": "docs: create two-column hero layout and restore seamless footer styling",
          "timestamp": "2026-09-02T14:55:18-07:00",
          "tree_id": "eda220e6712f5bccc01b795a7e73375c44631ca0",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/41037302effa425814fd3dba7929e526e49f9865"
        },
        "date": 1788386194933,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 112.15,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 163.41,
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
          "id": "72fd967b50def5c834a9f292219150b376df1c15",
          "message": "docs: use sun and moon icons for light and dark mode toggles",
          "timestamp": "2026-09-02T14:57:14-07:00",
          "tree_id": "cd2c88ef126f53911f026d846f153a942b0e8770",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/72fd967b50def5c834a9f292219150b376df1c15"
        },
        "date": 1788386370008,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 105.61,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 155.07,
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
          "id": "52e1d7675a5b2ecab70163d74ddc30d0a6676f6b",
          "message": "docs: simplify high-friction, academic, and marketing phrasing",
          "timestamp": "2026-09-02T15:10:54-07:00",
          "tree_id": "71a8c0feeeff835092486424c5790219387d51dd",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/52e1d7675a5b2ecab70163d74ddc30d0a6676f6b"
        },
        "date": 1788387145558,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 143.07,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 214.35,
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
          "id": "7bc2d12aad2717b9c671ccf090d91881a71db46c",
          "message": "chore: replace conventional-pre-commit with gitfluff",
          "timestamp": "2026-09-02T15:24:20-07:00",
          "tree_id": "50872d7a0ebede85f7647a0bc19a2fb191db578a",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/7bc2d12aad2717b9c671ccf090d91881a71db46c"
        },
        "date": 1788387935167,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 144.25,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 213.04,
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
          "id": "a5e42151f9e4b526e9d810cbb932b850d83f3afa",
          "message": "refactor(cli): replace high-friction sci-fi terminology in error and task messaging",
          "timestamp": "2026-09-02T15:28:03-07:00",
          "tree_id": "37fa9a206a17abab3747b8780ae55ac0e272d98c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a5e42151f9e4b526e9d810cbb932b850d83f3afa"
        },
        "date": 1788388144931,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 105,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 158.08,
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
          "id": "e77fb5ff3103e09bae08da8b52ff0bcbdd46784f",
          "message": "docs: shrinkwrap svg documentation fixtures to terminal output",
          "timestamp": "2026-09-02T15:34:48-07:00",
          "tree_id": "b9349490282d775926c336aa1a1f9c1b2a1036aa",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/e77fb5ff3103e09bae08da8b52ff0bcbdd46784f"
        },
        "date": 1788388595228,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 149.23,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 221.79,
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
          "id": "68e77b3ead8a5625169cab21d4c62a0d149d5d97",
          "message": "chore: migrate from markdownlint-cli2 to rumdl for Markdown linting/formatting\n\nReplace markdownlint-cli2 with rumdl, a faster Rust-native Markdown linter\nand formatter, to improve performance and simplify configuration.\n\nKey changes:\n- Remove root and docs/ markdownlint-cli2 YAML configs\n- Add rumdl configuration to pyproject.toml with:\n  - Global rule overrides (MD013, MD033, MD077 disabled)\n  - Enforced styles (ATX headings, dash lists, \"one\" ordered lists)\n  - Per-file ignores for docs/ (MD041, MD046 relaxed)\n- Update CI workflow: replace markdownlint-cli2 action with rumdl check/fmt\n- Update pre-commit hooks: replace markdownlint-cli2 with rumdl check/fmt\n- Update justfile format/lint targets to use rumdl\n- Add rumdl to ci dependency group in pyproject.toml\n- Clean up obsolete markdownlint-disable comments in docs files\n- Fix minor Markdown issues revealed by rumdl (list numbering consistency)",
          "timestamp": "2026-09-02T16:25:06-07:00",
          "tree_id": "c6f6f58bd78340851af90696318a2ce342352236",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/68e77b3ead8a5625169cab21d4c62a0d149d5d97"
        },
        "date": 1788392141008,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 147.68,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 219.23,
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
          "id": "1ed7a96f3e95df5908006e8805291e11c18e3594",
          "message": "ci: configure pre-push hooks and add doc link checking to local CI",
          "timestamp": "2026-09-02T16:48:45-07:00",
          "tree_id": "db2ac22c119b9ea8cf54465042f238a408b6b0ee",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1ed7a96f3e95df5908006e8805291e11c18e3594"
        },
        "date": 1788393186200,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 112.63,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 167.34,
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
          "id": "00724051701c39478ea363c80319a858056565bb",
          "message": "ci: separate lint and docs into dedicated jobs",
          "timestamp": "2026-09-02T17:01:23-07:00",
          "tree_id": "7d188ee9cb5b936ed83cde6326329fd1c6e89b2b",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/00724051701c39478ea363c80319a858056565bb"
        },
        "date": 1788393781553,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 144.01,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 210.91,
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
          "id": "dfba8aa522293128dcf76d61639e4aeb4c16efa6",
          "message": "docs: use dynamic ReadTheDocs status badge in README",
          "timestamp": "2026-09-02T17:02:21-07:00",
          "tree_id": "6e1c8bfff3731834bb172a67ee32ac042c18ff7f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/dfba8aa522293128dcf76d61639e4aeb4c16efa6"
        },
        "date": 1788393835611,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 129.76,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 191.82,
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
          "id": "a67f79a90ee9474357bddad93109477dd67f08ce",
          "message": "ci: create reusable mock-direnv composite action",
          "timestamp": "2026-09-02T17:05:43-07:00",
          "tree_id": "e0c7b70991f90147e56261e7b495e7bf204b9b18",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a67f79a90ee9474357bddad93109477dd67f08ce"
        },
        "date": 1788394102877,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 139.55,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 204.46,
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
          "id": "64737d35b7886fdcd468c9a30cf5a10d6be2e303",
          "message": "docs: eliminate unhelpful documentation redundancies and unify fixture snippets (#220)\n\n* docs: streamline orchestrator execution topology diagram\n\n* docs: clarify persona boundaries between template consumption and authoring\n\n* docs: unify POSIX exit codes table across documentation using snippet\n\n* docs: include Docker container scaffolding in tooling capabilities matrix\n\n* docs: consolidate telemetry and crash reporting documentation into error_handling.md\n\n* docs: streamline opinionated templates section in init.md\n\n* test: update fixture assertion for 4-column exit codes table",
          "timestamp": "2026-09-02T20:09:45-07:00",
          "tree_id": "9a8276f82d5b7edf0acb56584671e4e9008dc541",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/64737d35b7886fdcd468c9a30cf5a10d6be2e303"
        },
        "date": 1788405048062,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 147.75,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 222.41,
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
          "id": "4a7353e96dd734ab8079beea35d45e563f407ad6",
          "message": "ci: add zensical build pre-push hook",
          "timestamp": "2026-09-02T20:10:21-07:00",
          "tree_id": "713ce79c80d1ccf948eff32398f515aabd6745d3",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/4a7353e96dd734ab8079beea35d45e563f407ad6"
        },
        "date": 1788405128002,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 145.85,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 217.04,
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
          "id": "da9e661bcf3c5e8a71d6489e35e076da9efaa46e",
          "message": "docs: remove confusing prerequisites from getting started page",
          "timestamp": "2026-09-02T20:21:27-07:00",
          "tree_id": "17a35173bb36a447c7928806b1fdc066ebf9c307",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/da9e661bcf3c5e8a71d6489e35e076da9efaa46e"
        },
        "date": 1788405882028,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 144.69,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 213.43,
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
          "id": "46e17a364a22e47ecb41eb0bbc1168fc5192e316",
          "message": "refactor: centralize questionary with typed lazy wrappers",
          "timestamp": "2026-09-03T14:55:02-07:00",
          "tree_id": "2a519c5adaaf5e5aec641a957fa8d4f5c873385f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/46e17a364a22e47ecb41eb0bbc1168fc5192e316"
        },
        "date": 1788472729770,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 119.9,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 176.12,
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
          "id": "c082b6c86e5e35ad3fdc76b824fec6976ba0b133",
          "message": "feat(tooling): add rumdl module and set as default for production templates (#221)\n\n* feat: add rumdl module and enable for production-facing templates\n\n* style(toml): add # ---- rumdl ---- # section header for rumdl tooling config\n\n* fix(fixtures): replace --markdownlint with --rumdl and prune stale files\n\n* refactor(fixtures): simplify fixture matrices to pure template invocations\n\n* feat(ci): add --output-format github to rumdl workflow commands\n\n* fix(ide): make rumdl vscode installation optional and non-fatal\n\n* docs(fixtures): add maintainer note on ml docker fixture exception\n\n* refactor(executor): remove rumdl vscode execution from SystemExecutor",
          "timestamp": "2026-09-03T16:27:48-07:00",
          "tree_id": "38d74f7ec4aec3f78c3307993ff6d215a12e27a0",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/c082b6c86e5e35ad3fdc76b824fec6976ba0b133"
        },
        "date": 1788478138579,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 156.2,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 225.44,
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
          "id": "c0ec9f4a5d1473558c7fc2f68366c40eb9f5e348",
          "message": "refactor(ci): separate lint job and streamline matrix coverage include",
          "timestamp": "2026-09-03T16:34:19-07:00",
          "tree_id": "bc5876f6b894ad7a067e7e10c72a47a5f2132b6c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/c0ec9f4a5d1473558c7fc2f68366c40eb9f5e348"
        },
        "date": 1788478545563,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 149.43,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 218.55,
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
          "id": "506c4e85382cde2f0bb8b8c295bc33e20031a0d2",
          "message": "docs: align documentation and configuration with rumdl defaults (#222)",
          "timestamp": "2026-09-03T16:43:03-07:00",
          "tree_id": "a21c2e66b2495545ef28edc4b55d2f97eafeec64",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/506c4e85382cde2f0bb8b8c295bc33e20031a0d2"
        },
        "date": 1788479043583,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 147.52,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 223.19,
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
          "id": "7829ccd5e0dff9a91cd7ead65f392da3c0e6841d",
          "message": "refactor: polish ui module typing and docstrings",
          "timestamp": "2026-09-03T16:44:19-07:00",
          "tree_id": "2ea7d516eb8465f9935b9cd70611172ed7cf4a5b",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/7829ccd5e0dff9a91cd7ead65f392da3c0e6841d"
        },
        "date": 1788479165761,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 155.56,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 234.59,
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
          "id": "a91327234db44899ba0ee6f3b7e9fb763b2cdeed",
          "message": "refactor: polish ui module typing and docstrings",
          "timestamp": "2026-09-03T16:51:36-07:00",
          "tree_id": "b6e4d1fd8b4fa15c06f9b7d5bf5bea0c1ac78402",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a91327234db44899ba0ee6f3b7e9fb763b2cdeed"
        },
        "date": 1788479632964,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 122.22,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 186.65,
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
          "id": "c1e04112d6b45f0c149abfd7474b6aa7d7f2b7a0",
          "message": "feat: respect XDG_CONFIG_HOME for config file resolution",
          "timestamp": "2026-09-03T18:20:14-07:00",
          "tree_id": "908361f432539704d00e7613397c178e0ee9d5d4",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/c1e04112d6b45f0c149abfd7474b6aa7d7f2b7a0"
        },
        "date": 1788484887194,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 145,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 205.1,
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
          "id": "d027fe30ac6619cf2f25075ea3b5697e24fb7939",
          "message": "test: isolate XDG_CONFIG_HOME in run_cli to fix integration tests",
          "timestamp": "2026-09-03T18:31:00-07:00",
          "tree_id": "b20bfb9ac86b7b9ac9233476e749985ce0f46320",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d027fe30ac6619cf2f25075ea3b5697e24fb7939"
        },
        "date": 1788485543102,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 146.22,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 211.9,
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
          "id": "74e6370b33f04638654035012fd51a0cec952c98",
          "message": "feat: respect XDG_CONFIG_HOME for config file resolution",
          "timestamp": "2026-09-03T18:37:37-07:00",
          "tree_id": "b20bfb9ac86b7b9ac9233476e749985ce0f46320",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/74e6370b33f04638654035012fd51a0cec952c98"
        },
        "date": 1788485935709,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 147.03,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 212.79,
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
          "id": "26052dadfd6c56fb29f46e173fdf4fcc2d930bb0",
          "message": "chore(deps): lock file maintenance (#223)\n\nCo-authored-by: renovate[bot] <29139614+renovate[bot]@users.noreply.github.com>",
          "timestamp": "2026-09-09T16:24:38-07:00",
          "tree_id": "b6061fa1c95fe2696fed0b7690f2b9586067ede8",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/26052dadfd6c56fb29f46e173fdf4fcc2d930bb0"
        },
        "date": 1788996341236,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 149.21,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 222.52,
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
          "id": "7cb91ae943224343a7667349db5a7a8459ee4b4d",
          "message": "docs: comprehensive documentation polish and DRY exit codes (#224)\n\n* docs: add reporting contact email to code of conduct\n\n* docs: clarify quick start and fix typo in index\n\n* docs: refine Copier vs Cookiecutter comparison\n\n* docs: align type hinting guide with mypy strict config\n\n* docs: hide snippet macro in GitHub raw view\n\n* docs: explicitly tag stateful modules in executor docs\n\n* docs: clarify tri-state toggles and add pipx alternative\n\n* docs: cross-reference source tree in modules guide\n\n* docs: use raw string for justfile content in extending guide\n\n* docs: inject DRY exit codes table into CONTRIBUTING.md",
          "timestamp": "2026-09-09T16:36:05-07:00",
          "tree_id": "033831736b82983e708307c6bb5d05f7651faa38",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/7cb91ae943224343a7667349db5a7a8459ee4b4d"
        },
        "date": 1788997029644,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 149.8,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 206.48,
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
          "id": "4011c62bc512dc55c57bf6afbb32f65b05b5fdda",
          "message": "feat: dynamic homebrew missing dependency aggregation (#225)\n\n* feat: aggregate missing dependencies and dynamically generate homebrew hint\n\n* feat: append shell reload instructions to missing dependencies\n\n* feat: provide OS and shell specific reload instructions\n\n* refactor: remove alternative hints from aggregated pre-flight UI\n\n* refactor: eliminate dead MissingDependencyError fields and dead hints",
          "timestamp": "2026-09-09T17:59:25-07:00",
          "tree_id": "0d38cbe8489659b59929d2b5af8d7fffbbebb50d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/4011c62bc512dc55c57bf6afbb32f65b05b5fdda"
        },
        "date": 1789002030461,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 147.44,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 216.56,
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
          "id": "fec9ff6591af5e75e2141ea2312dd26a0705ab26",
          "message": "chore: migrate performance benchmarks to /benchmarks/ directory",
          "timestamp": "2026-09-09T18:02:47-07:00",
          "tree_id": "c413c2255222f4ff5d370ffeca6660156438f471",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/fec9ff6591af5e75e2141ea2312dd26a0705ab26"
        },
        "date": 1789002245445,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 152.06,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 224.52,
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
          "id": "998cdb6b6f985215b6b924ffed98ef1716d8cfca",
          "message": "docs: standardize project tagline across codebase and configuration",
          "timestamp": "2026-09-09T18:09:57-07:00",
          "tree_id": "2d1389fce038199bbb162f98bbd92709683fd41f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/998cdb6b6f985215b6b924ffed98ef1716d8cfca"
        },
        "date": 1789002677160,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 145.59,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 212.87,
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
          "id": "53841d11352427ced9dee6a6b6a09f8a153e01ce",
          "message": "fix: resolve core stability, encoding, and CLI import-time side effects (#226)\n\n* chore: ignore log files in repository gitignore\n\n* perf: lazy-load package version to reduce startup latency\n\n* fix(errors): use urljoin for docs url construction\n\n* fix(executor): enforce utf-8 encoding on file reads\n\n* refactor(cli): avoid module-level argv evaluation and argv mutation",
          "timestamp": "2026-09-09T18:25:42-07:00",
          "tree_id": "ac77f47d82eecf29ec7dab6f26417798546bf44c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/53841d11352427ced9dee6a6b6a09f8a153e01ce"
        },
        "date": 1789003604393,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 134.85,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 210.45,
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
          "id": "07a1748f1401c07cdd6023e6b5c929dbd1fc6aff",
          "message": "refactor(workflows): streamline YAML generation with lightweight YAMLBuilder (#227)\n\n* build: update sdist exclusions in pyproject.toml\n\n* refactor(workflows): streamline YAML generation with lightweight YAMLBuilder",
          "timestamp": "2026-09-09T19:04:09-07:00",
          "tree_id": "3795b0f3a4a636a8108e52f45356092ee3cc7958",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/07a1748f1401c07cdd6023e6b5c929dbd1fc6aff"
        },
        "date": 1789005905266,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 130.66,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 201.59,
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
          "id": "ba12ec74fd54b89404c84c7f9d6c984a3e711009",
          "message": "chore(docs): sync demo theme and conclude on file preview\n\n- Centralize demo theme definition in scripts/record_demos.py as single source of truth\n- Remove redundant theme override in justfile so agg inherits theme from cast header\n- End demo directly on pyproject.toml preview without quitting bat\n- Regenerate .cast and .gif assets for headless and wizard demos",
          "timestamp": "2026-09-09T19:54:51-07:00",
          "tree_id": "0692fbd0b7c88c21d8ff698bf7ed664056c8d17f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/ba12ec74fd54b89404c84c7f9d6c984a3e711009"
        },
        "date": 1789009015206,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 143.41,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 226.53,
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
          "id": "062592a3b09049e4ab7cb273c810b95648ce507c",
          "message": "test: modernize test suite and add missing module coverage (#228)\n\n* test(docs_registry): add unit tests for docs registry enum and paths\n\n* test(ui): add unit tests for lazy prompt wrappers and selection helpers\n\n* test(errors): consolidate domain exception tests into test_errors.py\n\n* test(executor): refactor mocked Path operations to use tmp_path",
          "timestamp": "2026-09-09T20:07:10-07:00",
          "tree_id": "0d2b538551e8497bf6bba8cb6b6015c030987c30",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/062592a3b09049e4ab7cb273c810b95648ce507c"
        },
        "date": 1789009690085,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 133.27,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 204.52,
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
          "id": "63fd9e3540ae6bec36db1720b6b52592cdef3a69",
          "message": "refactor(cli): decompose monolithic cli into submodules (#229)\n\n- Break src/protostar/cli.py into main, parser, schema, and ui.\n- Improve separation of concerns for the CLI orchestration.\n- Update test suite to reflect the new package structure.",
          "timestamp": "2026-09-09T20:58:11-07:00",
          "tree_id": "64ee84c1904fc05e0309ecb9119079dcd24814f6",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/63fd9e3540ae6bec36db1720b6b52592cdef3a69"
        },
        "date": 1789012740287,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 102.02,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 158.41,
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
          "id": "f0aa1d82d9cfd4378323f91de8f0a487b458a9d7",
          "message": "fix(justfile): enforce strict error handling and pre-checks in bump recipe",
          "timestamp": "2026-09-10T11:38:06-07:00",
          "tree_id": "9c3ea12c4cae112ec8cd13ef43822a40d1743d42",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f0aa1d82d9cfd4378323f91de8f0a487b458a9d7"
        },
        "date": 1789065569578,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 139.13,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 226.81,
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
          "id": "89a3412a37055e0eaf30bd6e31c8cd844443ca25",
          "message": "feat(release): harden bump recipe with read-only preflights and rollback guard",
          "timestamp": "2026-09-10T11:44:30-07:00",
          "tree_id": "870614c1f7ce68f3244438b5c32670e876ea064d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/89a3412a37055e0eaf30bd6e31c8cd844443ca25"
        },
        "date": 1789066013872,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 135.22,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 205.69,
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
          "id": "9e85ddbc3f7634d0deb01b31fb9fd57f6789826e",
          "message": "feat(release): delegate release workflow to centralized ci-cd-tooling script",
          "timestamp": "2026-09-10T11:56:12-07:00",
          "tree_id": "8ba93ced80b383b02db7e57482cec5a375d995b1",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/9e85ddbc3f7634d0deb01b31fb9fd57f6789826e"
        },
        "date": 1789066649521,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 138.32,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 218.22,
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
          "id": "8846da902755ed9c2a1a8212401eb76528ea9206",
          "message": "chore(justfile): add --refresh to release.py call",
          "timestamp": "2026-09-10T12:09:53-07:00",
          "tree_id": "b0804e2fd904b8f0d2d1ad4e22a602c909d0897d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/8846da902755ed9c2a1a8212401eb76528ea9206"
        },
        "date": 1789067464096,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 110.8,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 170.68,
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
          "id": "84d6be493c4839903b9babad5b048c9aee8229d1",
          "message": "chore: bump version to 0.9.0",
          "timestamp": "2026-09-10T12:18:52-07:00",
          "tree_id": "62760f55345d320d798965a01e01ea5d9345bab3",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/84d6be493c4839903b9babad5b048c9aee8229d1"
        },
        "date": 1789068004500,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 132.31,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 204.72,
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
          "id": "9b9dd8b6bade9fc636578ab3e7c4c80e41d93c71",
          "message": "ci: update pypa/gh-action-pypi-publish pin to support Metadata 2.5",
          "timestamp": "2026-09-10T12:26:38-07:00",
          "tree_id": "c72c6f56519ddb468e2f89bf7512e904de0b45f3",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/9b9dd8b6bade9fc636578ab3e7c4c80e41d93c71"
        },
        "date": 1789068478770,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 135.35,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 207.38,
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
          "id": "06e2ab8c1a380e43682984b73d9d4477f466a225",
          "message": "chore(justfile): drop ci dependency from bump recipe",
          "timestamp": "2026-09-10T12:35:11-07:00",
          "tree_id": "843ffda6f15995c0051d1c77b818a317b97059c8",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/06e2ab8c1a380e43682984b73d9d4477f466a225"
        },
        "date": 1789068989452,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 132.25,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 203.14,
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
          "id": "4735c5f370be8ccc31c3a0eac8048f479c3f2058",
          "message": "docs: update Read the Docs links to /stable/\n\nRemove the `/en/` locale prefix from all Read the Docs URLs in the README,\ncovering the documentation badge, official docs, agent interface guide,\ntemplate authoring guide, and developer overview links.",
          "timestamp": "2026-09-10T16:40:32-07:00",
          "tree_id": "b706714455df50b403ab8a62d414ed988f48973a",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/4735c5f370be8ccc31c3a0eac8048f479c3f2058"
        },
        "date": 1789083726394,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 138.47,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 212.79,
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
          "id": "032b2fbb3949b00332814d5eff8dffd0dcc7f3a0",
          "message": "docs: tidy README headings and formatting\n\n- Remove emojis from section headings for a cleaner look\n- Drop redundant `---` dividers around the demo image\n- Add a divider before the Contact section\n- Minor punctuation fix in the License section",
          "timestamp": "2026-09-10T16:58:02-07:00",
          "tree_id": "6a4795da1027f62b1a8054b5daeedfea74572e1e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/032b2fbb3949b00332814d5eff8dffd0dcc7f3a0"
        },
        "date": 1789085270279,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 138.58,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 212.29,
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
          "id": "9b54ce905ef777459b2f4b30a6e9d66ddd95d68e",
          "message": "docs: add quick links to README header\n\nAdd a row of navigation links to key documentation pages (Get Started,\nDocs, Why Protostar?, Design Principles, Authoring Templates,\nTroubleshooting) below the badge row for faster access.",
          "timestamp": "2026-09-10T17:06:50-07:00",
          "tree_id": "216bc11a3156c72f7b34de684b197412740e7879",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/9b54ce905ef777459b2f4b30a6e9d66ddd95d68e"
        },
        "date": 1789085279626,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 107.19,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 167.2,
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
          "id": "da8f8abeaa6eeeefb1b5b4e226fee62676efd6bd",
          "message": "docs: add AGENTS.md with architectural invariants and development guidelines",
          "timestamp": "2026-09-10T17:38:31-07:00",
          "tree_id": "e04370346286af1456833b754a2661c85cd084c9",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/da8f8abeaa6eeeefb1b5b4e226fee62676efd6bd"
        },
        "date": 1789087185089,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 130.88,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 201.82,
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
          "id": "9b54ce905ef777459b2f4b30a6e9d66ddd95d68e",
          "message": "docs: add quick links to README header\n\nAdd a row of navigation links to key documentation pages (Get Started,\nDocs, Why Protostar?, Design Principles, Authoring Templates,\nTroubleshooting) below the badge row for faster access.",
          "timestamp": "2026-09-10T17:06:50-07:00",
          "tree_id": "216bc11a3156c72f7b34de684b197412740e7879",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/9b54ce905ef777459b2f4b30a6e9d66ddd95d68e"
        },
        "date": 1789087931135,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 143.4,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 224.8,
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
          "id": "f1aad2c6d799270f2a41fc05afaeef6c4d16d796",
          "message": "feat(cli): cross-platform dynamic shell autocompletion and detection (#230)\n\n* feat(cli): add completion command and shell setup instructions\n\n* feat(cli): attach rich completers for templates and configuration flags\n\n* test(cli): add cross-platform tests for POSIX and Windows shell completion protocols\n\n* feat(cli): dynamically detect user shell and tailor completion setup instructions\n\n* feat(cli): adopt zero-startup-overhead static file completion across shells\n\n* style(cli): redesign completion guide to borderless copy-friendly layout\n\n* feat(cli): streamline completion guide to detected shell and remove redundant headers\n\n* style(cli): update completion guide commands to protostar cyan theme",
          "timestamp": "2026-09-10T19:47:00-07:00",
          "tree_id": "ef85ebd498d0648d399ab2fad8810dcd0751e866",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f1aad2c6d799270f2a41fc05afaeef6c4d16d796"
        },
        "date": 1789094875884,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 133.15,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 205.55,
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
          "id": "b46766643b3536a22f2d91e4642d5b57adfaefc9",
          "message": "feat(templates): centralized metadata discovery, explicit trust boundary, and CLI UX improvements (#231)\n\n* feat(config): add name and description metadata to templates and blueprint\n\n* feat(config): support rich template alias metadata and trust flag in user config\n\n* feat(templates): implement centralized zero-network template discovery engine\n\n* feat(cli): enforce explicit template trust boundary and warning bypass\n\n* feat(cli): wire centralized template discovery into list-templates, completion, and wizard\n\n* docs: update documentation and README for template metadata, trust configuration, and autocompletion\n\n* feat(wizard): format template choices with display name, aligned columns, and middle dot separator\n\n* feat(cli): optimize list-templates table layout and dual name resolution\n\n* feat(cli): display template names directly without alias annotations in table\n\n* fix(cli): eliminate nargs=? on template option to scope tab completion to templates\n\n* chore(tests): remove unused fixtures and parameters",
          "timestamp": "2026-09-10T20:55:43-07:00",
          "tree_id": "1f9dd3ae8551ce4efb99e660171bc89b98d9fabc",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/b46766643b3536a22f2d91e4642d5b57adfaefc9"
        },
        "date": 1789099001419,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 133.85,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 201.23,
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
          "id": "7b71292b250ef6d9ec04c8e6a781cef4d81b36f5",
          "message": "fix(cli): make --version a top-level flag only",
          "timestamp": "2026-09-10T21:11:52-07:00",
          "tree_id": "b15aa651aff323de48ff842b667fe3dfc1267348",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/7b71292b250ef6d9ec04c8e6a781cef4d81b36f5"
        },
        "date": 1789100120236,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 136.6,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 211.36,
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
          "id": "9b99820b71c2b1b1904003c8dc8f1625d49daa83",
          "message": "fix(errors): omit documentation link when docs_path is not set",
          "timestamp": "2026-09-10T21:17:42-07:00",
          "tree_id": "b7651fca4f778260dc6eb0bb35fb1f749c8e4ac9",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/9b99820b71c2b1b1904003c8dc8f1625d49daa83"
        },
        "date": 1789100422934,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 130.66,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 203.47,
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
          "id": "347b60ca1a476172af6ae41039cf1f09e205b3bd",
          "message": "feat(cli): suppress --verbose from non-init subcommand help output",
          "timestamp": "2026-09-10T21:23:39-07:00",
          "tree_id": "e5a8c5f54dfbc1ce6fd8997e1570e6a31f12ac41",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/347b60ca1a476172af6ae41039cf1f09e205b3bd"
        },
        "date": 1789100984949,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 132.79,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 203.48,
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
          "id": "9725a193b14f5b0534e2642d8bc1a2e7943cdf4d",
          "message": "feat(cli): add debug logging to config and completion subcommands",
          "timestamp": "2026-09-10T21:31:47-07:00",
          "tree_id": "4995aa5e334606d99a54d9dab6cf5a27d31de0d7",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/9725a193b14f5b0534e2642d8bc1a2e7943cdf4d"
        },
        "date": 1789101249430,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 131.19,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 202.43,
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
          "id": "86fd0174f759723cdbd0218cdf42a6526ee73c71",
          "message": "feat(cli): replace --force-replace with -f/--force on config subcommand",
          "timestamp": "2026-09-10T21:37:57-07:00",
          "tree_id": "408e67a2f46c433c67988b9c972fb8b19189ddcc",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/86fd0174f759723cdbd0218cdf42a6526ee73c71"
        },
        "date": 1789101618501,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 142.99,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 231.14,
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
          "id": "00df1acb96a07e11c05e2071d6bbe5cb8e31ebd3",
          "message": "docs: unify portable configuration terminology to templates",
          "timestamp": "2026-09-10T21:43:53-07:00",
          "tree_id": "da791dc21f848ddb58be36e098f07561020c54d3",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/00df1acb96a07e11c05e2071d6bbe5cb8e31ebd3"
        },
        "date": 1789102000473,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 133.46,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 212.49,
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
          "id": "9154354e227712de1ccc198d40b7c65e84d988c9",
          "message": "feat(cli): unify help formatting with Rich tables across all commands\n\n- Add print_help() to JsonAwareParser delegating to print_table_help,\n  eliminating the need for per-parser monkey-patches\n- Support argparse._SubParsersAction in print_table_help by unpacking\n  _choices_actions to render each subcommand name/description as a row\n- Normalize group titles (options, positional arguments, subcommands)\n  to Title Case\n- Guard table rendering with row_count > 0 to avoid empty boxes\n  for commands without options (e.g. export-schema)\n- Use file-aware console so print_help(file=...) routes to the right\n  output stream\n- Add usage=argparse.SUPPRESS and metavar='<command>' to help_parser\n  for consistent display with other subcommands\n- Update generate_doc_fixtures.py is_custom_table check to recognise\n  JsonAwareParser instances directly\n- Regenerate cli_help.svg and cli_config_help.svg fixtures and update\n  expected shrinkwrapped widths in test_doc_fixtures.py",
          "timestamp": "2026-09-10T21:55:17-07:00",
          "tree_id": "58e3672dd869c6f1d04509efe6134e07d5b3d516",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/9154354e227712de1ccc198d40b7c65e84d988c9"
        },
        "date": 1789102791818,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 134.07,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 205.65,
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
          "id": "1524d74202f41a0d26b26e3cd4ffbe5870b4e142",
          "message": "refactor(cli): delete ProtoHelpFormatter and remove all formatter_class noise\n\nAll parsers are JsonAwareParser subclasses whose print_help() centralises\nrendering through print_table_help(). ProtoHelpFormatter was never invoked\non the human-readable code path after that change and carried dead styles,\na dead add_usage override, and dead SVG-generator fallback branches.\n\n- Delete ProtoHelpFormatter entirely\n- Remove formatter_class=ProtoHelpFormatter from root parser and all six\n  subparser add_parser() calls\n- Replace _VersionAction formatter dance with a direct ui.console.print()\n- Collapse generate_cli_help_svgs() is_custom_table branch: always routes\n  through JsonAwareParser.print_help() / print_table_help()\n- Drop now-dead ProtoHelpFormatter.console save/restore in finally block\n- Replace test_proto_help_formatter_usage with\n  test_json_aware_parser_print_help_uses_table_renderer\n- Drop ClassVar, Iterable, Style, RawTextRichHelpFormatter imports",
          "timestamp": "2026-09-10T22:04:48-07:00",
          "tree_id": "f181c714f1f098d67ff03c49d9ef729c8a62c606",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1524d74202f41a0d26b26e3cd4ffbe5870b4e142"
        },
        "date": 1789103176605,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 140.64,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 228.7,
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
          "id": "a09086a2e7d2962813d239f678411cb8e2051983",
          "message": "docs: streamline and simplify documentation mermaid diagrams for legibility",
          "timestamp": "2026-09-10T23:22:10-07:00",
          "tree_id": "87dc841e3e90c63f22ce8d339707ca76fad29705",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a09086a2e7d2962813d239f678411cb8e2051983"
        },
        "date": 1789107854434,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 142.21,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 227.24,
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
          "id": "ecafd446cb1d9de734f3bdd7d7031d9fa75284a4",
          "message": "docs: simplify documentation terminology and remove misleading jargon",
          "timestamp": "2026-09-10T23:29:44-07:00",
          "tree_id": "25493a29bc32c13448668e1cd6abfe3c96aeb074",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/ecafd446cb1d9de734f3bdd7d7031d9fa75284a4"
        },
        "date": 1789108267528,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 131.28,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 204.66,
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
          "id": "88a13007d333c28a9cf0c2cea88a674e9dab219d",
          "message": "fix(tooling): protect dependency groups during AST overwrite and declare docs group in wiring",
          "timestamp": "2026-09-10T23:42:11-07:00",
          "tree_id": "602517241e33355982f90a29e4cbde07c3a9fc3f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/88a13007d333c28a9cf0c2cea88a674e9dab219d"
        },
        "date": 1789109022696,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 109.16,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 178.07,
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
          "id": "69ceb7735cfc1670e436637984e113178a2a2cc7",
          "message": "fix(executor): sanitize subprocess environment and guard post-install tasks (#232)",
          "timestamp": "2026-09-11T11:16:10-07:00",
          "tree_id": "8737a59c42bfc9654cf6b652e25fc10efbd49c2c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/69ceb7735cfc1670e436637984e113178a2a2cc7"
        },
        "date": 1789150631306,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 138.93,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 226.25,
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
          "id": "68312d767c8f4944c299b0e900046e44c8905690",
          "message": "fix: pass minimum_python from wizard to PythonCore and omit single-target CI matrix",
          "timestamp": "2026-09-11T11:20:51-07:00",
          "tree_id": "c4e9ccd9eba2935d798c842880cb7193d6c8c79e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/68312d767c8f4944c299b0e900046e44c8905690"
        },
        "date": 1789151199693,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 110.83,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 179.43,
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
          "id": "27fded9ac478ddecee9443cf1ca0929239347d24",
          "message": "feat(tooling): model HookRunner and enforce mutual exclusivity for git hook managers (#233)\n\n- Replace dual booleans (wants_pre_commit, wants_prek) on ToolingManifest\n  with HookRunner enum\n- Add wants_hooks property and set_hook_runner() to guard against\n  conflicting runner registrations\n- Enforce mutual exclusivity in Orchestrator.plan() and\n  UserConfig.__post_init__()\n- Add interactive conflict resolution prompt in wizard component selection\n- Update pre-commit config generation and execution logic to consume HookRunner\n- Update API reference docs and regenerate doc snapshot fixtures\n- Add and update comprehensive unit tests across manifest, orchestrator,\n  config, executor, modules, and wizard",
          "timestamp": "2026-09-11T11:35:10-07:00",
          "tree_id": "fee037a71d715e1e5f340db2ddf1f940516d4d9d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/27fded9ac478ddecee9443cf1ca0929239347d24"
        },
        "date": 1789151770123,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 129.79,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 201.08,
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
          "id": "9c13a3e7bc9f2509fc8c8b9cf362d6b35eb2d310",
          "message": "chore(workflows): remove unused yellow ANSI color from generated justfiles",
          "timestamp": "2026-09-11T11:46:40-07:00",
          "tree_id": "0e10c61b2248e877ed2f785af99e32127738a684",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/9c13a3e7bc9f2509fc8c8b9cf362d6b35eb2d310"
        },
        "date": 1789152585036,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 139.88,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 216.73,
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
          "id": "898e45f6ed24a8da5d8266c348dbe8f55f24732f",
          "message": "feat(scaffolding): pair container artifacts and guard license drift (#234)\n\n- Bundle container artifacts (.dockerignore and Dockerfile) in\n  SystemExecutor._write_docker_artifacts() so skipping Dockerfile under\n  MERGE also preserves .dockerignore without mutation.\n- Add Docker collision markers (Dockerfile and .dockerignore) to\n  Orchestrator.plan() Phase 2 collision check when req.docker is enabled.\n- Add Path(\"LICENSE\") to PythonCore.collision_markers.\n- Guard license injection and trove classifier drift in PythonCore.build()\n  when LICENSE already exists on disk and is preserved under MERGE.\n- Update doc fixture generation to isolate planned payload workspace and\n  refresh ml_merged snapshot.\n- Add comprehensive test coverage for container pairing, docker collision\n  detection, and license preservation.",
          "timestamp": "2026-09-11T12:03:59-07:00",
          "tree_id": "0695e52e8f44832d31a6eea453b48b600f0b8425",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/898e45f6ed24a8da5d8266c348dbe8f55f24732f"
        },
        "date": 1789153501374,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 150.08,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 232.58,
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
          "id": "b6285be40fc3ecf310d9e34ad7a73e41ad1c9373",
          "message": "fix(executor): enforce collision strategy and error wrapping for CI and release workflows (#235)",
          "timestamp": "2026-09-11T12:35:42-07:00",
          "tree_id": "4a6ddbc3c9c3ef8796caa5805b5444ee0835d831",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/b6285be40fc3ecf310d9e34ad7a73e41ad1c9373"
        },
        "date": 1789155404389,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 138.16,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 220.5,
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
          "id": "8c92e093ccd0c8a4ab6c05e7c3ec7d92f17e1f58",
          "message": "refactor(orchestrator): enforce cross-module contract in plan phase and guard file injections (#236)",
          "timestamp": "2026-09-11T12:43:46-07:00",
          "tree_id": "c1c1cffee77082e4c77634943b1682638b8de7e4",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/8c92e093ccd0c8a4ab6c05e7c3ec7d92f17e1f58"
        },
        "date": 1789155881413,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 132,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 201.73,
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
          "id": "ba2ae1ec7df1f3a375689e28f8d30011d3bbdd80",
          "message": "refactor(cli): simplify collision retry with dataclasses.replace and remove dead module stubs (#237)",
          "timestamp": "2026-09-11T12:50:18-07:00",
          "tree_id": "ba2b8081ffd86a56289f4aa94c3d61594aa53b7e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/ba2ae1ec7df1f3a375689e28f8d30011d3bbdd80"
        },
        "date": 1789156277278,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 138.34,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 211.45,
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
          "id": "6dd3aa0de850c0d69627231544449a8f3890c077",
          "message": "fix(test): replace mutable singleton class caches with functools.cache and explicit cache clearing (#238)",
          "timestamp": "2026-09-11T12:58:04-07:00",
          "tree_id": "1e656e6b114953674a337e8c9b858a9be710405a",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/6dd3aa0de850c0d69627231544449a8f3890c077"
        },
        "date": 1789156733553,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 105.84,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 162.62,
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
          "id": "c51c0e213403eb91064a7a097e5d5c5b3e82007e",
          "message": "fix(config): enforce type guards on template blueprint fields during parsing (#239)",
          "timestamp": "2026-09-11T13:02:11-07:00",
          "tree_id": "69d7cbdee1e387da6a6a4b2f0474d15e44e14fd4",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/c51c0e213403eb91064a7a097e5d5c5b3e82007e"
        },
        "date": 1789157070938,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 108.84,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 171.81,
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
          "id": "9909b979295eeed3e5ddbf9eef2f415eb367b520",
          "message": "refactor(modules): move git and workspace probe from build to pre_flight (#240)",
          "timestamp": "2026-09-11T13:08:48-07:00",
          "tree_id": "32ffbb70a8406aa9a772ec3188227ae604acff6c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/9909b979295eeed3e5ddbf9eef2f415eb367b520"
        },
        "date": 1789157388529,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 141.29,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 225.71,
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
          "id": "030928ee0fddfcbce68c2dfdd82714bbb8c1cb24",
          "message": "feat: implement pipeline transactionality and rollback (#241)\n\n* feat: implement transactional execution pipeline with MutationJournal and rollback\n\n* fix: remove trailing comma returning tuple in orchestrator execution\n\n* test: fix legacy tests for journal architecture\n\n* test: remove last failing legacy string matches\n\n* fix(ci): update fixtures, fix types, and adapt tests to journal execution\n\n* test(integration): dynamically resolve python version for direnv and isolation tests\n\n* fix: correct transaction rollback semantics",
          "timestamp": "2026-09-11T17:54:48-07:00",
          "tree_id": "76cedaa02867fd9f5506af9c2d4774a036dcaaaf",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/030928ee0fddfcbce68c2dfdd82714bbb8c1cb24"
        },
        "date": 1789174543205,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 110.24,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 175.14,
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
          "id": "35c28fa6bda2d4658b39088c6033d9b47a0fa086",
          "message": "docs: document pipeline transactionality, mutation journal, and rollback architecture (#242)\n\nAlign repository documentation, guides, error references, and fixtures with the\ntransactional execution model introduced in PR #241:\n\n- Document MutationJournal, TransactionAwareFS, and ProcessRunner in executor mechanics\n- Delineate honest rollback boundaries (what is reliably reverted vs. what may remain)\n- Document fatal dependency installation policy for uv add\n- Document new domain exceptions: RollbackFailedError, ProcessTerminationError,\n  UnsupportedFilesystemNodeError, TransactionStateError, and AggregatedDependencyError\n- Update PartialExecutionAbortedError documentation to clarify tracked change rollback\n- Add execution interruptions and rollback recovery section to troubleshooting guide\n- Wire DocsPage.TROUBLESHOOTING_ROLLBACK to rollback and unsupported node errors\n- Update check_doc_links.py sentinel reflection to validate all domain error doc links\n- Update exit code fixture table generator and synchronize doc fixtures",
          "timestamp": "2026-09-11T18:27:21-07:00",
          "tree_id": "3080a00bc2d1a2427980e402cec94a87b9ed4ccf",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/35c28fa6bda2d4658b39088c6033d9b47a0fa086"
        },
        "date": 1789176498512,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 132.24,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 203.41,
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
          "id": "350012ca1f70208411a0c8eca784dcaa39c45bbf",
          "message": "fix(orchestrator): resolve false collisions and close detection gaps (#243)\n\n- Update ZensicalModule collision_markers to target docs/index.md rather\n  than the entire docs/ directory, preventing phantom collisions in\n  workspaces with existing doc directories.\n- Make PythonCore collision_markers conditionally include LICENSE only when\n  an active license is configured, preventing collisions when selecting\n  'None'.\n- Add CHANGELOG.md to CommitizenModule collision_markers.\n- Inspect req.template_blueprint.files during Phase 2 collision checks\n  with placeholder interpolation (e.g., README.md and source scaffolding).\n- Synchronize CLI entry points (interactive wizard and main parser) to pass\n  resolved license into PythonCore.\n- Update tests and synchronize documentation fixture tables.",
          "timestamp": "2026-09-11T19:37:41-07:00",
          "tree_id": "b06463761f4677814b8eff75675da5052967bfbd",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/350012ca1f70208411a0c8eca784dcaa39c45bbf"
        },
        "date": 1789180720815,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 131.26,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 202.72,
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
          "id": "f3d35f33fbfa839993bf6a15097b05c1a1be6bda",
          "message": "refactor(orchestrator): implement manifest-first collision detection (#244)\n\n* refactor(orchestrator): implement manifest-first collision detection\n\nRefactor workspace collision detection to inspect the fully assembled\nEnvironmentManifest instead of relying on static, pre-manifest guesswork\nvia module collision_markers. This aligns the engine with Architectural\n\nInvariant #1 (Manifest-First, Side-Effects-Last).\n\nKey changes:\n- Add wants_docker to ToolingManifest and target_files() query to\n  EnvironmentManifest to compute all files intended to be written.\n- Reorder Orchestrator.plan() lifecycle: run pre-flight, instantiate and\n  populate manifest (module builds + blueprint injections), and evaluate\n  collisions against manifest.target_files().\n- Eliminate collision_markers property cleanly from BootstrapModule and\n  all module subclasses across lang_layer, tooling_layer, and ci_layer.\n- Purge premature should_skip_file checks from module build() methods so\n  modules remain 100% pure and declarative.\n- Dynamically derive scaffolded files in generate_doc_fixtures.py and\n  update tooling table fixtures and documentation.\n- Update module and orchestrator unit tests to verify manifest-first\n  declarative execution.\n\n* docs: document manifest-first collision detection in mechanics and developer docs",
          "timestamp": "2026-09-11T20:26:04-07:00",
          "tree_id": "3d4d530ee452923a025d4b3132acf48234c17504",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f3d35f33fbfa839993bf6a15097b05c1a1be6bda"
        },
        "date": 1789183620378,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 133.09,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 205.63,
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
          "id": "c489b15d23186eb9118f01f66d833d85e7ea1e89",
          "message": "feat: extend rollback boundary to explicitly owned subprocess footprints (#245)\n\n* feat: extend rollback boundary to explicitly owned subprocess footprints\n\n* chore: update documentation fixtures for new task footprints",
          "timestamp": "2026-09-11T21:30:47-07:00",
          "tree_id": "d1da0285ba3b1d0594d1bcba7475c4d271b82c69",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/c489b15d23186eb9118f01f66d833d85e7ea1e89"
        },
        "date": 1789187496467,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 109.15,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 169.94,
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
          "id": "fce62a3070f508f6356173d60c3cacbfa0bb2856",
          "message": "docs(rollback): add dedicated user & mechanics rollback pages (#246)\n\n- Add docs/usage/rollback.md: user-facing guide covering what rollback\n  protects, what might remain, Ctrl+C behavior, RollbackFailedError\n  remediation, and UnsupportedFilesystemNodeError handling. Includes\n  a mermaid sequence diagram of the interrupt → terminate → restore flow.\n\n- Add docs/mechanics/rollback.md: developer-facing deep dive into the\n  MutationJournal / TransactionAwareFS / ProcessRunner three-layer stack.\n  Covers record-before-mutate semantics, OriginalState data model,\n  reversed-order replay, two-stage subprocess termination, shield_sigint,\n  Bytes Over Intent, empty-directory-only removal, and the fatal\n  dependency policy. Includes two mermaid diagrams (architecture and\n  full transactional flow). Moves the MutationJournal, TransactionAwareFS,\n  and ProcessRunner API reference blocks here from executor.md.\n\n- Trim docs/mechanics/executor.md: extract the 49-line rollback section\n  into an 8-line callout pointing to mechanics/rollback.md; remove the\n  now-redundant API reference blocks for MutationJournal, TransactionAwareFS,\n  ProcessRunner, and execute_subprocess; add rollback.md to related links.\n\n- Trim docs/mechanics/orchestrator.md: replace the long rollback parenthetical\n  in Phase 3 with a single sentence linking to mechanics/rollback.md.\n\n- Trim docs/usage/troubleshooting.md: replace the 30-line Execution\n  Interruptions & Rollback section with a 5-line info callout pointing to\n  usage/rollback.md; add rollback.md to related resources.\n\n- Trim docs/usage/agent-interface.md: replace 4-line inline rollback paragraph\n  with a single sentence linking to usage/rollback.md.\n\n- Update docs/design-principles.md: tighten the Transaction Boundary note\n  block and add see-also links to both new rollback pages.\n\n- Update zensical.toml: add 'Automatic Rollback' to the User Guide nav\n  (between Agent & Machine Interface and CLI Reference) and 'Rollback\n  Internals' to the Mechanics nav (between Executor and Modules).",
          "timestamp": "2026-09-12T14:37:14-07:00",
          "tree_id": "1f8db56533349dd6c446f3aa79d3d6ab88658bc5",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/fce62a3070f508f6356173d60c3cacbfa0bb2856"
        },
        "date": 1789249094189,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 133.98,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 206.17,
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
          "id": "d4183c16fcecc41008608d518685637719fbfd1e",
          "message": "feat(cli): conditionally render rich formatted rollback checklist based on template origin (#247)\n\n* feat(executor): centralize rollback messaging and clarify subprocess boundary\n\n* docs: rename rollback registry entry to reflect dedicated page\n\n* feat(journal): cache formatted display paths for rollback UI rendering\n\n* refactor(orchestrator): decouple rollback presentation from engine logic\n\nIntroduce RollbackContext to transport execution history from SystemExecutor\n\nto CLI, removing string formatting from Domain and Execution layers.\n\n* feat(cli): conditionally render rich formatted rollback checklist based on template origin\n\nDisplays explicitly tracked paths and executed task history.\n\n* test(orchestrator): fix failing test for rollback context\n\n* fix(cli): render documentation links as rich OSC 8 hyperlinks\n\nFormats rollback documentation links with bold cyan OSC 8 hyperlink\n\nmarkup so they are clickable without requiring modifier keys.",
          "timestamp": "2026-09-12T15:15:28-07:00",
          "tree_id": "ffb5a6fa8f7db032a70cc92701b445f7f73347c1",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d4183c16fcecc41008608d518685637719fbfd1e"
        },
        "date": 1789251386819,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 130.53,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 200.84,
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
          "id": "e2cb6b65ae5833d992ae685eaa69eaf234d6ca3a",
          "message": "refactor: centralize documentation linking and type safety (#248)\n\nThis commit centralizes all documentation URLs by upgrading DocsPage to a\nstandard Enum with path and label tuples. It introduces format_docs_link to\nensure all CLI doc links flow through this registry, eliminating hardcoded\nURLs in errors and the CLI. Check_doc_links.py was completely overhauled to\nstatically iterate the enum instead of relying on fragile dynamic instantiation.",
          "timestamp": "2026-09-12T16:14:56-07:00",
          "tree_id": "c7d7d7b1db6fd3471b8b513f2b439776251c35d5",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/e2cb6b65ae5833d992ae685eaa69eaf234d6ca3a"
        },
        "date": 1789254953850,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 139,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 212.96,
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
          "id": "f92789e94c3b77c95bb6c131529b45da240ab3d7",
          "message": "fix(justfile): tolerate non-zero exit from interactive sandbox shells",
          "timestamp": "2026-09-12T16:29:44-07:00",
          "tree_id": "75cbee89bdcac2cf108c115d6b86fefed50df09e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f92789e94c3b77c95bb6c131529b45da240ab3d7"
        },
        "date": 1789255847389,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 106.48,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 164.2,
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
          "id": "3e344fd89ae9fcf0e3a0916240c1937c56a2a5f9",
          "message": "refactor(errors): replace PartialExecutionAbortedError with ExecutionInterruptedError",
          "timestamp": "2026-09-12T16:35:25-07:00",
          "tree_id": "1f0c11f835109b3bb4e69d13e3bec26d01d61592",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/3e344fd89ae9fcf0e3a0916240c1937c56a2a5f9"
        },
        "date": 1789256289042,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 134.47,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 208.44,
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
          "id": "a22c19f5536d10915e20bfdfeec82b6bda5b77b0",
          "message": "docs: adopt 'Safe. Predictable. Clean.' hero messaging",
          "timestamp": "2026-09-13T11:44:42-07:00",
          "tree_id": "1bf8bdb8f5e1e9058e7fd64261302cae83ac40e4",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a22c19f5536d10915e20bfdfeec82b6bda5b77b0"
        },
        "date": 1789325185832,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 143.43,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 226.28,
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
          "id": "4cd45fb94aa8293b80bf30032f6945456f636f79",
          "message": "docs: use balance icon for 'Why Protostar?' and GitHub icon for repo",
          "timestamp": "2026-09-13T11:49:18-07:00",
          "tree_id": "73e24df13dc39d72a7660c508c0f1c9883fb0c4d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/4cd45fb94aa8293b80bf30032f6945456f636f79"
        },
        "date": 1789325538881,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 131.35,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 200.31,
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
          "id": "a48d924b0209b27dfc9ac63aa00dbe58cc5db060",
          "message": "docs(readme): replace br with sub tag for github vertical spacing",
          "timestamp": "2026-09-13T11:52:27-07:00",
          "tree_id": "31dddb6ab336ce7f9c36681c33be7779a9e0c71c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a48d924b0209b27dfc9ac63aa00dbe58cc5db060"
        },
        "date": 1789325621151,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 152.85,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 244.38,
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
          "id": "0aef9e2f9429822aefc4449574c99a6cf6758a2d",
          "message": "docs(readme): replace br with sub tag for github vertical spacing",
          "timestamp": "2026-09-13T11:53:14-07:00",
          "tree_id": "31dddb6ab336ce7f9c36681c33be7779a9e0c71c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/0aef9e2f9429822aefc4449574c99a6cf6758a2d"
        },
        "date": 1789325646084,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 115.46,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 185.74,
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
          "id": "0070b701825e563600d6228fba986b04ef637cd6",
          "message": "docs(readme): replace br with sub tag for github vertical spacing",
          "timestamp": "2026-09-13T11:53:30-07:00",
          "tree_id": "3a5a92d51b50b0059f78e0918d4e2dc8d54ee7a4",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/0070b701825e563600d6228fba986b04ef637cd6"
        },
        "date": 1789325665723,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 124.45,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 193.52,
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
          "id": "072e1df599fc0cf1560894ca0fa0536bd4ea490c",
          "message": "docs(readme): replace br with sub tag for github vertical spacing",
          "timestamp": "2026-09-13T11:54:04-07:00",
          "tree_id": "31dddb6ab336ce7f9c36681c33be7779a9e0c71c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/072e1df599fc0cf1560894ca0fa0536bd4ea490c"
        },
        "date": 1789325705197,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 138.91,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 208.75,
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
          "id": "4cd45fb94aa8293b80bf30032f6945456f636f79",
          "message": "docs: use balance icon for 'Why Protostar?' and GitHub icon for repo",
          "timestamp": "2026-09-13T11:49:18-07:00",
          "tree_id": "73e24df13dc39d72a7660c508c0f1c9883fb0c4d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/4cd45fb94aa8293b80bf30032f6945456f636f79"
        },
        "date": 1789325785242,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 132.92,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 202.78,
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
          "id": "07f333eb4feebe10f73101196ae1aa7c8841b2ef",
          "message": "docs: add bottom padding to README logo SVGs and remove br",
          "timestamp": "2026-09-13T11:58:30-07:00",
          "tree_id": "96c9978f4f243e403063e95fe2fb8f3e684dca91",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/07f333eb4feebe10f73101196ae1aa7c8841b2ef"
        },
        "date": 1789325993632,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 143.53,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 222.97,
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
          "id": "adbb710394106ab6332cf6af07da3299107bc24a",
          "message": "docs: update linter ignore rule in README and fix RTD URL\n\n- Switch markdownlint file-disable comment to rumdl first-line-heading syntax in README.md.\n- Update documentation URL in pyproject.toml to point directly to /stable/.",
          "timestamp": "2026-09-13T21:33:23-07:00",
          "tree_id": "9e53f1211f1ee4cecdb515e22cd15f9ee474d7d4",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/adbb710394106ab6332cf6af07da3299107bc24a"
        },
        "date": 1789360603052,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 137.29,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 212.89,
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
          "id": "fc6f1cdca1c12ec6026d6a6954657499b97b52f9",
          "message": "ci(release): update reusable workflow ref and justfile to ci-cd-release-infrastructure",
          "timestamp": "2026-09-13T22:46:05-07:00",
          "tree_id": "5340a72eb8823f19eff19f93e0e478a7a3bf66c1",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/fc6f1cdca1c12ec6026d6a6954657499b97b52f9"
        },
        "date": 1789364839268,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 117.14,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 178.06,
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
          "id": "b95b79f0245fa6c0eef192829c4c1e3e1b0f16c8",
          "message": "docs: add Stage 1 safe semantic reconciliation plan\n\nIntroduce `SEMANTIC_MERGE_PLAN.md` defining the architecture, state\nschema, artifact-specific policies, and phased PR rollout for safe\nsemantic reconciliation under `protostar init --force-merge`.\n\nKey decisions established:\n- Implement three-way semantic reconciliation for managed TOML/YAML\n  configurations using `.protostar.lock.toml` (schema v1) baselines.\n- Establish strict non-destructive merge rules: preserve user edits/deletions,\n  prevent implicit adoption, and emit machine-readable conflict warnings.\n- Apply checksum-gated replacement for generated files (Renovate, workflows,\n  Dockerfile, justfile) and stable-ID managed append regions.\n- Gate dependency updates via PEP 508 requirement normalization and\n  targeted `uv add` operations, avoiding redundant `uv lock` invocations.\n- Break implementation into 8 bounded, gated phases (PR-A through PR-H).",
          "timestamp": "2026-09-15T16:08:39-07:00",
          "tree_id": "dc6f8827d9c04af4db055bd7198d91cb29b5a025",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/b95b79f0245fa6c0eef192829c4c1e3e1b0f16c8"
        },
        "date": 1789513822243,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 106.48,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 165.75,
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
          "id": "e4956c45cc0e76b502806b35948af13e3df921bd",
          "message": "chore(deps): lock file maintenance (#249)\n\nCo-authored-by: renovate[bot] <29139614+renovate[bot]@users.noreply.github.com>",
          "timestamp": "2026-09-15T16:31:02-07:00",
          "tree_id": "d6e97f75e1d706d5a34ebfce1eb73f430b96872b",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/e4956c45cc0e76b502806b35948af13e3df921bd"
        },
        "date": 1789515113930,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 113.06,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 184.49,
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
          "id": "be0be979a2c131b3c2dfcdd71c396ff5063ced3c",
          "message": "feat(manifest): declare semantic merge intent and template identity (#250)",
          "timestamp": "2026-09-15T16:32:08-07:00",
          "tree_id": "43608b52356621b66a78d446b96ec6c5019d29e9",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/be0be979a2c131b3c2dfcdd71c396ff5063ced3c"
        },
        "date": 1789515188841,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 143.44,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 219.73,
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
          "id": "b385ddb0e8e0dd8b7f67a3a682c32e62e9021cd3",
          "message": "docs(plan): mark semantic merge PR A complete",
          "timestamp": "2026-09-15T23:37:27Z",
          "tree_id": "5c0580f32e6c4ae628f8496ba0c992f129bd2da3",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/b385ddb0e8e0dd8b7f67a3a682c32e62e9021cd3"
        },
        "date": 1789515812745,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 138.96,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 213.74,
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
          "id": "23869e713693dfb8cce5986d5a45718279bf3ab1",
          "message": "feat(merge): add state codec and pure reconciliation kernel (#251)\n\nTrack only applied contributions in deterministic schema-v1 state.\nPreserve user edits and deletions with typed three-way decisions and\ncomposite baselines, without wiring the executor before PR C.",
          "timestamp": "2026-09-15T16:52:58-07:00",
          "tree_id": "4be20f92f98610460455db0f93262f771a1f8894",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/23869e713693dfb8cce5986d5a45718279bf3ab1"
        },
        "date": 1789516435538,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 136.67,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 206.66,
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
          "id": "a7ce1b9accbc06bf38263f4a3a719503ba188f57",
          "message": "feat(merge): integrate transactional TOML ownership state (#252)\n\n* feat(merge): integrate transactional TOML ownership state\n\n* docs(merge): align fixtures with tracked template identity\n\n* docs(plan): mark semantic merge PR C complete\n\n* fix(deps): normalize requirement values before selection\n\n* fix(merge): preserve authored TOML presentation\n\nKeep semantic values separate from their tomlkit AST.\n\nAccepted updates now retain comments, array layout, inline tables, and generated tool markers.\n\nRestore the documentation fixtures and cover overlapping module and template contributions.\n\n* fix(fixtures): preserve merged workspace state\n\nKeep foreign ML workspace additions visible across the tracked template rerun.\n\nSnapshot reconciliation state for every scenario and keep managed tool headers in canonical order.",
          "timestamp": "2026-09-16T09:06:07-07:00",
          "tree_id": "ee5e38fdce122c73a33ac115594e8a651bc56e72",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a7ce1b9accbc06bf38263f4a3a719503ba188f57"
        },
        "date": 1789574838292,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 168.89,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 249.7,
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
          "id": "c79f0278c6a9ba70cb6362751234e690ad4ba6f1",
          "message": "fix(merge): preserve deleted projects and local TOML trivia (#253)",
          "timestamp": "2026-09-16T11:46:11-07:00",
          "tree_id": "bc2d11588c940c7e2475d7cde53908d1b33bf96f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/c79f0278c6a9ba70cb6362751234e690ad4ba6f1"
        },
        "date": 1789584424227,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 114.58,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 173.02,
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
          "id": "ab2700f05c98a05519b6400ee49d44d73fe09d69",
          "message": "refactor(testing): decouple snapshot regression testing from documentation assets (#254)\n\n* refactor(testing): add scenario modeling and inline drift detection to fixture generator\n\n* feat(testing): split fixture generator and migrate snapshots to tests/snapshots\n\n* test: exclude snapshots from pytest discovery and fix moved fixture path\n\n* ci: update snapshot and docs asset verification step in CI workflow\n\n* feat(snapshots): track generated .envrc in scenario snapshots\n\n* fix(testing): restore exit code docs, harden drift detection, and track gitkeep",
          "timestamp": "2026-09-16T15:21:47-07:00",
          "tree_id": "1e65deaab8745cc56533869b30d1558f087576b7",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/ab2700f05c98a05519b6400ee49d44d73fe09d69"
        },
        "date": 1789597377375,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 174.6,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 256.5,
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
          "id": "ab2700f05c98a05519b6400ee49d44d73fe09d69",
          "message": "refactor(testing): decouple snapshot regression testing from documentation assets (#254)\n\n* refactor(testing): add scenario modeling and inline drift detection to fixture generator\n\n* feat(testing): split fixture generator and migrate snapshots to tests/snapshots\n\n* test: exclude snapshots from pytest discovery and fix moved fixture path\n\n* ci: update snapshot and docs asset verification step in CI workflow\n\n* feat(snapshots): track generated .envrc in scenario snapshots\n\n* fix(testing): restore exit code docs, harden drift detection, and track gitkeep",
          "timestamp": "2026-09-16T15:21:47-07:00",
          "tree_id": "1e65deaab8745cc56533869b30d1558f087576b7",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/ab2700f05c98a05519b6400ee49d44d73fe09d69"
        },
        "date": 1789597526354,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 159.96,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 230.95,
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
          "id": "8dc20d1d324a4fa1b17aa4420ad7411173a388b2",
          "message": "test(snapshots): harden regression testing with input pinning and repeatability suites (#255)\n\n* test(snapshots): harden regression testing with input pinning and repeatability suites\n\n* fix(snapshots): isolate repeatability network calls and fix missing target drift",
          "timestamp": "2026-09-16T16:33:53-07:00",
          "tree_id": "522231912d7ec09587485e5cbc7b7d8af6a8e22e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/8dc20d1d324a4fa1b17aa4420ad7411173a388b2"
        },
        "date": 1789601697338,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 164.74,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 237.04,
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
          "id": "6deeab6765d4ed25ef7abf3e4de56588c3cb0017",
          "message": "feat(merge): reconcile Codecov YAML with owned baselines (#256)\n\n* feat(merge): reconcile Codecov YAML with owned baselines\n\n* test(yaml): assign explicit IDs to bounded input parameter sets",
          "timestamp": "2026-09-16T17:52:04-07:00",
          "tree_id": "d5aa2602c41377abb219acea1a99d45608853184",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/6deeab6765d4ed25ef7abf3e4de56588c3cb0017"
        },
        "date": 1789606392184,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 167.54,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 238.43,
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
          "id": "0f0279b5b757ca378696cdf197f18be7435d169b",
          "message": "fix(ci): enforce Windows test step gating and fix platform test failures (#257)",
          "timestamp": "2026-09-16T18:01:39-07:00",
          "tree_id": "9eef0e33f4258908515248e4515c3c7a0ff559ec",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/0f0279b5b757ca378696cdf197f18be7435d169b"
        },
        "date": 1789606970998,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 183.32,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 259.97,
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
          "id": "72f89764e77615a40336e306fbce0241ca5daece",
          "message": "ci(workflows): add 6-minute job timeouts and automatic retry for hung jobs",
          "timestamp": "2026-09-16T18:10:59-07:00",
          "tree_id": "a171d017d95bd60a23a761a4dd8550d9caf65f73",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/72f89764e77615a40336e306fbce0241ca5daece"
        },
        "date": 1789607550485,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 168.85,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 242.66,
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
          "id": "0cd2a7b10002bf4453708a34c3615776da06a734",
          "message": "feat(hooks): reconcile pre-commit configuration by identity (#258)\n\n* feat(hooks): reconcile pre-commit configuration by identity\n\n* docs(hooks): record PR E contracts and ownership snapshots",
          "timestamp": "2026-09-16T18:27:53-07:00",
          "tree_id": "a8ecce1e036ed0e19032350338b0d1d85cde471e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/0cd2a7b10002bf4453708a34c3615776da06a734"
        },
        "date": 1789608542938,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 173.25,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 246.21,
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
          "id": "05397de6521f52054bbb910a4956dc63d44d1245",
          "message": "feat(reconciliation): gate generated files and managed regions (#259)",
          "timestamp": "2026-09-17T10:19:06-07:00",
          "tree_id": "bf244b938547f193de842d661d51a004b99361e8",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/05397de6521f52054bbb910a4956dc63d44d1245"
        },
        "date": 1789665620073,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 185.94,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 261.65,
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
          "id": "cb12031e75214ecc81194b032f1e9ce178a57d1a",
          "message": "perf(cli): defer heavy ast and engine imports to resolve cold-start latency (#260)\n\n* perf(cli): defer heavy ast and engine imports to resolve cold-start latency\n\n* fix(sync_state): explicitly re-export PinProvenance for mypy strict compliance",
          "timestamp": "2026-09-17T11:03:42-07:00",
          "tree_id": "56a33cb9b37bac5e7678cd7d2b3ef3277cb2b277",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/cb12031e75214ecc81194b032f1e9ce178a57d1a"
        },
        "date": 1789668273111,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 102.49,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 165.63,
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
          "id": "25c6a18422b4b252cb03990794308d11d5c79f15",
          "message": "ci(hooks): run mypy across full repository on pre-commit",
          "timestamp": "2026-09-17T11:07:23-07:00",
          "tree_id": "e9b3b10d17e404356d55cd745a3fdabf1b9fea58",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/25c6a18422b4b252cb03990794308d11d5c79f15"
        },
        "date": 1789668542167,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 144.06,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 221.66,
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
          "id": "156d6d672a54b6ce24dea2302ef4f42caec47c24",
          "message": "ci(hooks): exclude docs, site, and snapshots from python hooks",
          "timestamp": "2026-09-17T11:13:10-07:00",
          "tree_id": "de9fbaa03e1357cdb8500e9d46586560820b84b0",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/156d6d672a54b6ce24dea2302ef4f42caec47c24"
        },
        "date": 1789668880410,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 131.44,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 204.74,
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
          "id": "cacfc1df5b1a70c2775e7ee69f0f994cdb60c95e",
          "message": "ci(hooks): run full-repo mypy and align snapshot exclusions across tools",
          "timestamp": "2026-09-17T11:25:50-07:00",
          "tree_id": "57bec947675c0d81ab10a71e424e8fb02d65a2c6",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/cacfc1df5b1a70c2775e7ee69f0f994cdb60c95e"
        },
        "date": 1789669663044,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 98.59,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 162.74,
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
          "id": "6aece03b91888a47d1a0b305cedd0739bacb2568",
          "message": "feat(resolver): complete semantic merge resolution ordering (#261)",
          "timestamp": "2026-09-17T11:41:28-07:00",
          "tree_id": "20f9570a994d5cd4e47cf2e6848ee57a1bd8f4cc",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/6aece03b91888a47d1a0b305cedd0739bacb2568"
        },
        "date": 1789670550070,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 139.19,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 229.93,
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
          "id": "6927ef4cae2ebe45b0d835bf50e8f0e5778dcbf3",
          "message": "test(reconciliation): complete stage one acceptance (#262)\n\nDocument safe reinitialization boundaries and verify generated artifact\n\nownership across built-in templates.",
          "timestamp": "2026-09-17T11:57:56-07:00",
          "tree_id": "2a3176642150bcb2311e9da196fc58e27ceea163",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/6927ef4cae2ebe45b0d835bf50e8f0e5778dcbf3"
        },
        "date": 1789671534185,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 107.47,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 169.85,
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
          "id": "11d9517f09764a083b8d893ccf6c0816c1018a39",
          "message": "docs: retire stage 1 semantic merge plan",
          "timestamp": "2026-09-17T12:22:09-07:00",
          "tree_id": "386f9dfcbcf6dbca47cfeeab8b8200b06314cc0b",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/11d9517f09764a083b8d893ccf6c0816c1018a39"
        },
        "date": 1789673010254,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 120.38,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 187.13,
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
          "id": "a5b4e0af0704425fc79b59f8eb2e708df2ee9b71",
          "message": "docs: establish stage 2 developer lifecycle plan",
          "timestamp": "2026-09-17T13:10:06-07:00",
          "tree_id": "29768797b94c561341be1a2fad40897eabf150d0",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a5b4e0af0704425fc79b59f8eb2e708df2ee9b71"
        },
        "date": 1789675970821,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 125.95,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 196.74,
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
          "id": "24cc4d2d1b2c266894303095db5f92b752756e98",
          "message": "feat(recipe): persist project intent in pyproject (#263)\n\n* feat(recipe): persist project intent in pyproject\n\n* fix(manifest): defer annotation evaluation with future annotations\n\n* fix(recipe): permit Windows absolute paths for local template locators\n\n* test(recipe): skip posix file mode checks on windows",
          "timestamp": "2026-09-17T13:51:35-07:00",
          "tree_id": "93a5d7f47a4bd3b05461355421f6ec1f8837d289",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/24cc4d2d1b2c266894303095db5f92b752756e98"
        },
        "date": 1789678358415,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 155.04,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 242.3,
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
          "id": "d2ca54773fa2bdbf88465f14348c5343b2fc1c3e",
          "message": "refactor(reconcile): share read-only preparation with execution (#264)\n\n* refactor(reconcile): share read-only preparation with execution\n\n* test(preparation): fix windows compatibility in preparation suite",
          "timestamp": "2026-09-17T14:35:47-07:00",
          "tree_id": "475ffa630bc0e4d35524fa4e426956bcc121811f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d2ca54773fa2bdbf88465f14348c5343b2fc1c3e"
        },
        "date": 1789681010561,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 148.57,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 223.94,
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
          "id": "5234b5be907412285f71e81076e6e6993e00a17d",
          "message": "feat(cli): add project status and diff reviews (#265)\n\n* feat(cli): add project status and diff reviews\n\n* test(lifecycle): normalize template locator path in identity change test",
          "timestamp": "2026-09-17T15:48:33-07:00",
          "tree_id": "c1cb36333c04e07ff3cdb2afda6fe43c20c4ecf9",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/5234b5be907412285f71e81076e6e6993e00a17d"
        },
        "date": 1789685376061,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 148.35,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 211.51,
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
          "id": "6d0f10ea2b687e3c34e743d033c7ed90c4f712a4",
          "message": "feat(cli): apply safe lifecycle updates with sync (#266)\n\n* feat(cli): apply safe lifecycle updates with sync\n\n* test(lifecycle): invalidate stale review via content for windows compatibility",
          "timestamp": "2026-09-17T16:10:23-07:00",
          "tree_id": "548060693d618204d0ed8d2d47b4c70c8c4a627e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/6d0f10ea2b687e3c34e743d033c7ed90c4f712a4"
        },
        "date": 1789686698799,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 196.51,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 275.2,
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
          "id": "86cec9be28d2f5cd29fff874c2f7361fa24ef3cf",
          "message": "test(lifecycle): verify stage 2 acceptance and publish workflows (#267)\n\n* test(lifecycle): verify stage 2 acceptance and publish workflows\n\n* test(lifecycle): preserve exact bytes for region drift test on windows",
          "timestamp": "2026-09-17T16:30:26-07:00",
          "tree_id": "0f2d1d54af063ab21d2461bd3b850ae2d6b27ff0",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/86cec9be28d2f5cd29fff874c2f7361fa24ef3cf"
        },
        "date": 1789687940005,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 202.46,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 285.06,
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
          "id": "70367055b9e93f8251ec21757db2ace93c68b84a",
          "message": "docs: remove completed Stage 2 execution plan\n\nStage 2 (developer-facing lifecycle commands: status, diff, sync) has\nshipped, passing all acceptance criteria across PRs 1 through 5. Remove\nSTAGE_2_PLAN.md now that its requirements, boundaries, and test matrices\nare codified in tree.",
          "timestamp": "2026-09-18T12:19:54-07:00",
          "tree_id": "60953182970b1bb0d7fa11a812a961db1fb01362",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/70367055b9e93f8251ec21757db2ace93c68b84a"
        },
        "date": 1789759292812,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 193.71,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 267.94,
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
          "id": "404fe166ba37630fd0a6b8fe678592df8fdbc02f",
          "message": "ci: scope pre-push hooks to relevant changed files",
          "timestamp": "2026-09-18T12:34:38-07:00",
          "tree_id": "6c9bf6c7b4b7ff36e1e9605f4a1e6ac109a2197e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/404fe166ba37630fd0a6b8fe678592df8fdbc02f"
        },
        "date": 1789760163108,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 189.54,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 263.26,
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
          "id": "52635020308e27ff57e4b49752b878b56ab81059",
          "message": "feat(reconcile): manage Renovate and VS Code settings via lossless JSONC ownership (#268)\n\n* refactor(merge): share declared-leaf overlay and baseline pruning\n\nThe TOML and YAML adapters each carried an identical nested overlay for\nexplicit overwrite, and the YAML adapter carried the only baseline pruning\nhelper. Move both into the merge kernel module so the upcoming JSONC adapter\ndoes not become a third copy. Behavior is unchanged.\n\n* feat(jsonc): add lossless JSONC codec and byte-splice editor\n\nAdd a stdlib-only JSONC parser that records source spans, so edits are\ncomputed as replacements over those spans and every byte outside an accepted\nedit is preserved. The editor sets, appends, and deletes members and elements\nwhile inferring indentation, separators, line endings, and comma style from\nthe surrounding document, and diffs replaced arrays by position so unchanged\nelements keep their comments.\n\nThe codec accepts comments and trailing commas, rejects duplicate keys,\nnon-finite numbers, and unsupported structures, and enforces the same size,\ndepth, and node limits as the YAML codec. A strict mode backs deterministic\nowned-baseline snapshots.\n\n* feat(jsonc): reconcile owned JSONC values against local documents\n\nAdd reconcile_jsonc, which runs the shared three-way kernel over decoded\nvalues and splices only accepted changes into the local text. New files take\nthe desired bytes verbatim so template comments and layout survive, existing\nequal content is never adopted, and a semantic no-op returns the original\nbytes. Explicit overwrite owns declared leaves and retains foreign siblings,\nmatching the TOML and YAML adapters.\n\n* feat(reconcile): manage Renovate and VS Code settings via JSONC ownership\n\nRoute .github/renovate.json and .vscode/settings.json through the JSONC\nadapter and a new structured-jsonc ownership policy instead of a checksum\ngate and a blind json.dumps merge. Comments, ordering, and user edits\nsurvive, clean template updates apply to untouched keys, and conflicts are\nreported per key. A malformed Renovate document now fails before any\nmutation, while a malformed settings file is skipped with a warning.\n\nDeclarations keep arriving through the file-injection channel so template\n[files] entries for Renovate continue to work; only the reconciliation\nbehind the special-cased path changed. The YAML-only Codecov helper becomes\na shared document reconciler, and ide.write_ide_settings is deleted.\n\n* docs(jsonc): document the JSONC boundary and regenerate snapshots\n\nRecord the codec, editor, and adapter contracts in the reconciliation\ndevelopment guide and retire the deferred Renovate/JSONC note. Regenerated\nsnapshots show only the Renovate lock record changing from a checksum digest\nto a structured-jsonc baseline, and the agent payload examples now report the\nconflict at key level.",
          "timestamp": "2026-09-18T13:35:43-07:00",
          "tree_id": "a9eeb347984f3d2fa1e156427548eb16dc8a6ff2",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/52635020308e27ff57e4b49752b878b56ab81059"
        },
        "date": 1789763818383,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 195.72,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 272.65,
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
          "id": "7187eade53befe6f8c517efba59ef0631f253d9a",
          "message": "feat(reconciliation): introduce subtle region delimiters and lockfile metadata (#269)",
          "timestamp": "2026-09-18T14:57:31-07:00",
          "tree_id": "408ab0cab5ff5b401684f00d7e740c15317a775a",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/7187eade53befe6f8c517efba59ef0631f253d9a"
        },
        "date": 1789768728488,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 195.15,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 272.43,
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
          "id": "420639a6ca5082b99537b55e4f3e2155ecd0b617",
          "message": "feat(ci): add schema validation and local actionlint gating (#270)",
          "timestamp": "2026-09-18T17:44:51-07:00",
          "tree_id": "0eafd7b4727151e0e5e8981b20a2fa44d81a73d9",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/420639a6ca5082b99537b55e4f3e2155ecd0b617"
        },
        "date": 1789778773974,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 215.07,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 307.12,
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
          "id": "3880048b82ebd2d60e3be97c96b28e0d1b0608c7",
          "message": "fix(schema): support docker in template schema and use RFC-valid email placeholder",
          "timestamp": "2026-09-18T17:50:42-07:00",
          "tree_id": "334f4a807daaed70416cabdef786606428f01c4f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/3880048b82ebd2d60e3be97c96b28e0d1b0608c7"
        },
        "date": 1789779201562,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 160.98,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 233.34,
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
          "id": "f460e55ddd692143b0873282d77bbfd93871c01b",
          "message": "refactor(scripts): harden developer tooling, paths, and presentation boundaries (#271)\n\n* chore(scripts): guard check_schemas with uv sync and direct binary execution\n\n* fix(scripts): resolve working directory coupling to repo root in generate_docs_assets\n\n* fix(scripts): resolve working directory coupling in snapshot test runner\n\n* fix(scripts): prune empty directories during snapshot target extraction\n\n* refactor(scripts): make Hyperfine command parsing robust against flag order\n\n* fix(scripts): ensure trailing newline in benchmark JSON output\n\n* fix(scripts): eliminate 64 KiB buffer cap when fetching registry\n\n* fix(scripts): use atomic file writes in registry sync\n\n* refactor(cli): promote _print_dry_run_summary to public UI function",
          "timestamp": "2026-09-18T20:55:30-07:00",
          "tree_id": "183eead4288867d2c5256634feda021d9f772a77",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f460e55ddd692143b0873282d77bbfd93871c01b"
        },
        "date": 1789790201382,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 188.15,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 260.17,
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
          "id": "f198d794deeb712dd5f2a608877acf79efa4969e",
          "message": "refactor(scripts): centralize repository paths and fix CWD assumptions (#272)",
          "timestamp": "2026-09-18T22:31:29-07:00",
          "tree_id": "f7729eebad8722f776ef8a296c65db15429d172d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f198d794deeb712dd5f2a608877acf79efa4969e"
        },
        "date": 1789795962841,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 192.42,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 267.95,
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
          "id": "a97edb5179c466b9fecd02dc24aa12ec079e49fd",
          "message": "fix(scripts): eliminate clear command leak in initial demo frame",
          "timestamp": "2026-09-19T11:14:53-07:00",
          "tree_id": "5f01d309fb445fdbc5aca4ef1337c9e4a38f81a7",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a97edb5179c466b9fecd02dc24aa12ec079e49fd"
        },
        "date": 1789841977942,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 189.17,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 264.05,
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
          "id": "f180beae66b63605e2729a77e7a80f70fb3b739c",
          "message": "feat(scripts): add dynamic demo pacing, multi-trial selection, and unified demo recipes (#273)\n\n* feat(scripts): implement dynamic completion detection for demo recording\n\n* feat(scripts): add multi-trial demo selection and structured trial summary\n\n* feat(just): unify demo recipes under demo- prefix with multi-trial support\n\n* chore(docs): regenerate demo assets with shortest-trial runner",
          "timestamp": "2026-09-19T12:15:36-07:00",
          "tree_id": "55e65bd987e0ff7323af7b7693cb1fa8d75a3ec2",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f180beae66b63605e2729a77e7a80f70fb3b739c"
        },
        "date": 1789845414205,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 196.81,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 276.6,
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
          "id": "e980f1b4850e7c4108bd1c51cf53365c1b39960e",
          "message": "refactor(templates): express cli strictness as a delta over module baselines (#274)\n\n* fix(templates): disable rumdl in the ml workbench template\n\nWorkbench templates (astro, dsp, embedded) are lightweight and leave\nmarkdown linting off; ml was the lone exception. Regenerates the ml and\nml_merged snapshots without rumdl config, dependency, justfile lines, or\ncache ignores.\n\n* refactor(templates): express cli strictness as a delta over module baselines\n\nModules ship a sensible baseline for casual projects; templates state only\nthe delta that defines their shape. cli.toml now uses extend-select for the\nextra ruff rules and drops the mypy keys the module already sets, leaving\nstrict = true plus the tests override. Effective ruff settings for the cli\nsnapshot are identical.\n\nAlso declares every quality flag explicitly in dsp and embedded, and\ncorrects the Mypy/Ruff module docstrings, which described strict\nenforcement that the code does not apply.",
          "timestamp": "2026-09-19T12:59:19-07:00",
          "tree_id": "f88c0d785c5896ff33953248afa0813b7cce645b",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/e980f1b4850e7c4108bd1c51cf53365c1b39960e"
        },
        "date": 1789848019418,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 147.5,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 203.42,
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
          "id": "5cb056c17670bd12e57bd74c84df8c1abee36dea",
          "message": "test(templates): enforce the built-in template contract, and fix what it found (#275)\n\n* fix(docker): start uvicorn from the project package instead of core.main\n\nThe generated Dockerfile ran uvicorn against core.main:app, a module that\ndoes not exist in the api scaffold, so the container failed with\nModuleNotFoundError on start. Use <package>.main:app, the src-layout\nconvention the api template scaffolds; the project is installed by uv sync\nso the package is importable in the image.\n\n* fix(templates): make cli and api installable packages and stop shipping unrunnable pytest\n\nFresh scaffolds failed their own quality gates:\n\n- cli and api had a src layout but no build system, so tests could not\n  import the package and the cli console script was inert. Both now declare a\n  hatchling build backend (no version bound, unlike uv_build). api also ships\n  the README that the seeded pyproject already references, and a /health test\n  using the httpx and pytest-asyncio dev dependencies it already declared.\n- cli hard-wrapped the project name into a long f-string, so\n  ruff format --check failed for names over about 16 characters. The name now\n  lives in an APP_NAME constant.\n- dsp and ml enabled pytest but scaffold no code or tests, so pytest exited 5.\n  pytest is now off there.\n\nRegenerates snapshots and generated docs.\n\n* test(templates): enforce the built-in template contract\n\nAdds tests/test_builtin_template_contract.py, parametrized over discovered\n\nbuilt-ins: every quality flag declared explicitly, only real tooling flags,\nno version pins, tasks within a trusted allowlist, and pyproject payloads that\nstate only the delta from module baselines (no verbatim repeats, no redefined\nbaseline lists where an additive key exists). A synthetic suite proves the\ndelta check can fail; run against the pre-#274 cli.toml it flags every\nproblem that PR fixed.\n\nModule tests now parse Ruff and Mypy payloads and pin their casual\nbaselines. The exhaustive suite derives its template list from discovery,\nholds each fresh scaffold to the gates its flags enable (with an exact-match\nknown-gaps set, currently empty), and checks the api Dockerfile target\nimports inside the scaffold.",
          "timestamp": "2026-09-19T13:43:34-07:00",
          "tree_id": "7ae0c3eb5a7c0a5d957d5b327237c9131e9e0b7f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/5cb056c17670bd12e57bd74c84df8c1abee36dea"
        },
        "date": 1789850685641,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 193.97,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 267.41,
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
          "id": "00611a2e512a51637cf9cfaabc4069294a6a1b4f",
          "message": "fix(init): honor a template's docker opinion (#276)\n\nA template's docker = true had no effect: handle_init took docker only from\n--docker or a previously captured recipe, so protostar init -t api wrote no\nDockerfile despite api.toml opting in. The recipe layer already accepted\ndocker as a template opinion key; nothing read it.\n\nDocker now resolves like tooling flags: an explicit --docker/--no-docker,\nthen the project's captured recipe, then the template opinion, then off.\nInitialized projects keep their captured choice when a template changes.\nThe wizard pre-checks Docker and labels it as enforced by the template.\n\nRegenerates the api snapshot, which now includes its Dockerfile and\n.dockerignore, and documents the behavior. The end-to-end Dockerfile test now\nrelies on the template alone instead of passing --docker.",
          "timestamp": "2026-09-19T14:01:36-07:00",
          "tree_id": "215c4e823c5e77e38d0c99e04ebd7699c3b0f7ed",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/00611a2e512a51637cf9cfaabc4069294a6a1b4f"
        },
        "date": 1789851761054,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 157.04,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 226.89,
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
          "id": "b1eb920afd89834f55e9f82d39bfc4666931355b",
          "message": "fix(templates): stop scaffolding an empty tests/host_mocks in embedded\n\nThe embedded workbench template has pytest off, yet it created an empty\ntests/host_mocks directory and the docs advertised it as a host mock testing\nharness. The directory held nothing and implied a testing story the template\ndoes not deliver, so drop it and the docs bullet that promised it.",
          "timestamp": "2026-09-19T14:11:56-07:00",
          "tree_id": "fa55207ca038835eb674bc7bacbe1ba839862c1f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/b1eb920afd89834f55e9f82d39bfc4666931355b"
        },
        "date": 1789852457657,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 194.73,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 266.37,
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
          "id": "ffd46d8f731f649953005c5406c38f95a522bb47",
          "message": "docs: document the built-in template philosophy (#277)\n\nAdds docs/developer/built-in-templates.md, the contract every built-in\ntemplate shares: what deserves to ship as one (a project shape, not a stack),\nthe admission criteria, the product and workbench tiers, the rule that modules\nship a casual baseline while templates state only the delta, the conventions\nchecklist, and a map from each rule to the test that enforces it.\n\nWires it through the rest of the docs:\n\n- CONTRIBUTING.md: replace section 6, which described a PresetModule class\n  that no longer exists, and point template and module-default changes at the\n  new page.\n- design-principles.md: new 'Baseline in Modules, Shape in Templates' section.\n- modules.md: note that module config is a casual baseline, and fix an example\n  that set strict = true in a mypy module.\n- init.md, tooling-matrix.md, authoring-templates.md: drop 'Opinionated\n  Templates' and 'high-level macros' wording, and add a State Only the Delta\n  tip for template authors.\n- README.md and zensical.toml: pointer and nav entry.\n- Generated template table gains a Description column; each built-in carries\n  a header naming its tier and pointing at the contract; discovery.py links to\n  the page.\n\nBuilt-in template digests change because of the header comments.",
          "timestamp": "2026-09-19T14:48:02-07:00",
          "tree_id": "805e54cbb67697fb89ebea79fc4fbe8d7e4d7f06",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/ffd46d8f731f649953005c5406c38f95a522bb47"
        },
        "date": 1789854537862,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 136.2,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 188.11,
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
          "id": "3edbeef5746065be0180d31db05c5da2ae54d00a",
          "message": "feat(config): make template tool configuration and packages follow the tool flags (#278)\n\n* feat(config): inject template pyproject payloads only while their tool is enabled\n\nTemplate [dev.pyproject] payloads were injected whether or not the tool they\nconfigure was enabled, so 'protostar init -t cli --no-mypy' still wrote\n[tool.mypy] and '--no-pytest' still wrote [tool.coverage].\n\nAn entry is now either a TOML string, which is always injected, or a table\nwith content and an optional requires naming a tool, which is injected only\nwhile that tool is active. The orchestrator decides from the modules actually\nbeing applied, so recipe opt-outs and CLI flags are honored the same way, and\nattributes a tool-bound payload to its tool like module output.\n\n- PyprojectPayload in intent.py; parsing and validation in config.py, which\n  rejects malformed tables and unknown tool names when the template loads.\n- JSON schema, generated template schema doc, and the docs generator updated.\n- cli, ml, and astro gate their tool configuration; the build system and\n  entrypoint stay plain strings because no tool toggle should remove them.\n- The contract test compares a tool-bound payload only with its own tool's\n  baseline, and a new check requires built-in payloads that configure a tool to\n  declare it.\n- Docs: authoring guide, built-in templates page, CONTRIBUTING.\n\nDefault scaffolds are byte-identical, and an existing project that opts a tool\nout behaves the same as before.\n\n* feat(config): install template dev packages only while their tool is enabled\n\nTemplate dev_dependencies were installed regardless of tool flags, so\n'--no-pytest' still added pytest-cov for cli and httpx and pytest-asyncio for\napi, the same leak that pyproject payloads had.\n\nAdd [dev.tool_dependencies], a table that maps a tool to the dev packages it\nneeds. The orchestrator installs them only while that tool is active and\nattributes them to it, like a module's own output. [dev].dev_dependencies keeps\nits meaning for packages no toggle should remove. Tool names are validated when\nthe template loads, through the same check the payload parser now shares.\n\n- cli and api move their test packages under the pytest tool.\n- JSON schema and the schema fixture generator updated. The fixture now\n  renders dev_dependencies inside [dev], where the parser reads it; it used to\n  print it as a root key that would have been ignored.\n- Contract tests: gated packages are covered by the version-pin check, and a\n  new check flags tool-owned packages (pytest-*, coverage, ruff, mypy) that are\n  installed unconditionally.\n- Docs: the authoring guide and built-in templates page describe the table. The\n  tool-bound sections in the authoring guide moved to the end of Level 1, after\n  they had been inserted into the middle of the appends and dependency\n  discussion.\n\nDefault scaffolds are byte-identical, dependency order included.",
          "timestamp": "2026-09-19T15:21:25-07:00",
          "tree_id": "564cf65a98bc48eed1ca5bca0115a3f757b24235",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/3edbeef5746065be0180d31db05c5da2ae54d00a"
        },
        "date": 1789856557495,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 185.22,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 259.76,
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
          "id": "68f3d3d1e6cf6fb13123c841cb91a750bb146f19",
          "message": "fix(pyproject): settle the generated layout, keep ml's notebook tools, and drop empty recipe tables (#279)\n\n* fix(pyproject): settle the generated layout and keep ml's notebook tools installed\n\nLayout. uv add appends [dependency-groups] and the recipe write inserts\n[tool.protostar] after the managed merge has formatted pyproject.toml, so a\nfresh project ended with dependency groups last and no blank line before them,\nand [tool.hatch] under the Tool Configuration banner. _write_recipe now runs a\nfinal formatting pass, only when Protostar created the file so a project the\nuser already had keeps its own order.\n\n- [dependency-groups] and [tool.hatch...] sit above the banner; only tooling\n  lives beneath it.\n- [tool.protostar] gets a '# ---- Protostar ---- #' header and sorts last.\n- Every table header is preceded by a blank line unless a comment precedes it.\n\nml. jupyterlab, nbdime, and ipywidgets were declared as docs_dependencies.\nuv sync installs the dev group by default but not docs, so the first just\nrecipe (each depends on sync) removed them. They are now dev dependencies.\n\nGuards: built-ins may not declare docs_dependencies, and the exhaustive suite\nruns a plain uv sync after scaffolding and asserts every declared package is\nstill installed. Formatter and executor tests cover the ordering, the header,\nblank lines, and that an existing pyproject is left alone.\n\nDocs describe the layout, the docs-group rule, and the new checks.\n\n* fix(recipe): write [tool.protostar] tables only while they have entries\n\nNew projects carried empty [tool.protostar.tools], [tool.protostar.metadata],\nand [tool.protostar.bindings] tables. Drop them from the file; an absent table\nnow means empty.\n\ndecode_recipe required all three to be present, so omitting them is a reader\nchange as well as a writer change: the required set is now version, mode,\npython, docker, ide, fallback, and context, which are always populated. Recipes\nwritten earlier, with empty tables, still decode, and the next init tidies\nthem. to_dict() is unchanged because it also feeds the JSON output agents read;\nonly the file representation differs.\n\nOmitting a table means a later run can have to add one to an existing recipe.\ntomlkit appends it after the trailing comment that belongs to the recipe's last\ntable, which mislabeled the next tool's header (ml_merged put [tool.protostar.tools]\nunder '# ---- Mypy ---- #'). Late-added tables are now moved to their canonical\nposition, and a blank line is guaranteed before each recipe header without\ntouching any other bytes.\n\nThe recipe and lifecycle docs no longer tell users to edit an existing tools\ntable; they say to add it when needed.",
          "timestamp": "2026-09-19T16:19:34-07:00",
          "tree_id": "85da8ca266c4c0b7698c313ad1f5d943a72e23da",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/68f3d3d1e6cf6fb13123c841cb91a750bb146f19"
        },
        "date": 1789860047377,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 196.54,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 273.06,
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
          "id": "5beee1b9171b4a9ec0ccf9eb85fcf7cfcebd14ea",
          "message": "refactor(pyproject): one layout spec and a section model, on tomlkit's public API (#280)\n\n* refactor(pyproject): one layout spec and a section model, on tomlkit's public API\n\nThe layout of the pyproject.toml Protostar creates was defined in several places\nthat could drift apart, applied through regex passes over serialized text, and\nimplemented by rewriting tomlkit's private container state. This replaces all\nof it with src/protostar/toml_layout.py, and changes no generated byte: every\nsnapshot is identical.\n\n- One spec. ROOT_ORDER and TOOL_SECTIONS decide order, header titles, and which\n  comment lines are managed. TOOL_SECTION_NAMES is derived from it. This removes\n  the parallel lists (_RAW_TOOL_HEADERS, _FIRST_TOOL_HEADER_RE, tool_order,\n  _PACKAGING_TOOLS) that had to be edited together, and one of which was missed\n  when the Protostar header was added.\n- A section model. The file is a list of Section pieces (each root table, and each\n  child of [tool]) rendered with public tomlkit calls; joining them reproduces the\n  input byte for byte, and managed banner and header lines are matched by exact\n  line, not pattern. Managed decoration trails a piece, so it can no longer be\n  mislabelled when a table is added inside a section.\n- Formatting builds the file from those sections in spec order. Nothing outside a\n  section, including blank runs inside multi-line strings, is touched.\n- edit_recipe edits [tool.protostar] as its own section, so no other byte of the\n  file changes; a new recipe is inserted after the last tool section with a clean\n  seam and in the file's own newline style. Recipe tables are composed in schema\n  order with one blank line between them, replacing the tomlkit body reordering\n  and the recipe-specific text pass.\n- The parity fallback is no longer silent: it is logged and surfaced as a warning\n  diagnostic (Left pyproject.toml unformatted: ...).\n\nTests: split and join are byte-exact over a corpus of files a user might already\nhave (irregular spacing, CRLF, out-of-order tables, arrays of tables, dotted keys,\nan inline [tool], no trailing newline, user-written headers); every combination\nof the known tools is checked for canonical order, one header each, idempotence,\nand that the fallback never triggers; two guards fail if a module or template\nwrites a tool table with no spec entry, and one fails if any source reaches into\ntomlkit's private state.\n\nMerging into an existing project is unchanged and still appends new tool tables.\n\n* docs: describe the pyproject.toml layout and how to add a tool\n\nAdds a developer page for the layout spec, the section model, the two ways the\nlayout is applied, and the safety fallback, and records the rule that a new\ntool table needs a ToolSection entry in the built-in template contract.",
          "timestamp": "2026-09-19T16:54:58-07:00",
          "tree_id": "ca3761e16d2df4632426188013621eeb5945267f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/5beee1b9171b4a9ec0ccf9eb85fcf7cfcebd14ea"
        },
        "date": 1789862174958,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 198.63,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 278.14,
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
          "id": "954236764e9b67711296a0e322dc9b770cafffff",
          "message": "fix(pyproject): place tables a merge adds by the layout spec (#281)\n\n* fix(pyproject): place tables a merge adds by the layout spec\n\nA tool enabled by a later run, whether through init --force-merge or a lifecycle\nsync, was appended after the last existing section, so it landed after\n[tool.protostar] with its header under Protostar's. Tables a merge adds are now\nplaced by the same spec that lays out a fresh file.\n\nplace_new_sections splits the merged document into sections, keeps every section\nthat already existed, and inserts each new one after the last existing section\nthat ranks at or below it. Only the two seams change: each gets exactly one blank\nline, in the file's own newline style, and a missing final newline is supplied.\n\nHeaders are re-homed, because a header announces the section after it. A new,\nknown tool gets its header and takes the banner (and a sibling's header) with it\nwhen it now comes first; a tool the user already had is never labelled, and the\nbanner is added only if the file has none. A comment directly above a table stays\nwith that table when something is inserted before it, while a comment set apart by\na blank line, or by a managed header, stays put.\n\nThe two hand-written blocks in reconcile_toml's patch that attached banner and\nheader comments to whichever table happened to be last are deleted. Placement is\nproven safe by parsing the result against a plain dump; if it cannot be, the plain\ndump is used and the reason surfaces as a diagnostic, as formatting already does.\nOnly pyproject.toml targets are placed; other TOML targets are dumped as before.\n\nTests: inserting into a canonical file gives exactly the canonical file, for every\npair of present and added tools; adding A then B gives the same file as B then A;\nforeign files keep their lines, comments, CRLF, and missing final newline; and\neach rule above is mutation-checked. test_snapshots asserted the old order (Mypy\nafter Protostar) and now asserts the intended one.\n\n* docs: describe how a table added to an existing pyproject is placed\n\nReplaces the note that later merges still append with the actual rules: rank\nplacement, exact seams, header and banner re-homing, comments that travel with\ntheir table, and order independence.",
          "timestamp": "2026-09-19T17:13:37-07:00",
          "tree_id": "4eaa1ec7a88eedf8e81f65ae78763a3352f209df",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/954236764e9b67711296a0e322dc9b770cafffff"
        },
        "date": 1789863294625,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 203.3,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 271.5,
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
          "id": "a5c85af3a3686f141bdbb78d721a421d897189f0",
          "message": "feat(ci): add template hooks smoke matrix, unify test suite, and remove renovate pre-commit hook (#282)\n\n* feat(ci): add template hooks smoke matrix and unify test suite\n\n* fix(ci): install protostar executable via uv tool in template smoke job\n\n* fix(ci): check commit-msg hook conditionally on templates that declare it\n\n* fix(ci): disable git credential manager and autocrlf on windows smoke runner\n\n* fix(ci): normalize temp path with cygpath and add diagnostics to smoke runner\n\n* fix(ci): pre-stage files for verbose prek run and redirect stdin from /dev/null\n\n* fix(ci): run prek with -vvv and --no-progress for Windows debug tracing\n\n* fix(ci): configure windows defender exclusions, pre-cache renovate and increase smoke timeout\n\n* fix(tooling): remove renovate pre-commit hook to eliminate node.js dependency\n\n* fix(ci): stage files before commit-msg canary check in smoke runner\n\n* fix(ci): prevent bash -e premature exit during canary subshell in smoke runner",
          "timestamp": "2026-09-19T18:47:35-07:00",
          "tree_id": "77822dae82d1e40b9da16e5a897f570db8d005a0",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a5c85af3a3686f141bdbb78d721a421d897189f0"
        },
        "date": 1789868927496,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 189.8,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 262.12,
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
          "id": "9d43786aa2b022318c7e7370e5e961ae191eb95a",
          "message": "feat(ci): build and smoke-test the cli and api Docker images (#283)\n\n* feat(ci): build and smoke-test the cli and api Docker images\n\nAdd a template-docker-build job that scaffolds the cli and api templates\nwith --docker, builds the generated Dockerfile for real, and runs the\nimage (cli --help, api /health).\n\nThe first real build failed: the generated .dockerignore excluded README*,\nbut the scaffolded pyproject declares README.md as the package readme, so\nhatchling could not build the project inside the image. Stop ignoring the\nREADME and refresh the snapshots.\n\n* ci: drop redundant docker container cleanup step",
          "timestamp": "2026-09-19T19:09:43-07:00",
          "tree_id": "8b38ce21b9e1a5e29bdf3ba4f00ed85c830ea098",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/9d43786aa2b022318c7e7370e5e961ae191eb95a"
        },
        "date": 1789870259075,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 191,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 265.09,
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
          "id": "e3f845d1abfd03c4a25a5140dfc3bfe69015847c",
          "message": "feat(templates): add built-in lib template for reusable packages (#284)",
          "timestamp": "2026-09-19T19:45:21-07:00",
          "tree_id": "a4fbe29a40372708968dcfde875c9f78c675e65c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/e3f845d1abfd03c4a25a5140dfc3bfe69015847c"
        },
        "date": 1789872395008,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 197.77,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 280.25,
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
          "id": "8688cbf7b8a5cca0db9881c1b4891f12b26ee8a5",
          "message": "fix(config): reject template aliases that shadow built-in templates\n\nA user alias in `[templates]` could reuse a built-in template name, and\nthe two call sites that resolve an alias disagreed about which template\nwon. `discover_templates` appends built-ins before user aliases, so\n`--template api` broke on the first match and got the built-in, while\nthe wizard indexed the list into a dict and got the alias. Picking the\nrow displayed under \"Built-in Templates\" in the wizard therefore\nselected the external template, carrying that alias's `trusted` flag\npast the remote-execution warning. Case made it worse: `--template`\nfolds case, so `[templates.API]` was unreachable entirely while still\nshadowing `api`.\n\nThere is no correct silent answer here, so the ambiguity is refused at\nload time rather than resolved by precedence. `UserConfig.__post_init__`\nnow rejects an alias that shadows a built-in, or two aliases that differ\nonly by letter case, with a hint naming the config file. Aliases stay\nunique by construction, which lets both resolution sites keep their\ncurrent, now-equivalent lookups instead of growing defensive code.\n\nBuilt-in enumeration moves into `_builtin_template_files`, so discovery\nand the new `builtin_template_aliases` share one source of truth; the\ntry/except that used to wrap the whole discovery loop now guards only\nthe resource listing it was meant for.\n\nRendering the new error exposed a second bug: `main` passed domain error\ntext straight to `Text.from_markup`, so Rich ate any bracketed span. The\nexisting \"Unrecognized fields in '[templates.backend]'\" error had been\nprinting as \"Unrecognized fields in ''\", hiding the offending table.\nError text is data, so it is escaped at the render boundary rather than\nreworded upstream, keeping the core free of UI concerns.\n\nArchitectural invariants:\n- Template identity is case-insensitively unique across built-ins and\n  user aliases; `discover_templates` never emits one alias twice.\n- Built-in template names are reserved and cannot be redefined by\n  configuration.\n- Domain error messages and hints are plain text; escaping them for the\n  terminal is the CLI layer's job.",
          "timestamp": "2026-09-19T19:52:40-07:00",
          "tree_id": "034080e0feaf51f8568f350dcb4206dc0fd29a06",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/8688cbf7b8a5cca0db9881c1b4891f12b26ee8a5"
        },
        "date": 1789872886833,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 148.93,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 209.52,
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
          "id": "58d65a688e45e83a4882e21ca7e6bf33fb9a1cb7",
          "message": "docs(templates): document pinning a template revision\n\nTemplate sources could already be pinned, but nothing said so. The URL\ntranslators in `network.py` substitute only the host and path prefix, so\nwhatever ref sits in the path survives: a `blob/v1.2.0/api.toml` link\nresolves to the raw file at that tag. Teams hitting \"upstream changed\ntheir template and now everyone's scaffolds differ\" had no documented\nanswer, despite the mechanism being a URL away.\n\nDocuments the pinned URL form per host, and calls out the one case that\nsilently does not pin: a bare repository URL is rewritten to\n`archive/refs/heads/main.zip`, so multi-file templates need the tagged\narchive URL spelled out. Both GitHub forms were verified against a live\ntag and commit before being written down.\n\nAlso documents what the pin buys, which is the part that is not obvious\nfrom the URL:\n\n- A SHA-256 digest of the resolved template is always recorded, so\n  `protostar status` reports drift on unpinned sources too.\n- Only a full 40-character commit SHA is recorded as `source_revision`\n  (`resolve_remote_source` matches 40/64 hex); a tag is not, because a\n  tag can move.\n- The resolved locator feeds `TemplateReference.identity`, so pinning is\n  durable in both directions: a pinned project keeps that revision, and\n  bumping the pin in `pyproject.toml` is rejected by\n  `check_template_identity` as template switching. Projects that want\n  `sync` to deliver updates must stay on a floating ref.\n\nDrive-by: the `[templates.enterprise-api]` example used a `.git` suffix,\nwhich the archive translator turns into\n`https://github.com/myorg/enterprise-template.git/archive/refs/heads/main.zip`\n-- a 404, confirmed against GitHub. Dropped the suffix in the docs and in\n`DEFAULT_CONFIG_CONTENT`, which ships the same example as a comment in\nevery user's config file, and regenerated the docs asset.",
          "timestamp": "2026-09-19T19:59:38-07:00",
          "tree_id": "3b14d88f0d59d3fa22077a80a90dc0a56b040d19",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/58d65a688e45e83a4882e21ca7e6bf33fb9a1cb7"
        },
        "date": 1789873305965,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 154.35,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 213.2,
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
          "id": "318374e8296871f43acd29ee9c9adcbfcd8ee750",
          "message": "refactor(templates): curate built-in templates and modernize api and astro (#285)\n\n* refactor(templates): curate built-in templates and modernize api and astro\n\n* fix(ci): update template-hooks-smoke matrix to use current templates",
          "timestamp": "2026-09-19T20:14:16-07:00",
          "tree_id": "15bac6bbfd8fd691719131e50e747064fb35638b",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/318374e8296871f43acd29ee9c9adcbfcd8ee750"
        },
        "date": 1789874117012,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 148.76,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 197.37,
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
          "id": "414cd8c22ccc0965889c251d45c2aee4e76077c1",
          "message": "feat(config): select or disable the configuration file per run\n\nEvery run read `~/.config/protostar/config.toml` and nothing else could\nbe said about it. The path was a module constant resolved at import from\n`XDG_CONFIG_HOME`, so the only way to influence it was to relocate the\nwhole XDG tree before the process started -- which is why `just sandbox`\nconstructs an entire fake `$HOME` largely to get configuration\nisolation. CI inherited whatever the runner happened to have, and\nreproducing a config-dependent bug report meant editing your own file.\n\nAdds `--config <path>` and `--no-config`, with `PROTOSTAR_CONFIG` as the\nenvironment equivalent for scripts that cannot append a flag to every\ninvocation (an empty value disables, matching `--no-config`). Precedence\nis flag, then environment, then the default location.\n\nSelection is modeled rather than stringly-typed: `ConfigSource` pairs a\n`ConfigOrigin` with the resolved path, where `None` means configuration\nis disabled. `CONFIG_FILE` survives as the default location, so the one\nmodule attribute tests and scripts already patch stays the single source\nof truth; `active_config_source()` reads it at call time. The CLI applies\nits choice immediately after parsing, ahead of any handler that loads\nconfiguration -- the wizard path is unaffected because it only fires when\n`sys.argv` carries no flags at all.\n\nThe load path grew two behaviors that the feature depends on:\n\n- An explicitly selected file that does not exist is an error. Silently\n  degrading to defaults would defeat the entire point of naming the file,\n  and a typo in CI would go unnoticed. A missing file at the *default*\n  location remains ordinary and still yields built-in defaults.\n- `discover_templates` no longer swallows every exception from\n  `UserConfig.load()`. That blanket `except Exception` meant\n  `--list-templates` answered cheerfully while ignoring a broken or\n  missing selected config. The guard moves to `get_available_templates`,\n  where it belongs and is already tested: shell completion is the one\n  caller that must never fail loudly.\n\n`protostar config` follows the selection too, editing (and seeding) the\nchosen file, and refusing to open anything under `--no-config`.\n\nArchitectural invariants:\n- `active_config_source()` is the only answer to which configuration a\n  run reads; no component consults `CONFIG_FILE` directly.\n- An explicit selection is honored or reported, never silently ignored.",
          "timestamp": "2026-09-19T20:27:13-07:00",
          "tree_id": "040a76b66c93a490e786883bea27bfc3afa3bbc3",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/414cd8c22ccc0965889c251d45c2aee4e76077c1"
        },
        "date": 1789874970614,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 173.7,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 248.76,
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
          "id": "e8a4895949a5e60f0c51dd600975d01894662d5f",
          "message": "chore(deps): lock file maintenance (#286)\n\nCo-authored-by: renovate[bot] <29139614+renovate[bot]@users.noreply.github.com>",
          "timestamp": "2026-09-21T09:36:28-07:00",
          "tree_id": "96333835f302fc798be76dca1276fc4a8fb3b058",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/e8a4895949a5e60f0c51dd600975d01894662d5f"
        },
        "date": 1790008653048,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 158.33,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 219.1,
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
          "id": "d8815206cc6c0f60919042d7f7055e99fb477c4c",
          "message": "fix(scripts): eliminate initial demo frame flicker via native redraw\n\nReplace 'clear\\n' command execution with native Ctrl-L form-feed in PTYSession\nto avoid shell echoing of the command word, eliminate Zsh PROMPT_EOL_MARK\ninverted '%' line-fill artifacts, and synthesize a clean initial frame at\nt=0.0. Regenerate demo cast and gif assets.",
          "timestamp": "2026-09-21T11:34:30-07:00",
          "tree_id": "c034c69d64e2205c21209e89caf65d961d783cff",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/d8815206cc6c0f60919042d7f7055e99fb477c4c"
        },
        "date": 1790015768706,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 192.25,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 266.88,
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
          "id": "60cd1ce8716662e74e8914641b33ec83bd97286d",
          "message": "fix(docs): add Symbols Nerd Font fallback for asciinema player demo icons",
          "timestamp": "2026-09-21T11:53:54-07:00",
          "tree_id": "21f71528298bfd321b18876f16b1cde8d0188d49",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/60cd1ce8716662e74e8914641b33ec83bd97286d"
        },
        "date": 1790017009511,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 197.91,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 277.37,
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
          "id": "c9427e78226a557f9d98cfff8445d9b6d7b0d40c",
          "message": "feat(docs): defer asciinema playback until scrolled into view",
          "timestamp": "2026-09-21T11:57:53-07:00",
          "tree_id": "cab9fb1c04468e2c56f6b41657cd9132feadcbdf",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/c9427e78226a557f9d98cfff8445d9b6d7b0d40c"
        },
        "date": 1790017234248,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 189.25,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 260.54,
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
          "id": "c5f3114a13efcecf13f8c7a939196fdeb8c5e7d5",
          "message": "perf(docs): pre-warm Symbols Nerd Font for asciinema demo players",
          "timestamp": "2026-09-21T12:15:37-07:00",
          "tree_id": "ec9009a71e9b867772a4512dba8a5d5370cf5eac",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/c5f3114a13efcecf13f8c7a939196fdeb8c5e7d5"
        },
        "date": 1790018232289,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 209.88,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 294.33,
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
          "id": "f5d146133adab025a4f166a4a6b9d48e2b12e358",
          "message": "feat(tooling): scaffold a managed AGENTS.md guide (#287)\n\nAdd an --agents tool that writes an AGENTS.md guide for coding agents,\nbuilt from the project's actual tooling: the Python/uv workflow, the\njust recipes (or the raw commands when just is off), and the hook\nrunner. The guide lives in a Protostar region, so sync keeps it current\nwhile user notes outside the markers are never touched and edits inside\nit surface as conflicts.",
          "timestamp": "2026-09-21T12:33:31-07:00",
          "tree_id": "d81f6e1b42908bf98082433584c8166fd0303646",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/f5d146133adab025a4f166a4a6b9d48e2b12e358"
        },
        "date": 1790019274240,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 152.74,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 211.59,
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
          "id": "23214bf47f419c4939d122572c7fc19ac4303442",
          "message": "fix(sandbox): upgrade test harness to Node.js 22 LTS\n\nCopy Node.js 22 LTS from node:22-bookworm-slim into the protostar-test-harness\nDocker image to fix a SyntaxError when running markdownlint-cli2, which requires\nNode 20+ for regex v-flag support.",
          "timestamp": "2026-09-21T12:37:11-07:00",
          "tree_id": "fc2c93af12e81a90b9afdc8012cd894a86eca35e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/23214bf47f419c4939d122572c7fc19ac4303442"
        },
        "date": 1790019524125,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 190.97,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 264.8,
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
          "id": "a76693e3e6bce82841d52ac987fab43e926d34aa",
          "message": "ci(workflows): configure windows defender exclusions for test and smoke runners",
          "timestamp": "2026-09-21T12:51:27-07:00",
          "tree_id": "8019a5ceb1c0d70322c4c09e0ac999ecba3b9b33",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a76693e3e6bce82841d52ac987fab43e926d34aa"
        },
        "date": 1790020412799,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 198.71,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 279.43,
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
          "id": "23214bf47f419c4939d122572c7fc19ac4303442",
          "message": "fix(sandbox): upgrade test harness to Node.js 22 LTS\n\nCopy Node.js 22 LTS from node:22-bookworm-slim into the protostar-test-harness\nDocker image to fix a SyntaxError when running markdownlint-cli2, which requires\nNode 20+ for regex v-flag support.",
          "timestamp": "2026-09-21T12:37:11-07:00",
          "tree_id": "fc2c93af12e81a90b9afdc8012cd894a86eca35e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/23214bf47f419c4939d122572c7fc19ac4303442"
        },
        "date": 1790021133173,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 166.03,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 232.69,
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
          "id": "809c47461b90fa3d86b6a3fd402eecc3120b0a8b",
          "message": "feat(ci): parallelize test matrix with pytest-xdist and loadfile distribution",
          "timestamp": "2026-09-21T13:06:01-07:00",
          "tree_id": "0bebdce79c37640344910eec7527ecf8f1224130",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/809c47461b90fa3d86b6a3fd402eecc3120b0a8b"
        },
        "date": 1790021320365,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 153.55,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 215.53,
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
          "id": "479f4684f66fd84dc917ff7264b1ca20b4b4b0d3",
          "message": "feat(test): parallelize local full test runs in justfile and pre-push hook",
          "timestamp": "2026-09-21T13:11:53-07:00",
          "tree_id": "821c33a5d75221094e4e7b2db14c910870d744ce",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/479f4684f66fd84dc917ff7264b1ca20b4b4b0d3"
        },
        "date": 1790021606240,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 188.16,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 258.46,
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
          "id": "bb7b9ece996d3320847c83ef5e66af71696e5fc8",
          "message": "feat(docs): scaffold zensical.toml instead of mkdocs.yml (#288)\n\nScaffold native zensical.toml for Zensical documentation instead of legacy mkdocs.yml,\n\naligning generated projects with Protostar's own dogfooded configuration and modern TOML\n\nconventions.",
          "timestamp": "2026-09-21T13:24:19-07:00",
          "tree_id": "f38d119be9ed552a5da7a0b845374acca832d873",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/bb7b9ece996d3320847c83ef5e66af71696e5fc8"
        },
        "date": 1790022329124,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 165.86,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 231.34,
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
          "id": "1109e6b474787070a622965a522a50eab3c4097c",
          "message": "fix(yaml): keep line width and indentation when merging YAML (#289)\n\nAny accepted YAML edit re-emitted the whole document with a fixed\n2/4/2 indentation and the emitter's default 80-column width. Untouched\nlong lines were folded (leaving trailing spaces) and indentless\nsequences were re-indented, so one value change rewrote most of a file.\n\nDetect block indentation from the local document, emit with no line\nwidth limit, and write a fully accepted missing file as the desired\ntext verbatim so its comments survive.",
          "timestamp": "2026-09-21T14:07:10-07:00",
          "tree_id": "34cc94a435af2ab966cd1e45155444c067440c2a",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1109e6b474787070a622965a522a50eab3c4097c"
        },
        "date": 1790024905035,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 201.34,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 277.08,
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
          "id": "1bcf8612d7b7e9f552f1dbf773c9684f99d5da40",
          "message": "refactor(yaml): describe keyed sequences with a per-document spec (#290)\n\nPre-commit's repository/hook identities were hardcoded across the YAML\nadapter, preservation inspection, and state validation. Describe each\nYAML document with a YamlDocumentSpec registered by path, so a new\ndocument declares its keyed sequences instead of adding more branches.\n\nBehavior changes: new keyed records are inserted after their nearest\nearlier desired sibling instead of appended, local records without an\nidentity are kept in place as foreign content instead of raising, and\nthe pin guard holds the revision path instead of re-encoding the desired\ndocument, so other additions keep their key order and styling.",
          "timestamp": "2026-09-21T14:21:35-07:00",
          "tree_id": "d354770cc38c7480b6e18f3b013271fdf29c20fa",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1bcf8612d7b7e9f552f1dbf773c9684f99d5da40"
        },
        "date": 1790025768811,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 202.52,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 271.73,
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
          "id": "dcfa98a4205c7f7b3a1a899cd677a68700e669a9",
          "message": "feat(ci): merge GitHub Actions workflows by job and step (#291)\n\nci.yml and release.yml were owned by a whole-file checksum, so any edit\n(including Renovate pinning action digests, which the scaffolded Renovate\npreset does) froze them against every later Protostar update.\n\nBoth workflows now reconcile through the YAML adapter under one\nWORKFLOW_SPEC: mappings merge by key, steps are keyed by name, and the\ndocument is complete, so owned content the generator stops emitting is\nremoved when unedited and kept with a retracted conflict when edited.\nTwo guards run as holds: a job Protostar does not own is never grafted\ninto, and a changed ref on the same action is left to the user.\n\nThe generator names every step and folds the matrix pytest variants into\none \"Run tests\" step so variants update steps in place. Append regions\nare rejected for structurally merged YAML files.",
          "timestamp": "2026-09-21T14:43:46-07:00",
          "tree_id": "17b2a9a22f4f8bbd82df4594e6cd4f9895004c4a",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/dcfa98a4205c7f7b3a1a899cd677a68700e669a9"
        },
        "date": 1790027105260,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 195.48,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 274.24,
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
          "id": "5328513dd8eee3f0417e961e6965c1b3a784c8c6",
          "message": "refactor(documents): move per-file merge policy out of the format engines (#292)\n\nThe YAML and TOML engines carried file-specific knowledge: yaml_ast defined the\nCodecov, pre-commit, and workflow specs, targets, and registry; toml_ast held\npyproject's set-like paths, layout branch, seed splitting, and include edits.\nEach managed file now owns its target, spec, and guards in\nsrc/protostar/documents/, and the engines reconcile whatever spec they are handed.\n\nYAML policies plug in through one YamlGuard (holds plus conflicts), so pre-commit\nand workflows share Reconciliation._reconcile_document with Codecov, and\nTomlDocumentSpec carries set-like paths, super tables, and layout for pyproject.",
          "timestamp": "2026-09-21T15:02:59-07:00",
          "tree_id": "aeb701fb64d8a9addd574a28bca47d9036c3e947",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/5328513dd8eee3f0417e961e6965c1b3a784c8c6"
        },
        "date": 1790028256375,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 197.52,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 269.99,
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
          "id": "9ab3a2a6763bb2951772d7801dd65de6a8d12c62",
          "message": "feat(docs): merge zensical.toml by structure (#293)\n\nzensical.toml moves from a write-once seed to the structured TOML merge.\nProtostar manages theme features (by membership) and the mkdocstrings\nplugin; identity, navigation, look, and the Markdown extension list are\nseeded once. The document is left alone when it keeps its settings outside\n[project] or when creating it would displace an mkdocs.yml.\n\nSeed-only keys become document policy: TomlDocumentSpec.seed_paths, held\nat their owned value by reconcile_toml. pyproject's personal metadata\nmoves to it, replacing the declaration-time split and ContributionPolicy.\n\nThe scaffold's extension list now mirrors Zensical's defaults, so footnotes,\ntask lists, and the other defaults render again.",
          "timestamp": "2026-09-21T15:55:10-07:00",
          "tree_id": "483424417ee59378ce6ecec622e2eb6253d7ea0e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/9ab3a2a6763bb2951772d7801dd65de6a8d12c62"
        },
        "date": 1790031388636,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 205.23,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 278.56,
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
          "id": "db0d27347c49f7baf00cadecc551568530593332",
          "message": "feat(docs): merge .readthedocs.yaml by structure (#294)\n\n.readthedocs.yaml was a free-form seed: written once, never updated. It is\nnow a structured YAML contribution, like Codecov, under a complete-document\npolicy so jobs Protostar stops generating are retracted.\n\nTwo rules come from how Read the Docs reads the file. It loads the first\nfile matching ^\\.?readthedocs.ya?ml$ in directory-listing order, so the\nmanaged file is never created next to a sibling (new YamlDocumentSpec\ndisplaces field, mirroring TOML). And Protostar's build jobs replace build\n\nsteps: RTD rejects build.jobs next to build.commands, and the jobs skip the\ndefault steps that sphinx, mkdocs, python, and conda configure. The new\nguard holds build.jobs in either case, reporting unowned only when the hold\nwithholds a change, since conflicts fail sync --check.\n\nGuards that depend only on decoded documents are now registered in\ndocuments.YAML_GUARDS (workflows and Read the Docs), and YamlGuardPolicy\nmoves to yaml_ast.",
          "timestamp": "2026-09-21T16:18:53-07:00",
          "tree_id": "25242a2f4919dfd484d3dcdde7b891f26bd7e37c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/db0d27347c49f7baf00cadecc551568530593332"
        },
        "date": 1790032792951,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 152.91,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 209.26,
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
          "id": "63526f18d9f48d51c86169000070ebc56e75789a",
          "message": "fix(cli): show what init writes in the dry-run filesystem view (#295)\n\nThe dry-run count summed only directories and free-form files, so it\ndisagreed with the tree beneath it, which also listed merged documents\nand regions. Both views also used raw declared paths: the tree showed\nsrc/<% PACKAGE_NAME %>/ and left out files init generates outside the\nfilesystem slice (pre-commit config, workflows, justfile, Docker files)\nplus .gitignore and IDE settings.\n\nThe count and tree now share one path set built from new manifest\n\nmethods: target_directories() renders declared directories, and\nwritten_files() extends target_files() with .gitignore and IDE settings,\nwhich collision detection deliberately leaves out. Both render with the\nrecipe's names, never environment bindings. Engine state and subprocess\noutput (uv.lock, .python-version) stay out; the Tasks panel covers the\ncommands that produce them. The label now reads \"to create or update\".\n\nThe docs generator renders the dry run from a fixed demo_project\ndirectory, matching the regression snapshots, so the SVG stays\nbyte-stable now that paths render with the project name.",
          "timestamp": "2026-09-21T16:36:37-07:00",
          "tree_id": "733fad7dbe01c0e29a7200b2b73e1e5c6ab1b088",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/63526f18d9f48d51c86169000070ebc56e75789a"
        },
        "date": 1790033868290,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 191.86,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 263.85,
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
          "id": "1007795010807ff50ed74552dc08ca1347ce39d5",
          "message": "feat(docs): add package manager toggle and overflow handling to hero install box",
          "timestamp": "2026-09-21T16:49:31-07:00",
          "tree_id": "abfee76e9cb3fcdbe66c367568898db3d03c459c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1007795010807ff50ed74552dc08ca1347ce39d5"
        },
        "date": 1790034715130,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 199.77,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 275.65,
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
          "id": "c42cead22736d6a98422878d47d897662ed6fb6c",
          "message": "feat(documents): edit each document wherever its tool reads it (#296)\n\nWhether two paths hold the same configuration is a fact about the tool\nthat reads them, not about YAML: Read the Docs reads .readthedocs.yml,\npre-commit ignores .pre-commit-config.yml while prek reads it, Codecov\nreads four names in three folders, and GitHub Actions runs ci.yml and\nci.yaml as two workflows. Renaming a managed file used to orphan it\nbehind a permanent \"unowned\" warning, and an existing file under another\nname was never adopted or seen by the collision check.\n\nEach document module now declares a DocumentLocations: aliases Protostar\nedits in place, competitors it never edits, and whether the tool reads a\nsingle configuration. One resolver picks the file a run edits: an owned\nfile in place, else a single existing file, adopted or followed after a\nrename (ownership, baseline, and hook-pin provenance move with it). For\ntools that read one configuration, any other copy next to the edited\nfile is reported as duplicate-identity, and several unowned copies are\nheld. Workflows alias the extension pair without conflicts.\n\nThis replaces three copies of the same idea: Renovate's ALTERNATIVES\nbranch and the displaces fields on TomlDocumentSpec and YamlDocumentSpec,\nwhich the merge engines never read. The collision prompt, dry-run tree,\nstate validation, preserved deviations, and append-region rejection all\nlook documents up through the catalog. Guards receive the real file path\nso conflicts name it.",
          "timestamp": "2026-09-21T17:19:59-07:00",
          "tree_id": "793dab7165cf2b92b6c3ebed4dc3fbd86dd5194d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/c42cead22736d6a98422878d47d897662ed6fb6c"
        },
        "date": 1790036475025,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 207.96,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 278.18,
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
          "id": "8282438eecb5231690c43b9c65db5bcd308ce4af",
          "message": "docs: add PyPI link to footer social links",
          "timestamp": "2026-09-21T17:34:57-07:00",
          "tree_id": "46ee543e55b0f47d730ab62c8c9b8bfe7f39eda3",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/8282438eecb5231690c43b9c65db5bcd308ce4af"
        },
        "date": 1790037391284,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 199.42,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 271.59,
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
          "id": "7d6a8ad18ba541431d23e80ef23f7d30200846b0",
          "message": "fix(docs): follow project minimum Python in .readthedocs.yaml\n\nDynamically resolve the project's minimum Python version from manifest\nmetadata or pyproject.toml and populate build.tools.python in\n.readthedocs.yaml instead of hardcoding to 3.12.",
          "timestamp": "2026-09-21T18:07:14-07:00",
          "tree_id": "4d5419118418f94634ffa6677f6b9c32d311e259",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/7d6a8ad18ba541431d23e80ef23f7d30200846b0"
        },
        "date": 1790039378018,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 198.7,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 274.1,
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
          "id": "b3a44e8088d8c172f3f181e420e9876753170134",
          "message": "feat(docs): migrate documentation hosting to GitHub Pages with multi-versioning (#297)",
          "timestamp": "2026-09-21T20:24:39-07:00",
          "tree_id": "2f4d47ca35844cc704cfe12e45a765476b19ea67",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/b3a44e8088d8c172f3f181e420e9876753170134"
        },
        "date": 1790047559304,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 199.26,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 277.47,
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
          "id": "2b3c04a4ed59acd40c988b58d61d10d7563c74b0",
          "message": "feat(hooks): scaffold whole-project mypy, pre-push tests, and config linting (#298)\n\n* feat(hooks): scaffold whole-project mypy, pre-push tests, and config linting\n\n- mypy checks the whole project in the hook and in CI, matching `just typecheck`\n- pytest runs as a pre-push hook, filtered to src/, tests/, and lock inputs\n- the hook install is queued after every module builds, so each installed\n  hook script (commit-msg, pre-push) is owned and rolled back\n- ci/release lint workflows with actionlint, installed through uv\n- renovate and readthedocs validate their config with check-jsonschema,\n  matching every path the tool reads it from\n\n* feat(hooks): name the resolved document file in schema hooks\n\nA hook that validates a managed document now matches only the file that\nholds it in this run: the created target, an adopted alias, or a followed\nrename. A held document keeps matching every path its tool may read.",
          "timestamp": "2026-09-21T21:40:04-07:00",
          "tree_id": "03f5625ec8dd098aecf077e11f2221d4a4603e2c",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/2b3c04a4ed59acd40c988b58d61d10d7563c74b0"
        },
        "date": 1790052067005,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 154.45,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 211.51,
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
          "id": "95ceeba29cf6e6bf99bbbe11ec839134971946fe",
          "message": "feat(cli): replace the transient spinner with a persistent progress trail (#299)\n\n* feat(cli): replace the transient spinner with a persistent progress trail\n\nThe engine now brackets each subprocess and the initial scaffold in a\nProgressStep hook (src/protostar/progress.py); the CLI renders every\nfinished step as a permanent check (or cross) above a live spinner, for\nboth init and sync. The logger-driven SpinnerHandler, the global log-level\njuggling, and the INFO logs that fed it are removed. --json passes no hook.\n\nDocs gain a real-engine init SVG (now the landing hero) and re-recorded\nheadless demo.\n\n* docs: re-record wizard demo with the progress trail\n\n* fix(cli): keep the progress trail printable on legacy-encoded streams\n\nOn Windows, a redirected stdout uses cp1252, which cannot encode the check\nand cross marks. The UnicodeEncodeError escaped the step that had just\nsucceeded, so the executor rolled back a finished scaffold. The trail now\nfalls back to +/x marks and replaces unencodable label characters, and the\nProgressStep contract states that a presenter must never raise on its own.",
          "timestamp": "2026-09-21T22:15:22-07:00",
          "tree_id": "c5c9b6a96c5770a3b0622d72043762c66e10a8f2",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/95ceeba29cf6e6bf99bbbe11ec839134971946fe"
        },
        "date": 1790054182481,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 156.99,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 212.41,
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
          "id": "1c23138b8f9ac1da94bc0e966fa08a89a10a0ca7",
          "message": "fix(cli): never crash on output a legacy-encoded stream cannot encode (#300)\n\nOn Windows a redirected stdout encodes with the locale code page (cp1252).\nGlyphs such as the diagnostic and trust-prompt warnings, the rollback and\ncompletion check marks, and the docs-link arrow raised UnicodeEncodeError\nmid-render, as did non-Latin paths in error text and Rich's own traceback\nmarker in crash reports.\n\nTwo layers, both in the CLI:\n- main() switches strict stdout/stderr to errors=\"replace\", so arbitrary\n  data and Rich internals can no longer crash output. An error handler\n  chosen explicitly (PYTHONIOENCODING) is kept.\n- ui.glyph() gives intentional symbols readable ASCII stand-ins (!, +, ->)\n  rather than \"?\"; ui.printable() is lifted out of progress_trail, which\n  still sanitizes its own labels because a write error there would roll\n  back the step's work.",
          "timestamp": "2026-09-21T22:27:50-07:00",
          "tree_id": "b3f7ddde69df5553aabdbac02828015d7f6eea77",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/1c23138b8f9ac1da94bc0e966fa08a89a10a0ca7"
        },
        "date": 1790054926883,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 130.64,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 184.98,
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
          "id": "6314d837f247660b9d57e939ea9031852593b1d1",
          "message": "docs(hero): refine lede copy and link init terminal graphic to init guide",
          "timestamp": "2026-09-21T22:39:40-07:00",
          "tree_id": "94b040157bd734bb34b7f98bb4c01871b7268006",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/6314d837f247660b9d57e939ea9031852593b1d1"
        },
        "date": 1790055723713,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 202.57,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 280.4,
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
          "id": "6314d837f247660b9d57e939ea9031852593b1d1",
          "message": "docs(hero): refine lede copy and link init terminal graphic to init guide",
          "timestamp": "2026-09-21T22:39:40-07:00",
          "tree_id": "94b040157bd734bb34b7f98bb4c01871b7268006",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/6314d837f247660b9d57e939ea9031852593b1d1"
        },
        "date": 1790055952240,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 191.81,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 259.74,
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
          "id": "9ae7b8db57cd5013cf15897d962605dfbdda7f53",
          "message": "docs(ui): wrap asciinema demos in terminal shell and add uv/brew install toggle",
          "timestamp": "2026-09-21T22:43:52-07:00",
          "tree_id": "6de257cec8a00c8e84f6d2313aeca40a4564230e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/9ae7b8db57cd5013cf15897d962605dfbdda7f53"
        },
        "date": 1790055975550,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 200.68,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 275.25,
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
          "distinct": false,
          "id": "a42abe397dd71bb8e84271d284ca33dfc0356f05",
          "message": "docs(agents): track AGENTS.md in the repository\n\nAGENTS.md held the project's architectural invariants and agent rules but\nwas excluded locally via .git/info/exclude, so it was invisible to other\ncheckouts, cloud sessions, and review. It now also records the progress\nboundary from #299 (ProgressStep, fatal-only steps, presenters never\nraise), the CLI output rules from #300 (untrusted text as Text, glyphs\nthrough ui.glyph, cp1252 tests), demo re-recording, and progress.py in\nthe layout map.",
          "timestamp": "2026-09-21T22:46:20-07:00",
          "tree_id": "80401402d1559564178467522854b68f80942958",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a42abe397dd71bb8e84271d284ca33dfc0356f05"
        },
        "date": 1790056126514,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 204.16,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 277.29,
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
          "id": "300a0b3decfb574d59b0f3729a76961842e9cd4d",
          "message": "fix(ci): point benchmark workflows and performance link to gh-pages and custom domain",
          "timestamp": "2026-09-22T10:36:46-07:00",
          "tree_id": "cae24aad2361582c46ec07bf1425644f1f851b2d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/300a0b3decfb574d59b0f3729a76961842e9cd4d"
        },
        "date": 1790098676689,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 160.58,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 223.86,
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
          "id": "5d4ca63e9f38ce9034c1cff4174b2397abb62d4c",
          "message": "fix(snapshots): freeze actionlint-py, check-jsonschema, and json5 in constraints",
          "timestamp": "2026-09-22T10:47:39-07:00",
          "tree_id": "584d7a6d635cbc10de213ff0b6c5cd60c9f9dfe4",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/5d4ca63e9f38ce9034c1cff4174b2397abb62d4c"
        },
        "date": 1790099411469,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 195.74,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 264.53,
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
          "id": "c50f8d57427642bb9db5bb8e0664d4609b9534bd",
          "message": "refactor(cli): move prompt code out of the engine (#301)\n\nThe headless-core rule says engine modules never import terminal UI\npackages, but the questionary wrappers (protostar/ui.py) and the init\nwizard (protostar/wizard.py, which builds a Rich console) lived in the\nengine package. Move them under cli/ as cli/prompts.py and cli/wizard.py,\nunchanged apart from imports: both are replaced by the Textual rebuild,\nand prompts.py is deleted whole once questionary goes.\n\nWizardSelections leaves the package's public exports; it is a CLI type.\n\ntests/test_headless_boundary.py now enforces the rule. In a fresh\ninterpreter it imports every module outside protostar.cli and fails if\nrich, questionary, prompt_toolkit, or textual was loaded, naming the\nengine module whose import first pulled it in. It replaces the narrower\nquestionary check in test_metadata.py.",
          "timestamp": "2026-09-22T13:46:25-07:00",
          "tree_id": "5ad5131a36ffc38e5a93338925c7ce18d21a6bf8",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/c50f8d57427642bb9db5bb8e0664d4609b9534bd"
        },
        "date": 1790110064427,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 203.24,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 279.37,
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
          "id": "22c5a0b11db0f0a75df7358a2dd1538beaae0723",
          "message": "feat(security): secret guard for template variables (#302)\n\n* feat(security): secret guard for template variables\n\nCustom template variables are non-secret by definition: their values\nrender into committed files, and the next change persists them in the\nproject recipe too. This guard backs that rule up before any of that\nhappens, and it lands first so no commit ever writes an unchecked value.\n\nValues are checked against gitleaks' default rules at the tag already\npinned for the scaffolded gitleaks pre-commit hook, so the guard and the\nhook agree. scripts/sync_secret_rules.py fetches that tag's config and\ntranslates it at build time into src/protostar/_secret_rules.py. Python\nreads several RE2 constructs differently, so the translator:\n\n- rewrites \\z as \\Z (Python before 3.14 rejects it)\n- expands POSIX classes such as [[:alnum:]], which Python compiles with\n  only a warning and never matches (the Airtable rule was dead this way)\n- rescopes mid-pattern flags like (?i) with Go's semantics, including\n  later alternation branches (curl-auth-header)\n\nEvery translated pattern must compile without a warning; anything else\nstops the script unless the rule is excluded with a reason. `--check`\nregenerates and compares bytes, and runs in `just bump` and the release\nworkflow. The generated module is excluded from ruff for that reason,\nand allowlisted in a new .gitleaks.toml because it quotes gitleaks' own\npatterns, some of which contain literal token prefixes.\n\nAt runtime, secret_guard ports gitleaks' detector: a rule runs only when\none of its keywords appears (which is also what keeps unrelated values\nlike a v1.0-<hex> tag from reading as a Sourcegraph token), secret\ngroups and entropy thresholds apply as in gitleaks, and allowlists keep\nonly the checks a value without a path or commit can meet. A\ngitleaks:allow marker is deliberately ignored, since it would be an\noverride. Rules compile on first use; CLI startup never loads them.\n\nVariable names that read as credentials stop a template from loading.\nValues over 1,024 characters are refused, bounding scan time.\n\nSecretDetectedError names each variable and rule, never the value. It\nexits 77 like other security violations, and ProtostarError.details()\nnow carries error-specific JSON fields, replacing the isinstance special\ncase for collision paths.\n\n* refactor(security): store secret rules compressed so scanners skip them\n\nThe generated rules module held gitleaks' patterns as text, and some of\nthat text is exactly what secret scanners look for. gitleaks flagged the\nBedrock rule's literal token prefix, and GitHub secret scanning raised\n16 alerts on the Google API key rule's allowlist, which lists publicly\nknown keys. Every scanner has its own ignore mechanism, and none of them\ntravel with the wheel, so users scanning an environment with Protostar\ninstalled would see the same alerts.\n\nThe module now stores the rule set as base64 of zlib-compressed JSON:\nno scanner can find key-shaped text in it, and .gitleaks.toml is gone.\nMetadata (the gitleaks version, source hash, license, omitted rules)\nstays readable, and `sync_secret_rules.py --dump` prints the rules.\nload_rules() decodes them on first use, in about half a millisecond.\n\nzlib output can differ between builds of the same Python, so the script\nkeeps the committed payload whenever it decodes to the same rules; that\nkeeps regeneration and `--check` stable across machines. A test scans\nevery line of the committed module with the rules themselves.",
          "timestamp": "2026-09-22T14:39:43-07:00",
          "tree_id": "3918707702d5209297d1df1aba8a11239988755e",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/22c5a0b11db0f0a75df7358a2dd1538beaae0723"
        },
        "date": 1790113258026,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 195.1,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 265.1,
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
          "id": "a13c978e5adcb157b0f670745972e108202e4a8c",
          "message": "feat(recipe)!: persist template variables and drop --bind (#303)\n\nCustom template variables had three ways in and two persistence models:\nfree-form trailing flags, interactive answers, and --bind, which stored\nan environment-variable name in the recipe and read the value at replay.\nThe paths disagreed (the wizard prompted for values the flag path then\nrefused without bindings), and any mistyped flag silently became a\ntemplate variable.\n\nThere is now one mechanism. A template's variables get values from the\nrecipe, then --var NAME=VALUE flags, then a prompt in an interactive\nterminal, and every value persists in [tool.protostar.variables]. The\nrule is that template variables are non-secret: the recipe is committed,\nand the secret guard (previous PR) checks every value, including ones\nedited into the recipe by hand, since decode_recipe runs it too.\n\nThe engine no longer prompts. TemplateBlueprint.load's variable_resolver\ncallback is gone: TemplateSource.load() acquires a template once,\n.variables reports what it needs (checking names), and .render(context)\nraises MissingTemplateVariablesError listing every missing name. The CLI\nprompts between those steps, so a remote template is fetched once. In\n--json mode, off a terminal, and in sync, the error surfaces instead;\nits details() adds missing_variables to the JSON envelope.\n\n- --var replaces trailing dynamic flags and works with --template,\n  --from, or a recorded source; unknown names and repeats are rejected\n  without echoing values\n- argparse now parses strictly, so a mistyped flag is an error\n- one BUILT_IN_VARIABLES set and one identifier-shaped VARIABLE_NAME\n  pattern replace three separate copies\n- bindings, --bind, and their orchestrator and lifecycle checks are gone\n- docs teach non-secret examples instead of DATABASE_URL\n\nBREAKING CHANGE: --bind and [tool.protostar.bindings] are removed; pass\nvalues with --var or record them under [tool.protostar.variables].\nTrailing --NAME=value flags are no longer accepted.",
          "timestamp": "2026-09-22T15:00:41-07:00",
          "tree_id": "411202bdbed1ac8c51162c408dbd230e489f32e1",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/a13c978e5adcb157b0f670745972e108202e4a8c"
        },
        "date": 1790114514771,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 203.6,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 272.84,
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
          "id": "70b419217d0fd558d37d458aa0b9bd1a799ce69a",
          "message": "docs(plan): record the TUI rebuild plan in the repository",
          "timestamp": "2026-09-22T15:17:45-07:00",
          "tree_id": "038a90635a1adc6b99f8534be2a2abc053ec391d",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/70b419217d0fd558d37d458aa0b9bd1a799ce69a"
        },
        "date": 1790115537804,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 167.44,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 235.9,
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
          "id": "7562661b02e75878e3e471d7e2cdc1618321d261",
          "message": "refactor(cli): single init draft and resolver (#304)",
          "timestamp": "2026-09-22T15:55:58-07:00",
          "tree_id": "03d3e7dce4a7afe5800aa53457c427f7353a6005",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/7562661b02e75878e3e471d7e2cdc1618321d261"
        },
        "date": 1790117824046,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 161.2,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 222.09,
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
          "id": "dd1700069fa0025051adfd76d921e2c28d1f37d7",
          "message": "feat(cli): Textual foundation and recipe editor (#305)\n\n* feat(cli): add Textual foundation and recipe editor\n\n* test(cli): stabilize recipe snapshot color environment",
          "timestamp": "2026-09-22T16:18:04-07:00",
          "tree_id": "cf7397a8bd9e9cb6810ad432ec2b3ae2a2993b91",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/dd1700069fa0025051adfd76d921e2c28d1f37d7"
        },
        "date": 1790119153617,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 211.9,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 199.73,
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
          "id": "7bcd8600fcfe7b48eef8450b88158e0b1f4346bf",
          "message": "feat(cli): variables, metadata and live plan preview (#306)\n\n* feat(cli): variables, metadata and live plan preview\n\nThe recipe editor now collects template variables and project metadata,\nand shows a live preview of the planned files beside the form.\n\n- Variable fields run the secret guard on submit or blur, never per\n  keystroke, and show the gitleaks rule on the field. Recorded values\n  pre-fill them; fields are labeled by name.\n- Metadata fields map PromptType to Input, Select, and SelectionList,\n  pre-filled from the recipe, then the auto-resolvers. Fields appear\n  only when an enabled tool or Docker reads them.\n- The preview re-plans in an exclusive, debounced worker thread and\n  lists collisions. It shares plan_tree() with --dry-run.\n- Template loads run in a worker with a loading line and inline errors,\n  so a remote alias no longer blocks the UI.\n- A flag-driven init missing variables in an interactive terminal opens\n  the variables step (edit_variables) instead of a questionary prompt.\n- cli/wizard.py is deleted; the app now runs a given screen.\n\n* test(cli): stabilize TUI continue event handling and subprocess encoding on Windows",
          "timestamp": "2026-09-22T17:06:42-07:00",
          "tree_id": "f4cce5af6e353c9dbd471cd19ea966410d2838cb",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/7bcd8600fcfe7b48eef8450b88158e0b1f4346bf"
        },
        "date": 1790122068227,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 204.57,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 197.42,
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
          "id": "fe36798b24d7f6db3c2c5a047512416da3eb5fbe",
          "message": "feat(cli): change review screen (#307)\n\n* feat(cli): change review screen\n\nBefore anything runs, init now shows what will change and settles the\ncollision and trust decisions on one Textual screen. The recipe editor\ncontinues to it, and an interactive flag-driven init opens it when a\ncollision or trust decision is open.\n\nThe review renders the first file batch (prepare_review at\nBEFORE_INITIALIZERS) as a file tree with unified diffs, and lists later\nfiles with the command that creates them instead of guessing content.\nIt takes one registry snapshot in a worker; InitDecision carries it to\nOrchestrator.execute(hook_revisions=...), so execution writes the pins\nthe review showed. A trust confirmation covers exactly the listed\ncommands. _run_engine no longer prompts: the questionary collision\nselect and trust confirm are gone.\n\n* fix(cli): normalize CRLF line endings in unified diffs",
          "timestamp": "2026-09-22T18:24:22-07:00",
          "tree_id": "32b1e17cd59dd1973d4f9bc5dffbc3f9579297f9",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/fe36798b24d7f6db3c2c5a047512416da3eb5fbe"
        },
        "date": 1790126730084,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 210.99,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 201.36,
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
          "id": "22f2947848c2e41343bd4595b49ee9e616272914",
          "message": "refactor(cli)!: remove questionary (#308)\n\nconfig --reset confirms with rich.prompt.Confirm, the wizard benchmark\nmeasures time to the recipe editor's first frame, the docs show Textual\nscreenshots of the editor and change review, and record_wizard drives the\nTextual key flow.",
          "timestamp": "2026-09-22T20:21:37-07:00",
          "tree_id": "16ec3c4f5e18d90950e3816b5b8db00843bed901",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/22f2947848c2e41343bd4595b49ee9e616272914"
        },
        "date": 1790133826603,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 207.42,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 718.05,
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
          "id": "e1a00be94fefeeaa4b0341ad396275b85c7c232c",
          "message": "perf(sync): memoize baseline decoding and balance xdist workers (#309)\n\n* perf(sync): memoize baseline decoding and balance xdist workers\n\nOne sync decoded the same owned YAML/TOML baselines hundreds of times\nthrough ruamel's pure-Python round-trip parser, and serialize_state\nre-canonicalized every baseline on each call. Memoize the decoders\n(callers receive a deep copy) and the canonicalization step.\n\nSwitch pytest-xdist from loadfile to worksteal so the slowest file no\nlonger sets the wall-clock floor.\n\nParallel suite: 57.5s -> ~14s. Serial: 100s -> 55s.\n\n* ci(test): report slowest tests and dump stacks of hung ones",
          "timestamp": "2026-09-23T10:33:15-07:00",
          "tree_id": "e3ab02aa58ac10e82f55bb514221f29686647f7a",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/e1a00be94fefeeaa4b0341ad396275b85c7c232c"
        },
        "date": 1790184921718,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 208.88,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 712.76,
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
          "id": "7093ae5ac2ef3e4df498a620943642baf04f153b",
          "message": "feat(security): confirmable secret guard and variable descriptions (#310)\n\nThe secret guard becomes a safety net instead of a hard wall:\n\n- A newly entered value that looks like a credential is held back until\n  the user confirms it isn't a secret, per variable: --allow-secret NAME,\n  or a checkbox beside the TUI field that resets when the value changes.\n- Only values that differ from the recipe are scanned, in resolve_init.\n  decode_recipe and sync no longer check recorded values.\n- Credential-shaped variable names warn instead of stopping the template.\n\nTemplates can declare [variables.NAME] description = \"...\" to explain a\nvariable; the TUI shows it under the field. Declaring an unused or\nbuilt-in variable is an error.\n\nAlso deletes TUI_REBUILD_PLAN.md: every PR in it has merged.",
          "timestamp": "2026-09-23T11:25:42-07:00",
          "tree_id": "3a4a1d7e6644d57fedc951723f8ec2b57fd4feec",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/7093ae5ac2ef3e4df498a620943642baf04f153b"
        },
        "date": 1790188077345,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 213.14,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 780.7,
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
          "id": "62b70648da5e67e98e40e3dad289d2ca0492389f",
          "message": "feat(cli): keyboard-first TUI navigation (#311)\n\n* feat(cli): keyboard-first TUI navigation\n\nArrow keys now walk every row of the recipe editor without changing a\nvalue, space and enter toggle or choose, and tab moves between controls\nwith the tool checkboxes counting as one stop. Ctrl+S continues; the\nreview answers to letters (a, m, o, t, q) and pages its diff from the\nfile tree. Each button and option shows its key, the footer is the\nlegend for moving, and F1 lists every key.\n\nEsc now asks before leaving instead of discarding the recipe; Ctrl+C\nstill quits at once.\n\n* fix(cli): leave the first row focused by Textual\n\nFocusing the template picker from on_mount could land after an early\nscroll and jump the view back to the top.\n\n* test(cli): settle before clicking a recorded-recipe tool\n\nThe editor recomposes its variable fields after mount, which can move a\nrow between a scroll and a click on slower CI runners.\n\n* test(cli): settle the editor before changing its template\n\nA template change posted while on_mount is still recomposing the\nvariable fields races the mount on slower Windows runners.",
          "timestamp": "2026-09-23T12:29:06-07:00",
          "tree_id": "3d455b4432d589d66461d1d61ac071e163f49181",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/62b70648da5e67e98e40e3dad289d2ca0492389f"
        },
        "date": 1790191874776,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 207.57,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 704.63,
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
          "id": "b4f68ead9aa3c2e4bf1528f121a3156e59889248",
          "message": "feat(cli): mission-control theme for the TUI and printed output (#312)\n\n* feat(cli): mission-control theme for the TUI and printed output\n\nMatch the TUI and every printed CLI surface to the zensical docs' dark\n\nscheme: one shared palette with cyan as the only accent, ruled panels\nand headings instead of boxes, the ❊ mark in a masthead, and a tree\ncolored by kind. The recipe editor gains vertical space with a one-line\nheadline and buttons moved under the preview.\n\n* fix(cli): let a late preview plan survive app teardown\n\nOn exit Textual removes PlanPreview's children before cancelling its\nworker, so a debounced plan finishing in that window hit NoMatches on\n'#preview-summary' and failed the run (flaky on ubuntu / py3.12). The\npreview now holds its three lines instead of querying for them.",
          "timestamp": "2026-09-23T14:35:47-07:00",
          "tree_id": "4e6fc03d5949ed9f4866eea7cba15a917fa8fc7f",
          "url": "https://github.com/JacksonFergusonDev/protostar/commit/b4f68ead9aa3c2e4bf1528f121a3156e59889248"
        },
        "date": 1790199456346,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "Protostar Headless Latency",
            "value": 156.9,
            "unit": "ms"
          },
          {
            "name": "Protostar TUI Wizard Latency",
            "value": 599.05,
            "unit": "ms"
          }
        ]
      }
    ]
  }
}