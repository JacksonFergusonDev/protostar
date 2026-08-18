window.BENCHMARK_DATA = {
  "lastUpdate": 1787027257922,
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
      }
    ]
  }
}