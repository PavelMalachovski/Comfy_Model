from pathlib import Path

import pytest
from typer.testing import CliRunner

from comfy_model.cli import app, bootstrap_cmd


def test_help_works():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ComfyUI" in result.output


def test_bootstrap_cmd_default():
    assert bootstrap_cmd(None) == "bash /workspace/cm/pod/bootstrap.sh"


def test_bootstrap_cmd_manifest():
    assert bootstrap_cmd(Path("pod/bakeoff_models.yaml")) == (
        "CM_MANIFEST=/workspace/cm/pod/bakeoff_models.yaml bash /workspace/cm/pod/bootstrap.sh")


@pytest.mark.parametrize("bad", ["/etc/passwd", "pod/../x.yaml", "pod/a b.yaml", "pod/x.txt", "x.yaml"])
def test_bootstrap_cmd_rejects_paths_outside_pod(bad):
    with pytest.raises(ValueError):
        bootstrap_cmd(Path(bad))
