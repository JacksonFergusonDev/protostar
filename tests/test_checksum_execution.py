"""Exact-byte generated-file and append-region acceptance tests."""

from hashlib import sha256
from pathlib import Path

import pytest

from protostar.appends import append_marker_blocks
from protostar.checksum import checksum_gate
from protostar.config import UserConfig
from protostar.errors import ConfigurationError
from protostar.executor import SystemExecutor
from protostar.intent import AppendContribution
from protostar.manifest import CollisionStrategy, EnvironmentManifest
from protostar.sync_state import deserialize_state

ARTIFACTS = [
    ".github/renovate.json",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    "Dockerfile",
    "justfile",
]


def run(mocker, setup):
    intent = EnvironmentManifest()
    intent.collision_strategy = CollisionStrategy.MERGE
    executor = SystemExecutor(intent, UserConfig())
    mocker.patch.object(executor, "_check_ide_extensions")
    setup(executor)
    executor.execute()
    return executor


@pytest.mark.parametrize("path", ARTIFACTS)
def test_generated_lifecycle(tmp_path, monkeypatch, mocker, path):
    monkeypatch.chdir(tmp_path)
    target = Path(path)

    def apply(value):
        return run(
            mocker,
            lambda e: mocker.patch.object(
                e,
                "_write_ci_workflow",
                side_effect=lambda: e._write_generated(target, value),
            ),
        )

    apply("v1\r\n")
    state = Path(".protostar.lock.toml")
    initial = state.read_bytes()
    assert (
        deserialize_state(initial.decode()).files[0].digest
        == sha256(target.read_bytes()).hexdigest()
    )
    assert not apply("v1\r\n").journal.touched_paths
    apply("v2\n")
    assert target.read_bytes() == b"v2\n"
    baseline = state.read_bytes()
    target.write_bytes(b"local\r\n")
    assert not apply("v2\n").diagnostics
    conflict = apply("v3\n")
    assert conflict.diagnostics[0].conflict.location.file == path
    assert target.read_bytes() == b"local\r\n"
    assert state.read_bytes() == baseline
    target.write_bytes(b"v3\n")
    converged = apply("v3\n")
    assert target.as_posix() not in converged.journal.touched_paths
    assert (
        deserialize_state(state.read_text()).files[0].digest
        == sha256(b"v3\n").hexdigest()
    )
    target.unlink()
    assert not apply("v3\n").journal.touched_paths
    assert apply("v4\n").diagnostics
    assert not target.exists()
    state.unlink()
    target.write_bytes(b"v4\n")
    apply("v4\n")
    assert not deserialize_state(state.read_text()).files
    target.write_bytes(b"// commented JSONC\n{}")
    assert apply("v5\n").diagnostics
    assert target.read_bytes() == b"// commented JSONC\n{}"


@pytest.mark.parametrize("suffix", [".py", ".md", ".css", ".js"])
def test_region_lifecycle_and_surrounding_bytes(suffix):
    path = Path("file" + suffix)
    first = append_marker_blocks(
        "prefix\r\n", [AppendContribution("test:id", "v1")], path
    )
    original = first.content + "suffix\r\n"
    changed = append_marker_blocks(
        original, [AppendContribution("test:id", "v2")], path, baselines=first.digests
    )
    assert changed.content.startswith("prefix\r\n")
    assert changed.content.endswith("suffix\r\n")
    assert "v2" in changed.content
    assert "v1" not in changed.content
    edited = changed.content.replace("v2", "local")
    repeat = append_marker_blocks(
        edited, [AppendContribution("test:id", "v2")], path, baselines=changed.digests
    )
    assert repeat.content == edited
    assert not repeat.conflicts
    conflict = append_marker_blocks(
        edited, [AppendContribution("test:id", "v3")], path, baselines=changed.digests
    )
    assert conflict.content == edited
    assert conflict.conflicts == ("test:id",)
    assert conflict.digests == changed.digests
    converged = append_marker_blocks(
        changed.content.replace("v2", "v3"),
        [AppendContribution("test:id", "v3")],
        path,
        baselines=changed.digests,
    )
    assert converged.digests != changed.digests
    deleted = append_marker_blocks(
        "prefix\r\nsuffix\r\n",
        [AppendContribution("test:id", "v3")],
        path,
        baselines=converged.digests,
    )
    assert deleted.content == "prefix\r\nsuffix\r\n"
    assert not deleted.conflicts
    unowned = append_marker_blocks(
        first.content, [AppendContribution("test:id", "v2")], path
    )
    assert not unowned.digests
    assert unowned.conflicts
    restored = append_marker_blocks(
        edited,
        [AppendContribution("test:id", "v3")],
        path,
        overwrite=True,
        baselines=changed.digests,
    )
    assert "v3" in restored.content


