import sys

from protostar.config import ProtostarConfig
from protostar.metadata import resolve_auto_metadata


def test_resolve_auto_metadata_from_config(mocker):
    """Test that resolve_auto_metadata extracts values from ProtostarConfig."""
    mock_config = mocker.patch("protostar.metadata.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(
        author_name="Alice",
        author_email="alice@example.com",
        github_username="alice-dev",
        python_version="3.12",
        supported_os=["Linux"],
    )

    metadata = resolve_auto_metadata()

    assert metadata["author_name"] == "Alice"
    assert metadata["author_email"] == "alice@example.com"
    assert metadata["github_username"] == "alice-dev"
    assert metadata["minimum_python"] == "3.12"
    assert metadata["supported_os"] == ["Linux"]
    assert metadata["docker_port"] == "8000"


def test_resolve_auto_metadata_from_git(mocker):
    """Test that git config auto-resolver works when config values are absent."""
    mocker.patch(
        "protostar.metadata.ProtostarConfig.load", return_value=ProtostarConfig()
    )
    mocker.patch(
        "protostar.metadata.get_git_config",
        side_effect=lambda key: "Git User" if key == "user.name" else "git@user.com",
    )

    metadata = resolve_auto_metadata({"author_name", "author_email"})

    assert metadata["author_name"] == "Git User"
    assert metadata["author_email"] == "git@user.com"


def test_resolve_auto_metadata_defaults():
    """Test that fields fall back to their defined default values."""
    config = ProtostarConfig()
    metadata = resolve_auto_metadata(
        {"docker_port", "minimum_python", "supported_os"}, config=config
    )

    assert metadata["docker_port"] == "8000"
    assert metadata["minimum_python"] == "3.13"
    assert metadata["supported_os"] == ["MacOS", "Linux", "Windows"]


def test_resolve_auto_metadata_subset_keys():
    """Test resolving a specific subset of metadata keys."""
    config = ProtostarConfig(author_name="Bob")
    metadata = resolve_auto_metadata({"author_name"}, config=config)

    assert metadata == {"author_name": "Bob"}
    assert "docker_port" not in metadata


def test_metadata_layer_has_no_questionary_dependency():
    """Verify that metadata module does not depend on or expose questionary."""
    import protostar.metadata

    assert not hasattr(protostar.metadata, "questionary")
    assert (
        "questionary" not in sys.modules
        or "questionary" not in protostar.metadata.__dict__
    )
