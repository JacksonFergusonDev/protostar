"""zizmor reaches enabled runners and never silently adopts existing files."""

import io
import re
import subprocess
import sys
from pathlib import Path

import pytest
from rich.console import Console

from protostar.cli import ui
from protostar.config import UserConfig
from protostar.manifest import DiagnosticPhase, Severity
from protostar.modules import (
    BootstrapModule,
    CIModule,
    JustModule,
    PreCommitModule,
    PrekModule,
    ReleaseModule,
    ZizmorModule,
)
from protostar.orchestrator import Orchestrator
from protostar.preparation import prepare_review
from protostar.yaml_ast import decode_yaml_baseline


@pytest.mark.parametrize("just", [False, True])
@pytest.mark.parametrize("ci", [False, True])
@pytest.mark.parametrize("hooks", [None, PreCommitModule, PrekModule])
def test_checks_reach_only_enabled_runners(tmp_path, monkeypatch, just, ci, hooks):
    monkeypatch.chdir(tmp_path)
    # Put zizmor first: checking runners must wait until every module builds.
    modules: list[BootstrapModule] = [ZizmorModule()]
    if just:
        modules.append(JustModule())
    if ci:
        modules.append(CIModule())
    if hooks:
        modules.append(hooks())
    config = UserConfig()
    before = {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    manifest = Orchestrator(modules, config).plan(check_executables=False)
    review = prepare_review(manifest, config)
    contents = {edit.path: edit.after.decode() for edit in review.edits if edit.after}
    assert "zizmor" in manifest.dependencies.dev_dependencies
    assert ("justfile" in contents) == just
    assert (".github/workflows/ci.yml" in contents) == ci
    assert (".pre-commit-config.yaml" in contents) == bool(hooks)
    if just:
        assert "uv run zizmor ." in contents["justfile"]
    if ci:
        assert "uv run zizmor --format=github ." in contents[".github/workflows/ci.yml"]
    if hooks:
        assert (
            "entry: uv run zizmor --no-progress" in contents[".pre-commit-config.yaml"]
        )
    warnings = [
        event for event in manifest.diagnostics if event.phase is DiagnosticPhase.ZIZMOR
    ]
    assert bool(warnings) == (not just and not ci and not hooks)
    if warnings:
        assert warnings[0].severity is Severity.WARNING
        assert "uv run zizmor ." in warnings[0].message
    assert {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    } == before


def test_existing_disabled_runners_stay_untouched_and_warn(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    files = {
        "justfile": "lint:\n    echo custom\n",
        ".pre-commit-config.yaml": "repos: []\n",
        ".github/workflows/ci.yml": "name: Custom CI\n",
    }
    for path, content in files.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    config = UserConfig()
    manifest = Orchestrator([ZizmorModule(), ReleaseModule()], config).plan(
        check_executables=False
    )
    review = prepare_review(manifest, config)
    assert not (set(files) & {edit.path for edit in review.edits})
    assert any(event.phase is DiagnosticPhase.ZIZMOR for event in manifest.diagnostics)
    for path, content in files.items():
        assert (tmp_path / path).read_text() == content


@pytest.mark.parametrize(
    "path",
    [
        ".github/workflows/ci.yml",
        "action.yaml",
        "actions/build/action.yml",
        ".github/dependabot.yml",
        ".pre-commit-config.yaml",
    ],
)
def test_hook_checks_supported_inputs(path):
    from protostar.manifest import EnvironmentManifest

    manifest = EnvironmentManifest()
    ZizmorModule().build(manifest)
    document = decode_yaml_baseline(
        "hooks:\n" + manifest.tooling.pre_commit_local_hooks[0]
    )
    assert isinstance(document, dict)
    hooks = document["hooks"]
    assert isinstance(hooks, list)
    hook = hooks[0]
    assert isinstance(hook, dict)
    pattern = hook["files"]
    assert isinstance(pattern, str)
    assert re.search(pattern, path)
    assert not re.search(pattern, "settings.yaml")


def test_runner_warning_prints_on_strict_cp1252(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manifest = Orchestrator([ZizmorModule()], UserConfig()).plan(
        check_executables=False
    )
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    console = Console(file=stream, force_terminal=False, color_system=None)
    monkeypatch.setattr(ui, "console", console)
    console.print(ui.diagnostics_report(manifest.diagnostics))
    stream.flush()
    assert "no runner invokes it" in stream.buffer.getvalue().decode("cp1252")


@pytest.mark.integration
@pytest.mark.parametrize("python", ["3.13", "3.14"])
def test_generated_workflows_pass_zizmor(tmp_path, real_tool_env, python):
    from protostar.manifest import EnvironmentManifest
    from protostar.modules import MarkdownLintModule
    from protostar.workflows import (
        CIFlag,
        CIWorkflowSpec,
        TargetOS,
        generate_ci_workflow,
        generate_pre_commit_config,
        generate_release_workflow,
    )

    manifest = EnvironmentManifest()
    for module in (CIModule(), ReleaseModule(), MarkdownLintModule(), ZizmorModule()):
        module.build(manifest)
    workflows = tmp_path / ".github/workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(
        generate_ci_workflow(
            CIWorkflowSpec(
                [TargetOS.LINUX],
                python,
                {CIFlag.PYTEST, CIFlag.CODECOV},
                manifest.tooling.ci_steps,
            )
        )
    )
    (workflows / "release.yml").write_text(generate_release_workflow())
    from protostar._fallbacks import DEFAULT_REVISIONS
    from protostar.registry import RemoteHook

    hooks = generate_pre_commit_config(
        local_hooks=manifest.tooling.pre_commit_local_hooks,
        remote_hooks=manifest.tooling.pre_commit_hooks,
    )
    for hook in RemoteHook:
        hooks = hooks.replace(hook.placeholder, DEFAULT_REVISIONS[hook.value])
    (tmp_path / ".pre-commit-config.yaml").write_text(hooks)
    executable = Path(sys.executable).parent / (
        "zizmor.exe" if sys.platform == "win32" else "zizmor"
    )
    result = subprocess.run(
        [str(executable), "--offline", "--no-progress", "."],
        cwd=tmp_path,
        env=real_tool_env(),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
