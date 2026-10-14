import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from comfy_model.workflow import load_manifest

REPO = Path(__file__).resolve().parent.parent
BOOTSTRAP = REPO / "pod" / "bootstrap.sh"
VERSIONS = REPO / "pod" / "versions.env"


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck not installed")
def test_bootstrap_shellcheck():
    r = subprocess.run(["shellcheck", str(BOOTSTRAP)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def _print_downloads() -> list[tuple[str, str]]:
    env = {**os.environ, "CM_PY": sys.executable}
    r = subprocess.run(["bash", str(BOOTSTRAP), "--print-downloads"],
                       capture_output=True, text=True, env=env, timeout=30)
    assert r.returncode == 0, r.stderr
    pairs = []
    for line in r.stdout.splitlines():
        url, dest = line.split(" ")
        pairs.append((url, dest))
    return pairs


def test_bootstrap_reads_manifest_paths():
    specs = load_manifest(REPO / "pod" / "models.yaml")
    pairs = _print_downloads()
    expected = {f"/workspace/ComfyUI/models/{s.dest}/{s.file}": s.url for s in specs}
    counts = Counter(dest for _, dest in pairs)
    assert set(counts) == set(expected)
    assert all(n == 1 for n in counts.values()), counts
    assert dict((d, u) for u, d in pairs) == expected
    for _, dest in pairs:  # everything stays on the network volume
        assert dest.startswith("/workspace/")


def test_bootstrap_unknown_argument_fails():
    r = subprocess.run(["bash", str(BOOTSTRAP), "--bogus"], capture_output=True, text=True, timeout=30)
    assert r.returncode == 2
    assert "usage" in r.stderr.lower()


def test_bootstrap_contract():
    src = BOOTSTRAP.read_text()
    assert "set -euo pipefail" in src
    assert "/proc/1/environ" in src
    for var in ("RUNPOD_POD_ID", "RUNPOD_API_KEY", "HF_TOKEN", "IDLE_TIMEOUT_MIN", "MAX_RUNTIME_H"):
        assert f"{var}=*" in src, var
    assert "NO_PROXY=127.0.0.1,localhost" in src
    assert "COMFY_URL=" in src
    assert "/workspace/.cm/watchdog.pid" in src
    assert "--listen 0.0.0.0" in src
    assert "nohup" in src
    assert "-C -" in src and "Authorization: Bearer" in src and ".part" in src
    assert "set -x" not in src  # would echo HF_TOKEN / RUNPOD_API_KEY into logs
    for name in ("ComfyUI-Impact-Pack", "ComfyUI-Impact-Subpack"):
        assert name in src


def test_versions_env_pins():
    pins = {}
    for line in VERSIONS.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            k, _, v = line.partition("=")
            pins[k] = v
    assert set(pins) == {"COMFYUI_TAG", "IMPACT_PACK_COMMIT", "IMPACT_SUBPACK_COMMIT", "AI_TOOLKIT_COMMIT"}
    assert pins["COMFYUI_TAG"].startswith("v")
    for k in ("IMPACT_PACK_COMMIT", "IMPACT_SUBPACK_COMMIT", "AI_TOOLKIT_COMMIT"):
        assert len(pins[k]) == 40 and all(c in "0123456789abcdef" for c in pins[k]), k
