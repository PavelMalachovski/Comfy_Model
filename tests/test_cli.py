from typer.testing import CliRunner

from comfy_model.cli import app


def test_help_works():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ComfyUI" in result.output
