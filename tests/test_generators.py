import pytest

from protostar.config import ProtostarConfig
from protostar.generators.cpp import CMakeGenerator, CppClassGenerator
from protostar.generators.embedded import CircuitPythonGenerator, PlatformIOGenerator
from protostar.generators.latex import LatexGenerator


@pytest.fixture
def mock_config():
    """Provides a default config instance for generator execution."""
    return ProtostarConfig()


def test_latex_generator_science_preset(mocker, mock_config):
    """Test LaTeX generator cascades science preamble macros correctly."""
    mock_write = mocker.patch("protostar.generators.latex.Path.write_text")
    mocker.patch("protostar.generators.latex.Path.exists", return_value=False)
    mocker.patch("protostar.generators.latex.Path.read_text", return_value="*.aux")

    # Override preset for this test
    mock_config.presets["latex"] = "science"

    generator = LatexGenerator()
    out_paths = generator.execute("report.tex", mock_config)

    assert out_paths[0].name == "report.tex"
    mock_write.assert_called_once()

    content = mock_write.call_args[0][0]
    assert "\\usepackage{physics}" in content
    assert "\\usepackage{siunitx}" in content
    assert "\\usepackage[backend=biber" not in content


def test_latex_generator_aborts_on_existing_file(mocker, mock_config):
    """Test LaTeX generation halts safely if the target file exists."""
    mocker.patch("protostar.generators.latex.Path.exists", return_value=True)

    generator = LatexGenerator()
    with pytest.raises(FileExistsError, match="Target file already exists"):
        generator.execute("main.tex", mock_config)


def test_cpp_class_generator_pascal_casing(mocker, mock_config):
    """Test C++ class scaffolding enforces PascalCase and drops correct files."""
    mock_write = mocker.patch("protostar.generators.cpp.Path.write_text")
    mocker.patch("protostar.generators.cpp.Path.exists", return_value=False)

    generator = CppClassGenerator()
    paths = generator.execute("dataPipeline", mock_config)

    assert len(paths) == 2
    assert paths[0].name == "DataPipeline.hpp"
    assert paths[1].name == "DataPipeline.cpp"

    hpp_content = mock_write.call_args_list[0][0][0]
    assert "#pragma once" in hpp_content
    assert "class DataPipeline {" in hpp_content


def test_cmake_generator_static_globbing(mocker, mock_config):
    """Test CMake generation explicitly enumerates local .cpp files to avoid cache issues."""
    mock_write = mocker.patch("protostar.generators.cpp.Path.write_text")
    mocker.patch("protostar.generators.cpp.Path.exists", return_value=False)

    mock_main = mocker.Mock()
    mock_main.name = "main.cpp"
    mock_engine = mocker.Mock()
    mock_engine.name = "Engine.cpp"
    mocker.patch(
        "protostar.generators.cpp.Path.glob", return_value=[mock_main, mock_engine]
    )

    generator = CMakeGenerator()
    generator.execute("AstroEngine", mock_config)

    content = mock_write.call_args[0][0]
    assert "project(AstroEngine)" in content
    assert "add_executable(${PROJECT_NAME} main.cpp Engine.cpp)" in content


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
