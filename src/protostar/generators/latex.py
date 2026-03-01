import logging
from pathlib import Path

from rich.console import Console

from protostar.config import ProtostarConfig

from .base import TargetGenerator

logger = logging.getLogger("protostar")
console = Console()


class LatexGenerator(TargetGenerator):
    """Generates a boilerplate LaTeX document based on the global preset."""

    @property
    def target_name(self) -> str:
        """Returns the generator's target name."""
        return "tex"

    def execute(self, identifier: str | None, config: ProtostarConfig) -> list[Path]:
        """Generates a boilerplate LaTeX document for the active preset.

        Args:
            identifier: Optional output filename, defaults to 'main.tex'.
            config: The active Protostar configuration.

        Returns:
            A list containing the created .tex file path.

        Raises:
            FileExistsError: If the target file already exists.
        """
        filename = identifier or "main.tex"
        preset = config.presets.get("latex", "minimal")

        target_path = Path(filename)
        if not target_path.suffix:
            target_path = target_path.with_suffix(".tex")

        if target_path.exists():
            raise FileExistsError(f"Target file already exists: {target_path}")

        preamble = [
            "\\documentclass[12pt, letterpaper]{article}\n",
            "\\usepackage{fontspec}",
            "\\usepackage{geometry}",
            "\\usepackage{hyperref}",
        ]

        if preset in ("science", "lab-report", "academic"):
            preamble.extend(
                [
                    "\\usepackage{amsmath, amssymb}",
                    "\\usepackage{siunitx} % Standardized units and uncertainties",
                    "\\usepackage{physics} % Macros for derivatives, matrices, bra-kets",
                ]
            )

        if preset == "lab-report":
            preamble.extend(
                [
                    "\\usepackage{graphicx}",
                    "\\usepackage{booktabs} % Professional table formatting",
                    "\\usepackage{caption}",
                    "\\usepackage{float}",
                ]
            )

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

        content = "\n".join(preamble) + "\n\n" + "\n".join(document_body)
        target_path.write_text(content)

        gitignore_path = Path(".gitignore")
        if gitignore_path.exists():
            if "*.aux" not in gitignore_path.read_text():
                console.print(
                    "[yellow]Warning:[/yellow] LaTeX auxiliary files not found in .gitignore. "
                    "Consider appending *.aux, *.bbl, *.fls, etc., to maintain tree cleanliness."
                )
        else:
            console.print(
                "[yellow]Warning:[/yellow] No .gitignore detected in current workspace. "
                "Consider tracking LaTeX build artifacts."
            )

        return [target_path]
