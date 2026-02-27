import pytest

from protostar.modules.lang_layer import (
    generate_circuitpython,
    generate_cmake,
    generate_cpp_class,
    generate_latex_boilerplate,
    generate_pio,
)


def test_generate_latex_boilerplate_science_preset(mocker):
    """Test LaTeX generator cascades science preamble macros correctly."""
    mock_write = mocker.patch("protostar.modules.lang_layer.Path.write_text")
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)
    mocker.patch("protostar.modules.lang_layer.Path.read_text", return_value="*.aux")

    out_path = generate_latex_boilerplate("report.tex", preset="science")

    assert out_path.name == "report.tex"
    mock_write.assert_called_once()

    content = mock_write.call_args[0][0]
    assert "\\usepackage{physics}" in content
    assert "\\usepackage{siunitx}" in content
    assert "\\usepackage[backend=biber" not in content  # Belongs to academic


def test_generate_latex_aborts_on_existing_file(mocker):
    """Test LaTeX generation halts safely if the target file exists."""
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=True)

    with pytest.raises(FileExistsError, match="Target file already exists"):
        generate_latex_boilerplate("main.tex", preset="minimal")


def test_generate_cpp_class_pascal_casing(mocker):
    """Test C++ class scaffolding enforces PascalCase and drops correct files."""
    mock_write = mocker.patch("protostar.modules.lang_layer.Path.write_text")
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    paths = generate_cpp_class("dataPipeline")  # Lowercase input

    assert len(paths) == 2
    assert paths[0].name == "DataPipeline.hpp"
    assert paths[1].name == "DataPipeline.cpp"

    hpp_content = mock_write.call_args_list[0][0][0]
    assert "#pragma once" in hpp_content
    assert "class DataPipeline {" in hpp_content


def test_generate_cmake_static_globbing(mocker):
    """Test CMake generation explicitly enumerates local .cpp files to avoid cache issues."""
    mock_write = mocker.patch("protostar.modules.lang_layer.Path.write_text")

    # Mock exists check for CMakeLists.txt
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    # Mock local .cpp files
    mock_main = mocker.Mock()
    mock_main.name = "main.cpp"
    mock_engine = mocker.Mock()
    mock_engine.name = "Engine.cpp"

    mocker.patch(
        "protostar.modules.lang_layer.Path.glob", return_value=[mock_main, mock_engine]
    )

    generate_cmake("AstroEngine")

    content = mock_write.call_args[0][0]
    assert "project(AstroEngine)" in content
    assert "set(CMAKE_CXX_STANDARD 17)" in content
    assert "add_executable(${PROJECT_NAME} main.cpp Engine.cpp)" in content


def test_generate_pio_inference(mocker):
    """Test PlatformIO generator maps common board targets to standard platforms."""
    mock_write = mocker.patch("protostar.modules.lang_layer.Path.write_text")
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    # Test ESP32 inference
    generate_pio("esp32dev")
    content = mock_write.call_args[0][0]
    assert "platform = espressif32" in content
    assert "board = esp32dev" in content


def test_generate_circuitpython(mocker):
    """Test CircuitPython generator drops non-blocking loop and LSP config."""
    mock_write = mocker.patch("protostar.modules.lang_layer.Path.write_text")
    mocker.patch("protostar.modules.lang_layer.Path.exists", return_value=False)

    paths = generate_circuitpython()

    assert len(paths) == 2
    assert paths[0].name == "code.py"
    assert paths[1].name == ".pyrightconfig.json"

    # Verify state machine architecture
    code_content = mock_write.call_args_list[0][0][0]
    assert "time.monotonic()" in code_content
    assert "time.sleep(0.01)" in code_content

    # Verify LSP false-positive suppression
    pyright_content = mock_write.call_args_list[1][0][0]
    assert '"reportMissingImports": false' in pyright_content
