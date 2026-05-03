import urllib.error
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from scripts.update_homebrew import (
    clean_poet_resources,
    extract_sdist_info,
    generate_poet_resources,
    get_pypi_metadata,
    main,
    splice_resources,
    update_formula_url_sha,
)


def test_get_pypi_metadata_success(mocker: MockerFixture) -> None:
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"info": {"version": "0.7.0"}}'
    mock_response.__enter__.return_value = mock_response

    mocker.patch("urllib.request.urlopen", return_value=mock_response)

    result = get_pypi_metadata("protostar", "0.7.0", max_retries=1, delay=0)
    assert result == {"info": {"version": "0.7.0"}}


def test_get_pypi_metadata_timeout(mocker: MockerFixture) -> None:
    mock_error = urllib.error.HTTPError(
        "http://test.com",
        404,
        "Not Found",
        {},  # type: ignore[arg-type]
        None,
    )
    mocker.patch("urllib.request.urlopen", side_effect=mock_error)
    mocker.patch("time.sleep", return_value=None)

    with pytest.raises(TimeoutError, match="Timed out waiting"):
        get_pypi_metadata("protostar", "0.7.0", max_retries=2, delay=0)


def test_extract_sdist_info() -> None:
    mock_data = {
        "urls": [
            {"packagetype": "bdist_wheel", "url": "bad", "digests": {"sha256": "bad"}},
            {"packagetype": "sdist", "url": "good_url", "digests": {"sha256": "123"}},
        ]
    }
    url, sha = extract_sdist_info(mock_data)
    assert url == "good_url"
    assert sha == "123"


def test_extract_sdist_info_missing() -> None:
    with pytest.raises(ValueError, match="sdist information not found"):
        extract_sdist_info({"urls": [{"packagetype": "bdist_wheel"}]})


def test_update_formula_url_sha(tmp_path: Path) -> None:
    formula = tmp_path / "protostar.rb"
    formula.write_text('class Formula\n  url "old"\n  sha256 "old"\nend')

    update_formula_url_sha(formula, "new_url", "new_sha")

    content = formula.read_text()
    assert '  url "new_url"' in content
    assert '  sha256 "new_sha"' in content
    assert '"old"' not in content


def test_generate_poet_resources(mocker: MockerFixture) -> None:
    mock_result = MagicMock()
    mock_result.stdout = "poet output"
    mocker.patch("subprocess.run", return_value=mock_result)

    result = generate_poet_resources("protostar", "0.7.0")
    assert result == "poet output"


def test_clean_poet_resources() -> None:
    raw_output = """resource "protostar" do
  url "https://files.pythonhosted.org/..."
  sha256 "..."
end

resource "rich" do
  url "https://files.pythonhosted.org/..."
  sha256 "..."
end
"""
    cleaned = clean_poet_resources(raw_output, "protostar")

    assert 'resource "protostar"' not in cleaned
    assert '  resource "rich" do' in cleaned
    assert '    url "https://' in cleaned


def test_clean_poet_resources_empty() -> None:
    raw_output = 'resource "protostar" do\nend\n'
    assert clean_poet_resources(raw_output, "protostar") == ""


def test_splice_resources(tmp_path: Path) -> None:
    formula = tmp_path / "protostar.rb"
    formula.write_text("top\n# RESOURCE_BLOCK_START\nold\n# RESOURCE_BLOCK_END\nbottom")

    splice_resources(formula, "  new_resource")

    expected = (
        "top\n# RESOURCE_BLOCK_START\n  new_resource\n# RESOURCE_BLOCK_END\nbottom\n"
    )
    assert formula.read_text() == expected


def test_splice_resources_missing_sentinel(tmp_path: Path) -> None:
    formula = tmp_path / "protostar.rb"
    formula.write_text("no sentinels here")

    with pytest.raises(ValueError, match="Could not find valid RESOURCE_BLOCK"):
        splice_resources(formula, "data")


def test_main_integration(mocker: MockerFixture, tmp_path: Path) -> None:
    formula = tmp_path / "protostar.rb"
    # Added 2-space indentation to the root url/sha256 to match script logic
    formula.write_text(
        '  url "old"\n  sha256 "old"\n# RESOURCE_BLOCK_START\n# RESOURCE_BLOCK_END'
    )

    mocker.patch(
        "sys.argv",
        ["script_name", "--version", "0.7.0", "--formula-path", str(formula)],
    )

    mocker.patch(
        "scripts.update_homebrew.get_pypi_metadata",
        return_value={
            "urls": [
                {
                    "packagetype": "sdist",
                    "url": "new_url",
                    "digests": {"sha256": "new_sha"},
                }
            ]
        },
    )

    mocker.patch(
        "scripts.update_homebrew.generate_poet_resources",
        return_value='resource "dep" do\n  url "foo"\nend',
    )

    main()

    content = formula.read_text()
    # These should now pass since the regex found its 2-space indented targets
    assert '  url "new_url"' in content
    assert '  sha256 "new_sha"' in content
    assert '  resource "dep" do' in content
    assert '    url "foo"' in content
