import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

from .base import BootstrapModule

logger = logging.getLogger("protostar")


class PythonModule(BootstrapModule):
    """Configures a modern Python environment using uv."""

    @property
    def name(self) -> str:
        return "Python"

    def pre_flight(self) -> None:
        """Ensures 'uv' is installed and accessible."""
        if not shutil.which("uv"):
            raise RuntimeError(
                "Missing dependency: 'uv' is required for Python scaffolding. "
                "Install it via `curl -LsSf https://astral.sh/uv/install.sh | sh`."
            )

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Queues uv initialization and ignores virtual environment artifacts."""
        logger.debug("Building Python language layer.")

        artifacts = [
            ".venv/",
            "__pycache__/",
            "*.ipynb_checkpoints",
            ".ruff_cache/",
            ".mypy_cache/",
        ]
        for artifact in artifacts:
            manifest.add_vcs_ignore(artifact)
            manifest.add_workspace_hide(artifact)

        if not Path("pyproject.toml").exists():
            manifest.add_system_task(["uv", "init", "--no-workspace"])


class RustModule(BootstrapModule):
    """Configures a Rust environment using Cargo."""

    @property
    def name(self) -> str:
        return "Rust"

    def pre_flight(self) -> None:
        """Ensures 'cargo' is installed and accessible."""
        if not shutil.which("cargo"):
            raise RuntimeError(
                "Missing dependency: 'cargo' is required for Rust scaffolding. "
                "Install it via `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`."
            )

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Queues cargo initialization and ignores target artifacts."""
        logger.debug("Building Rust language layer.")
        manifest.add_vcs_ignore("target/")
        manifest.add_workspace_hide("target/")

        if not Path("Cargo.toml").exists():
            manifest.add_system_task(["cargo", "init"])


class NodeModule(BootstrapModule):
    """Configures a Node.js/TypeScript environment."""

    def __init__(self, package_manager: str = "npm"):
        self.package_manager = package_manager

    @property
    def name(self) -> str:
        return f"Node ({self.package_manager})"

    def pre_flight(self) -> None:
        """Ensures the selected package manager is available."""
        if not shutil.which(self.package_manager):
            raise RuntimeError(
                f"Missing dependency: '{self.package_manager}' is required. "
                "Please install Node.js or the requested package manager."
            )

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Queues package initialization and ignores node_modules."""
        logger.debug(f"Building Node language layer using {self.package_manager}.")

        artifacts = ["node_modules/", "dist/", ".next/"]
        for artifact in artifacts:
            manifest.add_vcs_ignore(artifact)
            manifest.add_workspace_hide(artifact)

        if not Path("package.json").exists():
            cmd = [self.package_manager, "init"]
            if self.package_manager == "npm":
                cmd.append("-y")
            manifest.add_system_task(cmd)


class CppModule(BootstrapModule):
    """Configures a C/C++ environment footprint."""

    @property
    def name(self) -> str:
        return "C/C++"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Ignores standard C/C++ build outputs and IDE command caches."""
        logger.debug("Building C/C++ language layer.")

        artifacts = ["build/", "*.o", "*.out", ".cache/", "compile_commands.json"]
        for artifact in artifacts:
            manifest.add_vcs_ignore(artifact)
            manifest.add_workspace_hide(artifact)


class LatexModule(BootstrapModule):
    """Configures a LaTeX environment footprint."""

    @property
    def name(self) -> str:
        return "LaTeX"

    def build(self, manifest: "EnvironmentManifest") -> None:
        """Ignores LaTeX compiler auxiliary and log files."""
        logger.debug("Building LaTeX language layer.")

        artifacts = [
            "*.aux",
            "*.fdb_latexmk",
            "*.fls",
            "*.log",
            "*.synctex.gz",
            "*.bbl",
            "*.blg",
            "*.out",
        ]
        for artifact in artifacts:
            manifest.add_vcs_ignore(artifact)
            manifest.add_workspace_hide(artifact)