def test_seed_and_deleted_region_file(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)

    def setup(e):
        e.manifest.filesystem.add_file_injection("seed.py", "invalid Python seed")
        e.manifest.filesystem.add_region(".envrc", "v1", identity="test:old")

    run(mocker, setup)
    Path("seed.py").unlink()
    Path(".envrc").unlink()

    def revision(e):
        setup(e)
        e.manifest.filesystem.add_file_injection("new.py", "new")
        e.manifest.filesystem.add_region(".envrc", "v2", identity="test:new")

    run(mocker, revision)
    assert not Path("seed.py").exists()
    assert not Path(".envrc").exists()
    assert Path("new.py").read_text() == "new"


def test_generated_and_regions_rollback(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)

    def setup(e):
        e.manifest.tooling.wants_just = True
        e.manifest.filesystem.add_region(".envrc", "v1", identity="test:region")

    run(mocker, setup)
    paths = [Path("justfile"), Path(".envrc"), Path(".protostar.lock.toml")]
    for path in paths:
        path.chmod(0o640)
    originals = {p: (p.read_bytes(), p.stat().st_mode) for p in paths}

    def revision(e):
        e.manifest.filesystem.add_region(".envrc", "v2", identity="test:region")
        mocker.patch.object(
            e,
            "_write_justfile",
            side_effect=lambda: e._write_generated(Path("justfile"), "changed"),
        )
        mocker.patch.object(
            e, "_write_state", side_effect=ConfigurationError("failure")
        )

    with pytest.raises(ConfigurationError):
        run(mocker, revision)
    assert {p: (p.read_bytes(), p.stat().st_mode) for p in paths} == originals


@pytest.mark.parametrize(
    ("local", "base", "remote", "write", "conflict"),
    [
        (None, None, b"a", True, False),
        (b"a", None, b"a", False, False),
        (b"b", None, b"a", False, True),
        (None, b"a", b"a", False, False),
        (None, b"a", b"b", False, True),
    ],
)
def test_gate_absence(local, base, remote, write, conflict):
    result = checksum_gate(local, remote, sha256(base).hexdigest() if base else None)
    assert (result.write, result.conflict) == (write, conflict)


def test_real_producer_wiring_and_noop(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    mocker.patch("protostar.executor.generate_ci_workflow", return_value="ci v1\n")
    mocker.patch(
        "protostar.executor.generate_release_workflow", return_value="release v1\n"
    )
    mocker.patch("protostar.executor.generate_justfile", return_value="just v1\n")
    mocker.patch("protostar.executor.generate_dockerfile", return_value="docker v1\n")

    def setup(e):
        e.manifest.tooling.wants_ci = True
        e.manifest.tooling.wants_release = True
        e.manifest.tooling.wants_just = True
        e.docker = True
        e.manifest.filesystem.add_file_injection(
            ".github/renovate.json", '{"extends": []}\n'
        )
        e.manifest.filesystem.add_region(".envrc", "v1", identity="test:region")

    run(mocker, setup)
    state = deserialize_state(Path(".protostar.lock.toml").read_text())
    assert {r.path for r in state.files if r.digest is not None} == set(ARTIFACTS)
    for record in state.files:
        if record.digest:
            assert record.digest == sha256(Path(record.path).read_bytes()).hexdigest()
    original = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert not run(mocker, setup).journal.touched_paths
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == original
    mocker.patch("protostar.executor.generate_ci_workflow", return_value="ci v2\n")
    run(mocker, setup)
    assert Path(".github/workflows/ci.yml").read_text() == "ci v2\n"


@pytest.mark.parametrize(
    "alternate", ["renovate.json", ".renovaterc.json5", ".github/renovate.json5"]
)
def test_renovate_alternative_preserved(tmp_path, monkeypatch, mocker, alternate):
    monkeypatch.chdir(tmp_path)
    target = Path(alternate)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"// comments\n{}")

    def setup(e):
        e.manifest.filesystem.add_file_injection(".github/renovate.json", "{}")

    assert run(mocker, setup).diagnostics[0].conflict
    assert target.read_bytes() == b"// comments\n{}"
    assert not Path(".github/renovate.json").exists()


