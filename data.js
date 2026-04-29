window.BENCHMARK_DATA = {
  "lastUpdate": 1777494057369,
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
      }
    ]
  }
}