def generate_latex_boilerplate(filename: str, preset: str) -> Path:
    """Generates a boilerplate LaTeX file and evaluates local VCS ignores.

    Preamble inclusions cascade based on the complexity of the requested preset.

    Args:
        filename (str): The requested output filename.
        preset (str): The configuration preset dictating preamble complexity.

    Returns:
        Path: The absolute or relative path to the generated file.

    Raises:
        FileExistsError: If the target file already exists in the directory.
    """
    target_path = Path(filename)
    if not target_path.suffix:
        target_path = target_path.with_suffix(".tex")

    if target_path.exists():
        raise FileExistsError(f"Target file already exists: {target_path}")

    # Baseline configuration
    preamble = [
        "\\documentclass[12pt, letterpaper]{article}\n",
        "\\usepackage{fontspec}",
        "\\usepackage{geometry}",
        "\\usepackage{hyperref}",
    ]

    # Accumulate science macros
    if preset in ("science", "lab-report", "academic"):
        preamble.extend(
            [
                "\\usepackage{amsmath, amssymb}",
                "\\usepackage{siunitx} % Standardized units and uncertainties",
                "\\usepackage{physics} % Macros for derivatives, matrices, bra-kets",
            ]
        )

    # Accumulate data presentation macros
    if preset == "lab-report":
        preamble.extend(
            [
                "\\usepackage{graphicx}",
                "\\usepackage{booktabs} % Professional table formatting",
                "\\usepackage{caption}",
                "\\usepackage{float}",
            ]
        )

    # Accumulate bibliography and authorship macros
    if preset == "academic":
        preamble.extend(
            [
                "\\usepackage[backend=biber,style=ieee]{biblatex}",
                "\\usepackage{authblk} % Multiple authors/affiliations",
                "\\usepackage{cleveref}",
            ]
        )

    document_body = [
        "\\begin{document}\n",
        "\\title{Document Title}",
        "\\author{Author Name}",
        "\\date{\\today}",
        "\\maketitle\n",
        "\\section{Introduction}",
        "Begin writing here...\n",
        "\\end{document}\n",
    ]

    # Construct the AST string equivalent and write to disk
    content = "\n".join(preamble) + "\n\n" + "\n".join(document_body)
    target_path.write_text(content)

    # Non-intrusive VCS artifact check
    gitignore_path = Path(".gitignore")
    if gitignore_path.exists():
        if "*.aux" not in gitignore_path.read_text():
            logger.warning(
                "LaTeX auxiliary files not found in .gitignore. "
                "Consider appending *.aux, *.bbl, *.fls, etc., to maintain tree cleanliness."
            )
    else:
        logger.warning(
            "No .gitignore detected in current workspace. "
            "Consider tracking LaTeX build artifacts."
        )

    return target_path


def generate_cpp_class(class_name: str) -> list[Path]:
    """Generates standard C++ header and implementation files.

    Creates a `<class_name>.hpp` with a pragma once guard and a `<class_name>.cpp`
    with standard constructor and destructor boilerplate.

    Args:
        class_name (str): The name of the C++ class to scaffold.

    Returns:
        list[Path]: The paths to the generated header and implementation files.

    Raises:
        FileExistsError: If either target file already exists in the directory.
        ValueError: If a class name is not provided.
    """
    if not class_name:
        raise ValueError("A class name must be provided for C++ scaffolding.")

    # Enforce basic PascalCase naming convention
    safe_name = class_name[:1].upper() + class_name[1:]

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


def generate_cmake(project_name: str = "ProtostarApp") -> Path:
    """Generates a CMakeLists.txt statically linking local C++ source files.

    Scans the current working directory for `.cpp` files to include in the
    `add_executable` directive, avoiding the CMake globbing cache anti-pattern.
    Enforces the C++17 standard.

    Args:
        project_name (str, optional): The name of the executable target.
                                      Defaults to "ProtostarApp".

    Returns:
        Path: The path to the generated CMakeLists.txt.

    Raises:
        FileExistsError: If a CMakeLists.txt already exists.
    """
    target_path = Path("CMakeLists.txt")
    if target_path.exists():
        raise FileExistsError("CMakeLists.txt already exists in this directory.")

    # Statically resolve cpp files to avoid build system cache invalidation issues
    cpp_files = [p.name for p in Path(".").glob("*.cpp")]

    if not cpp_files:
        logger.warning(
            "No .cpp files found in the current directory. The CMake target will be empty."
        )
        source_list = "main.cpp  # WARNING: File does not exist yet"
    else:
        source_list = " ".join(cpp_files)

    cmake_content = f"""cmake_minimum_required(VERSION 3.10)
project({project_name})

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

add_executable(${{PROJECT_NAME}} {source_list})
"""

    target_path.write_text(cmake_content)
    return target_path
