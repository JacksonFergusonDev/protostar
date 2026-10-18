"""The smoke test's prek cache keeps only the hooks its scaffolds name."""

import json
from pathlib import Path

from scripts import prek_cache

CONFIG = """\
repos:
  - repo: builtin
    hooks:
      - id: check-yaml
  - repo: local
    hooks:
      - id: ruff-check
        language: system
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.30.1
    hooks:
      - id: gitleaks
  - repo: https://github.com/commitizen-tools/commitizen
    rev: "v4.19.2"
    hooks:
      - id: commitizen
"""

GITLEAKS = ("https://github.com/gitleaks/gitleaks", "v8.30.1")
COMMITIZEN = ("https://github.com/commitizen-tools/commitizen", "v4.19.2")
OLD_COMMITIZEN = ("https://github.com/commitizen-tools/commitizen", "v4.19.1")


def clone(home: Path, name: str, revision: tuple[str, str]) -> Path:
    path = home / "repos" / name
    path.mkdir(parents=True)
    repo, rev = revision
    (path / ".prek-repo.json").write_text(json.dumps({"repo": repo, "rev": rev}))
    return path


def environment(home: Path, name: str, revision: tuple[str, str]) -> Path:
    path = home / "hooks" / name
    path.mkdir(parents=True)
    repo, rev = revision
    metadata = {"language": "python", "repo": {"url": repo, "rev": rev}}
    (path / ".prek-hook.json").write_text(json.dumps(metadata))
    return path


def test_revisions_are_the_remote_repositories_a_config_pins() -> None:
    assert prek_cache.revisions(CONFIG) == {GITLEAKS, COMMITIZEN}


def test_prune_removes_what_no_config_names(tmp_path: Path) -> None:
    kept = [
        clone(tmp_path, "a", GITLEAKS),
        clone(tmp_path, "b", COMMITIZEN),
        environment(tmp_path, "golang-a", GITLEAKS),
        environment(tmp_path, "python-b", COMMITIZEN),
    ]
    stale = [
        clone(tmp_path, "c", OLD_COMMITIZEN),
        environment(tmp_path, "python-c", OLD_COMMITIZEN),
    ]
    # Git writes pack files read-only, which Windows won't delete as they are.
    pack = stale[0] / ".git" / "objects" / "pack" / "pack-1.idx"
    pack.parent.mkdir(parents=True)
    pack.write_text("index")
    pack.chmod(0o444)
    unreadable = tmp_path / "hooks" / "python-d"
    unreadable.mkdir()

    removed = prek_cache.prune(tmp_path, prek_cache.revisions(CONFIG))

    assert sorted(removed) == sorted(stale)
    assert all(path.is_dir() for path in [*kept, unreadable])
    assert not any(path.exists() for path in stale)


def test_digest_names_the_revisions_not_their_order() -> None:
    assert prek_cache.digest({GITLEAKS, COMMITIZEN}) == prek_cache.digest(
        {COMMITIZEN, GITLEAKS}
    )
    assert prek_cache.digest({GITLEAKS}) != prek_cache.digest({GITLEAKS, COMMITIZEN})
