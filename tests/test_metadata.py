from protostar.config import ProtostarConfig
from protostar.metadata import resolve_metadata


def test_resolve_metadata_flags_mode(mocker):
    # Mock auto_resolver behavior
    mock_config = mocker.patch("protostar.metadata.ProtostarConfig.load")
    mock_config.return_value = ProtostarConfig(
        author_name="Alice", author_email="alice@example.com"
    )
    mocker.patch("protostar.system.execute_subprocess", return_value="Alice")

    mock_text = mocker.patch("protostar.metadata.questionary.text")
    mock_text.return_value.ask.return_value = "Alice"

    required = {"author_name"}
    optional = {"author_email"}

    metadata = resolve_metadata(required, optional, tui_mode=False)

    assert metadata["author_name"] == "Alice"
    assert metadata["author_email"] == "alice@example.com"
