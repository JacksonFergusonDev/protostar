window.BENCHMARK_DATA = {
  "lastUpdate": 1773454190052,
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
            "name": "Protostar Initialization Latency",
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
            "name": "Protostar Initialization Latency",
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
            "name": "Protostar Initialization Latency",
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
            "name": "Protostar Initialization Latency",
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
            "name": "Protostar Initialization Latency",
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
            "name": "Protostar Initialization Latency",
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
            "name": "Protostar Initialization Latency",
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
            "name": "Protostar Initialization Latency",
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
            "name": "Protostar Initialization Latency",
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
            "name": "Protostar Initialization Latency",
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
            "name": "Protostar Initialization Latency",
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
            "name": "Protostar Initialization Latency",
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
            "name": "Protostar Initialization Latency",
            "value": 129.86,
            "unit": "ms"
          }
        ]
      }
    ]
  }
}