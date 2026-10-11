import subprocess

import pytest

from scripts import compare_text_merge


def completed(code: int) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], code, stdout="merged\n", stderr="boom")


@pytest.mark.parametrize(("code", "merged"), [(0, "merged\n"), (1, None), (127, None)])
def test_git_merge_reads_clean_merges_and_conflict_counts(
    monkeypatch, tmp_path, code, merged
):
    monkeypatch.setattr(subprocess, "run", lambda *_, **__: completed(code))
    assert compare_text_merge.git_merge(tmp_path, "a\n", "b\n", "c\n") == merged


@pytest.mark.parametrize("code", [255, -9])
def test_a_git_error_stops_the_comparison_instead_of_counting_as_a_conflict(
    monkeypatch, tmp_path, code
):
    monkeypatch.setattr(subprocess, "run", lambda *_, **__: completed(code))
    with pytest.raises(SystemExit, match="git merge-file failed: boom"):
        compare_text_merge.git_merge(tmp_path, "a\n", "b\n", "c\n")
