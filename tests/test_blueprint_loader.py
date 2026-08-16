import pytest

from protostar.config import TemplateBlueprint
from protostar.errors import TemplateResolutionError


def test_template_blueprint_load_local_directory(tmp_path):
    """Test loading a TemplateBlueprint from a local directory."""
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
    blueprint = TemplateBlueprint.load(
        str(tmp_path), template_context={"PACKAGE_NAME": "my_app"}
    )

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

    # Resolver function
    def mock_resolver(missing_vars):
        assert "DATABASE_URL" in missing_vars
        return {"DATABASE_URL": "postgresql://localhost:5432/db"}

    blueprint = TemplateBlueprint.load(str(tmp_path), variable_resolver=mock_resolver)

    assert "config.yaml" in blueprint.files
    assert blueprint.files["config.yaml"] == "db_url: postgresql://localhost:5432/db\n"


def test_template_blueprint_missing_variables_error(tmp_path):
    """Test that missing variables without a resolver raise an error."""
    toml_path = tmp_path / "protostar.toml"
    toml_path.write_text("[env]\nruff = true\n", encoding="utf-8")

    template_dir = tmp_path / "template"
    template_dir.mkdir()

    deep_file = template_dir / "config.yaml"
    deep_file.write_text("db_url: <% DATABASE_URL %>\n", encoding="utf-8")

    with pytest.raises(
        TemplateResolutionError, match="requires variables: DATABASE_URL"
    ):
        TemplateBlueprint.load(str(tmp_path))
