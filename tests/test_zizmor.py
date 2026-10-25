"""zizmor reaches enabled runners and never silently adopts existing files."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

from protostar.config import UserConfig
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
        assert "uv run zizmor --offline ." in contents["justfile"]
    if ci:
        assert "uv run zizmor --format=github ." in contents[".github/workflows/ci.yml"]
    if hooks:
        hook_config = contents[".pre-commit-config.yaml"]
        assert "entry: uv run zizmor --offline --no-progress" in hook_config
    assert {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    } == before


def test_existing_disabled_runners_stay_untouched(tmp_path, monkeypatch):
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


@pytest.mark.integration
@pytest.mark.parametrize("python", ["3.13", "3.14"])
def test_generated_workflows_pass_zizmor(tmp_path, real_tool_env, python):
    # The zizmor beside this interpreter: the locked one on pull requests, and the
    # newest release in nightly's latest-dependencies job, which scaffolds install.
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
