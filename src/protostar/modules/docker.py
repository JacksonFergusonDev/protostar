"""Docker's description.

Docker is a recipe flag of its own rather than a tooling module, so its
``ToolInfo`` lives here instead of on a module. It is the one source for
``--docker``'s help, the schema, and the TUI, as a module's ``info`` is.
"""

from .base import ToolInfo

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
