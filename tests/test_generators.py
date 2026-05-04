import pytest

from protostar.config import ProtostarConfig
from protostar.generators.embedded import CircuitPythonGenerator, PlatformIOGenerator


@pytest.fixture
def mock_config():
    """Provides a default config instance for generator execution."""
    return ProtostarConfig()


def test_pio_generator_inference(mocker, mock_config):
    """Test PlatformIO generator maps common board targets to standard platforms."""
    mock_write = mocker.patch("protostar.generators.embedded.Path.write_text")
    mocker.patch("protostar.generators.embedded.Path.exists", return_value=False)

    generator = PlatformIOGenerator()
    generator.execute("esp32dev", mock_config)

    content = mock_write.call_args[0][0]
    assert "platform = espressif32" in content
    assert "board = esp32dev" in content


def test_circuitpython_generator(mocker, mock_config):
    """Test CircuitPython generator drops non-blocking loop and LSP config."""
    mock_write = mocker.patch("protostar.generators.embedded.Path.write_text")
    mocker.patch("protostar.generators.embedded.Path.exists", return_value=False)

    generator = CircuitPythonGenerator()
    paths = generator.execute(None, mock_config)

    assert len(paths) == 2
    assert paths[0].name == "code.py"
    assert paths[1].name == ".pyrightconfig.json"

    code_content = mock_write.call_args_list[0][0][0]
    assert "time.monotonic()" in code_content
    assert "time.sleep(0.01)" in code_content


def test_circuitpython_generator_aborts_on_existing_file(mocker, mock_config):
    """Test CircuitPython generator halts safely if code.py exists."""
    mocker.patch("protostar.generators.embedded.Path.exists", return_value=True)

    generator = CircuitPythonGenerator()
    with pytest.raises(FileExistsError, match=r"code\.py already exists"):
        generator.execute(None, mock_config)


def test_pio_generator_aborts_on_missing_identifier(mock_config):
    """Test PlatformIO generator rejects empty identifiers."""
    generator = PlatformIOGenerator()
    with pytest.raises(ValueError, match="A board target must be specified"):
        generator.execute("", mock_config)


def test_pio_generator_aborts_on_existing_file(mocker, mock_config):
    """Test PlatformIO generator halts safely if platformio.ini exists."""
    mocker.patch("protostar.generators.embedded.Path.exists", return_value=True)

    generator = PlatformIOGenerator()
    with pytest.raises(FileExistsError, match=r"platformio\.ini already exists"):
        generator.execute("esp32dev", mock_config)


def test_pio_generator_pico_inference(mocker, mock_config):
    """Test PlatformIO generator correctly maps RP2040/Pico targets."""
    mock_write = mocker.patch("protostar.generators.embedded.Path.write_text")
    mocker.patch("protostar.generators.embedded.Path.exists", return_value=False)

    generator = PlatformIOGenerator()
    generator.execute("pico", mock_config)

    content = mock_write.call_args[0][0]
    assert "platform = raspberrypi" in content
    assert "board = pico" in content
