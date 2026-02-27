import abc
import logging
from pathlib import Path

from protostar.config import ProtostarConfig

logger = logging.getLogger("protostar")


class TargetGenerator(abc.ABC):
    """Abstract base class for discrete file scaffolding targets.

    Generators are imperative, executing disk I/O immediately when invoked,
    unlike the declarative initialization modules.
    """

    @property
    @abc.abstractmethod
    def target_name(self) -> str:
        """Returns the CLI identifier used to dispatch this generator."""
        pass

    @abc.abstractmethod
    def execute(self, identifier: str | None, config: ProtostarConfig) -> list[Path]:
        """Executes the discrete disk I/O for this generator.

        Args:
            identifier: The user-provided target name or primary filename.
            config: The active global CLI configuration.

        Returns:
            A list of paths to the files written to disk.

        Raises:
            FileExistsError: If a target file already exists in the workspace.
            ValueError: If a required identifier was not provided.
        """
        pass
