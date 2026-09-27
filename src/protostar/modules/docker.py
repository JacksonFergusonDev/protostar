"""Docker containerization tooling module."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from protostar.metadata import MetadataKey
from protostar.workflows import DOCKERFILE

from .base import PathSignal, ToolInfo, ToolModule

if TYPE_CHECKING:
    from protostar.manifest import EnvironmentManifest

logger = logging.getLogger("protostar")

DOCKER_NAME = "Docker"
"""Docker's display name."""

DOCKER_INFO = ToolInfo(
    summary="Package the project as a container image that runs anywhere",
    adds=(
        "A Dockerfile that installs the locked dependencies with uv into a slim "
        "Python image and runs the project as an unprivileged user, and a "
        ".dockerignore that keeps Git, tests, docs, and local files out of it."
    ),
    workflow=(
        "`docker build -t <name> .` builds the image and `docker run <name>` "
        "starts the project inside it, the same way on every machine. A web API "
        "listens on port 8000 unless you set the Docker port detail. You need "
        "Docker installed only to build or run the image."
    ),
    docs_url="https://docs.docker.com/get-started/",
)
"""What ``--docker`` does."""


class DockerModule(ToolModule):
    """Configures Docker containerization artifacts (Dockerfile and .dockerignore)."""

    cli_flags = ("--docker",)
    info = DOCKER_INFO
    config_key = "docker"
    signals = (PathSignal(DOCKERFILE), PathSignal(".dockerignore"))
    optional_metadata = (MetadataKey.DOCKER_PORT,)

    @property
    def name(self) -> str:
        """Returns the human-readable module name."""
        return DOCKER_NAME

    def build(self, manifest: EnvironmentManifest) -> None:
        """Appends Docker requirements to the environment manifest."""
        logger.debug("Building Docker tooling layer.")
        manifest.tooling.wants_docker = True