@pytest.mark.parametrize("content", ["{broken", "[]"])
def test_invalid_generated_renovate_rolls_back(tmp_path, monkeypatch, mocker, content):
    monkeypatch.chdir(tmp_path)

    def setup(e):
        e.manifest.filesystem.add_file_injection("seed.py", "seed")
        e.manifest.filesystem.add_file_injection(".github/renovate.json", content)

    with pytest.raises(ConfigurationError):
        run(mocker, setup)
    assert not Path("seed.py").exists()
    assert not Path(".protostar.lock.toml").exists()


def test_edited_dockerfile_still_appends_ignore_patterns(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    Path("Dockerfile").write_bytes(b"user docker\r\n")
    Path(".dockerignore").write_text("# custom\nmy-pattern\n")

    def setup(e):
        e.docker = True
        e.manifest.filesystem.vcs_ignores.add("new-pattern")

    run(mocker, setup)
    assert Path("Dockerfile").read_bytes() == b"user docker\r\n"
    assert Path(".dockerignore").read_text().startswith("# custom\nmy-pattern\n")
    assert "new-pattern" in Path(".dockerignore").read_text()


@pytest.mark.parametrize(
    "content",
    ["# --- Protostar Region: nested ---", "# --- End Protostar Region: test:id ---"],
)
def test_desired_region_cannot_inject_boundaries(content):
    with pytest.raises(ConfigurationError):
        append_marker_blocks("", [AppendContribution("test:id", content)], Path("x.py"))


def test_generated_justfile_with_regions(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    mocker.patch("protostar.executor.generate_justfile", return_value="base v1\n")

    def setup(value):
        def configure(e):
            e.manifest.tooling.wants_just = True
            e.manifest.filesystem.add_region(
                "justfile", value, identity="template:recipes"
            )

        return configure

    run(mocker, setup("recipe v1"))
    assert not run(mocker, setup("recipe v1")).journal.touched_paths
    target = Path("justfile")
    target.write_bytes(target.read_bytes().replace(b"base v1", b"user base"))
    run(mocker, setup("recipe v2"))
    assert "user base" in target.read_text()
    assert "recipe v2" in target.read_text()
    state = deserialize_state(Path(".protostar.lock.toml").read_text())
    record = next(r for r in state.files if r.path == "justfile")
    assert record.regions
    assert record.digest != sha256(target.read_bytes()).hexdigest()
    region = append_marker_blocks(
        "base v1\n", [AppendContribution("template:recipes", "recipe v2")], target
    )
    assert record.regions[0].digest == region.digests["template:recipes"]
    target.unlink()
    run(mocker, setup("recipe v3"))
    assert not target.exists()


def test_unowned_generated_file_can_manage_new_region(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    Path("justfile").write_text("user recipes\n")

    def setup(e):
        e.manifest.tooling.wants_just = True
        e.manifest.filesystem.add_region(
            "justfile", "managed recipe", identity="template:recipes"
        )

    run(mocker, setup)
    original = Path("justfile").read_bytes()
    run(mocker, setup)
    assert Path("justfile").read_bytes() == original
    record = deserialize_state(Path(".protostar.lock.toml").read_text()).files[0]
    assert record.digest is None
    assert record.regions
    Path("justfile").unlink()
    run(mocker, setup)
    assert not Path("justfile").exists()


def test_generated_region_omission_never_prunes(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    mocker.patch("protostar.executor.generate_justfile", return_value="base\n")

    def setup(e):
        e.manifest.tooling.wants_just = True
        e.manifest.filesystem.add_region("justfile", "keep", identity="test:omitted")

    run(mocker, setup)
    original = Path("justfile").read_bytes()
    baseline = Path(".protostar.lock.toml").read_bytes()
    mocker.patch("protostar.executor.generate_justfile", return_value="changed base\n")
    run(mocker, lambda e: setattr(e.manifest.tooling, "wants_just", True))
    assert Path("justfile").read_bytes() == original
    assert Path(".protostar.lock.toml").read_bytes() == baseline
