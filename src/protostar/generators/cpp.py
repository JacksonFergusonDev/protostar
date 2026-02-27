import logging
from pathlib import Path

from protostar.config import ProtostarConfig

from .base import TargetGenerator

logger = logging.getLogger("protostar")


class CppClassGenerator(TargetGenerator):
    """Generates standard C++ header and implementation files."""

    @property
    def target_name(self) -> str:
        return "cpp-class"

    def execute(self, identifier: str | None, config: ProtostarConfig) -> list[Path]:
        if not identifier:
            raise ValueError("A class name must be provided for C++ scaffolding.")

        safe_name = identifier[:1].upper() + identifier[1:]
        hpp_path = Path(f"{safe_name}.hpp")
        cpp_path = Path(f"{safe_name}.cpp")

        if hpp_path.exists() or cpp_path.exists():
            raise FileExistsError(
                f"C++ class files for '{safe_name}' already exist in this directory."
            )

        hpp_content = f"""#pragma once

class {safe_name} {{
public:
    {safe_name}();
    ~{safe_name}();

private:
    // Member variables
}};
"""
        cpp_content = f"""#include "{safe_name}.hpp"

{safe_name}::{safe_name}() {{
}}

{safe_name}::~{safe_name}() {{
}}
"""
        hpp_path.write_text(hpp_content)
        cpp_path.write_text(cpp_content)

        return [hpp_path, cpp_path]


class CMakeGenerator(TargetGenerator):
    """Generates a CMakeLists.txt statically linking local C++ source files."""

    @property
    def target_name(self) -> str:
        return "cmake"

    def execute(self, identifier: str | None, config: ProtostarConfig) -> list[Path]:
        target_path = Path("CMakeLists.txt")
        if target_path.exists():
            raise FileExistsError("CMakeLists.txt already exists in this directory.")

        cpp_files = [p.name for p in Path(".").glob("*.cpp")]

        if not cpp_files:
            logger.warning(
                "No .cpp files found in the current directory. The CMake target will be empty."
            )
            source_list = "main.cpp  # WARNING: File does not exist yet"
        else:
            source_list = " ".join(cpp_files)

        project_name = identifier or "ProtostarApp"
        cmake_content = f"""cmake_minimum_required(VERSION 3.10)
project({project_name})

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

add_executable(${{PROJECT_NAME}} {source_list})
"""
        target_path.write_text(cmake_content)
        return [target_path]
