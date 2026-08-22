from protostar.dependencies import install_dependencies
from protostar.errors import CommandExecutionError, CommandTimeoutError
from protostar.manifest import DependencyManifest, Severity


def test_install_dependencies_uv(mocker):
    """Test that install_dependencies invokes uv add and uv add --dev with proper arguments."""
    mock_execute = mocker.patch("protostar.dependencies.execute_subprocess")

    diagnostics = []

    def on_diagnostic(msg: str, sev: Severity, detail: str | None) -> None:
        diagnostics.append((msg, sev, detail))

    install_dependencies(
        dependencies_manifest=DependencyManifest(
            dependencies=["fastapi"],
            dev_dependencies=["pytest"],
            docs_dependencies=["mkdocs"],
        ),
        on_diagnostic=on_diagnostic,
    )

    mock_execute.assert_any_call(["uv", "add", "fastapi"], timeout=600)
    mock_execute.assert_any_call(["uv", "add", "--dev", "pytest"], timeout=600)
    mock_execute.assert_any_call(
        ["uv", "add", "--group", "docs", "mkdocs"], timeout=600
    )
    assert diagnostics == []


def test_install_dependencies_empty(mocker):
    """Test that install_dependencies is a no-op when all lists are empty."""
    mock_execute = mocker.patch("protostar.dependencies.execute_subprocess")
    diagnostics = []

    install_dependencies(
        dependencies_manifest=DependencyManifest(),
        on_diagnostic=lambda msg, sev, detail: diagnostics.append((msg, sev, detail)),
    )

    mock_execute.assert_not_called()
    assert diagnostics == []


def test_install_dependencies_graceful_degradation_uv(mocker):
    """Test that uv resolution failures invoke the diagnostic callback without aborting."""
    diagnostics = []

    mocker.patch(
        "protostar.dependencies.execute_subprocess",
        side_effect=CommandExecutionError(
            command=["uv", "add", "invalid-pkg"],
            returncode=1,
            stdout="Error: failed to resolve",
            stderr="Package not found",
        ),
    )

    install_dependencies(
        dependencies_manifest=DependencyManifest(
            dependencies=["invalid-pkg"], dev_dependencies=["invalid-dev-pkg"]
        ),
        on_diagnostic=lambda msg, sev, detail: diagnostics.append((msg, sev, detail)),
    )

    assert len(diagnostics) == 2
    assert "Standard dependency resolution failed" in diagnostics[0][0]
    assert diagnostics[0][1] == Severity.WARNING
    assert "Development dependency resolution failed" in diagnostics[1][0]
    assert diagnostics[1][1] == Severity.WARNING


def test_install_dependencies_timeout_degradation(mocker):
    """Test that dependency resolution timeouts trigger diagnostic warnings."""
    diagnostics = []

    mocker.patch(
        "protostar.dependencies.execute_subprocess",
        side_effect=CommandTimeoutError(
            command=["uv", "add", "massive-pkg"], timeout=600
        ),
    )

    install_dependencies(
        dependencies_manifest=DependencyManifest(dependencies=["massive-pkg"]),
        on_diagnostic=lambda msg, sev, detail: diagnostics.append((msg, sev, detail)),
    )

    assert len(diagnostics) == 1
    assert "Command timed out" in diagnostics[0][0]
    assert diagnostics[0][1] == Severity.WARNING


def test_install_dependencies_adds_warning_with_telemetry_on_failure(mocker):
    """Test that stderr telemetry is forwarded to diagnostic detail."""
    diagnostics = []

    error = CommandExecutionError(
        command=["uv", "add", "numpy"],
        returncode=1,
        stdout="Resolving dependencies...",
        stderr="error: package numpy not found",
    )
    mocker.patch("protostar.dependencies.execute_subprocess", side_effect=error)

    install_dependencies(
        dependencies_manifest=DependencyManifest(dependencies=["numpy"]),
        on_diagnostic=lambda msg, sev, detail: diagnostics.append((msg, sev, detail)),
    )

    assert len(diagnostics) == 1
    msg, sev, detail = diagnostics[0]
    assert sev == Severity.WARNING
    assert "Standard dependency resolution failed" in msg
    assert detail is not None
    assert "--- STDERR ---" in detail
    assert "error: package numpy not found" in detail


def test_dependency_group_properties():
    from protostar.dependencies import DependencyGroup

    assert DependencyGroup.MAIN.cli_args == []
    assert DependencyGroup.MAIN.label == "standard"

    assert DependencyGroup.DEV.cli_args == ["--dev"]
    assert DependencyGroup.DEV.label == "development"

    assert DependencyGroup.DOCS.cli_args == ["--group", "docs"]
    assert DependencyGroup.DOCS.label == "documentation"
