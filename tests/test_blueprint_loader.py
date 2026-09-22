import sys

import pytest

from protostar.config import TemplateSource, UserConfig
from protostar.errors import MissingTemplateVariablesError
from protostar.templates import TemplateType, discover_templates

BUILTIN_TEMPLATES = sorted(
    t.alias
    for t in discover_templates(config=UserConfig())
    if t.type == TemplateType.BUILT_IN
)


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows does not support < or > in filenames"
)
def test_template_blueprint_load_local_directory(tmp_path):
    """Test loading a template from a local directory."""
    # Setup standard protostar.toml
    toml_path = tmp_path / "protostar.toml"
    toml_path.write_text("[env]\nruff = true\n\n[files]\n", encoding="utf-8")

    # Setup template subdirectory
    template_dir = tmp_path / "template"
    template_dir.mkdir()

    # Create a nested file with variables in both path and content
    nested_dir = template_dir / "src" / "<% PACKAGE_NAME %>"
    nested_dir.mkdir(parents=True)

    main_file = nested_dir / "main.py"
    main_file.write_text("print('Hello from <% PACKAGE_NAME %>!')\n", encoding="utf-8")

    # Test loading
    blueprint = TemplateSource.load(str(tmp_path)).render({"PACKAGE_NAME": "my_app"})

    # Verify interpolation in paths and contents
    assert "src/my_app/main.py" in blueprint.files
    assert blueprint.files["src/my_app/main.py"] == "print('Hello from my_app!')\n"


def test_template_blueprint_variable_extraction_and_resolution(tmp_path):
    """Test that variables deep in the template directory are extracted and resolved."""
    toml_path = tmp_path / "protostar.toml"
    toml_path.write_text("[env]\nruff = true\n", encoding="utf-8")

    template_dir = tmp_path / "template"
    template_dir.mkdir()

    deep_file = template_dir / "config.yaml"
    deep_file.write_text("db_url: <% DATABASE_URL %>\n", encoding="utf-8")

    source = TemplateSource.load(str(tmp_path))
    assert source.variables == {"DATABASE_URL"}

    blueprint = source.render({"DATABASE_URL": "postgresql://localhost:5432/db"})

    assert "config.yaml" in blueprint.files
    assert blueprint.files["config.yaml"] == "db_url: postgresql://localhost:5432/db\n"


def test_template_blueprint_missing_variables_error(tmp_path):
    """Test that rendering without a value raises, naming the variable."""
    toml_path = tmp_path / "protostar.toml"
    toml_path.write_text("[env]\nruff = true\n", encoding="utf-8")

    template_dir = tmp_path / "template"
    template_dir.mkdir()

    deep_file = template_dir / "config.yaml"
    deep_file.write_text("db_url: <% DATABASE_URL %>\n", encoding="utf-8")

    with pytest.raises(MissingTemplateVariablesError, match="DATABASE_URL") as caught:
        TemplateSource.load(str(tmp_path)).render({})
    assert caught.value.variables == ("DATABASE_URL",)


@pytest.mark.parametrize("template_name", BUILTIN_TEMPLATES)
def test_builtin_templates_no_trailing_whitespace(template_name: str):
    """Statically verifies all built-in template files have zero trailing whitespace and valid newlines."""
    import importlib.resources
    import tomllib

    content = (
        importlib.resources.files("protostar.templates")
        .joinpath(f"{template_name}.toml")
        .read_text(encoding="utf-8")
    )
    data = tomllib.loads(content)
    files = data.get("files", {})

    for filepath, file_content in files.items():
        for idx, line in enumerate(file_content.splitlines(), 1):
            assert not line.endswith(" "), (
                f"Trailing space in {template_name}.toml -> {filepath}:{idx}"
            )
            assert not line.endswith("\t"), (
                f"Trailing tab in {template_name}.toml -> {filepath}:{idx}"
            )

        if file_content:
            assert file_content.endswith("\n"), (
                f"Missing trailing newline in {template_name}.toml -> {filepath}"
            )
