import json
import os
import shutil
import subprocess
import sys
import time
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
    # SaveVideo would otherwise embed the prompt/workflow in every mp4
    assert "--disable-metadata" in src
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


# -- full-mode simulation ---------------------------------------------------------
# A copy of bootstrap.sh with /workspace rewritten to tmp_path and stub git/curl/
# runpodctl on PATH; the venv python is the test interpreter. Exercises the real
# control flow without network or a pod.
STUB_GIT = """#!/bin/bash
if [ "$1" = init ]; then mkdir -p "$3/.git"; exit 0; fi
if [ "$1" = -C ] && [ "$3" = checkout ]; then
  printf 'import json, os, time\\njson.dump(sorted(os.environ), open(os.environ["CM_SIM_ENVDUMP"], "w"))\\ntime.sleep(60)\\n' > "$2/main.py"
fi
exit 0
"""
STUB_CURL = """#!/bin/bash
out=""; while [ $# -gt 0 ]; do [ "$1" = -o ] && out="$2"; shift; done
case "$out" in /dev/null) exit 7;; "") exit 0;; *) echo data > "$out";; esac
"""
STUB_WATCHDOG = "import time\ntime.sleep(60)\n"
SIM_SECRET = "rpa_SIM_SECRET_KEY_123"


def _simulate(tmp_path, runpodctl: str | None, wait_for: Path | None = None):
    ws = tmp_path / "ws"
    pod = ws / "cm" / "pod"
    pod.mkdir(parents=True)
    (pod / "bootstrap.sh").write_text(BOOTSTRAP.read_text().replace("/workspace", str(ws)))
    for f in ("models.yaml", "versions.env"):
        shutil.copy(REPO / "pod" / f, pod / f)
    (ws / "cm" / "watchdog.py").write_text(STUB_WATCHDOG)
    venv_bin = ws / "venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").symlink_to(sys.executable)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stubs = {"git": STUB_GIT, "curl": STUB_CURL}
    if runpodctl is not None:
        stubs["runpodctl"] = runpodctl
    for name, body in stubs.items():
        (bindir / name).write_text(body)
        (bindir / name).chmod(0o755)
    # system dirs only: the developer's own runpodctl (if any) must not leak in
    path = os.pathsep.join([str(bindir), str(Path(sys.executable).parent), "/usr/bin", "/bin"])
    assert runpodctl is not None or shutil.which("runpodctl", path=path) is None
    env = {"PATH": path, "HOME": str(tmp_path), "RUNPOD_POD_ID": "simpod",
           "RUNPOD_API_KEY": SIM_SECRET, "HF_TOKEN": "hf_SIM_TOKEN",
           "CM_SIM_ENVDUMP": str(tmp_path / "comfy_env.json")}
    try:
        r = subprocess.run(["bash", str(pod / "bootstrap.sh")], capture_output=True,
                           text=True, env=env, timeout=40)
        for _ in range(100):  # let background processes start before we stop them
            if wait_for is None or (wait_for.exists() and wait_for.read_text()):
                break
            time.sleep(0.1)
    finally:
        for pidfile in (ws / ".cm").glob("*.pid") if (ws / ".cm").exists() else []:
            try:
                os.kill(int(pidfile.read_text().strip()), 15)
            except (ValueError, OSError):
                pass
    return r, ws


RUNPODCTL_OK = "#!/bin/bash\n[ \"$1 $2 $3\" = 'get pod simpod' ] && echo 'ID NAME' && exit 0\nexit 1\n"
RUNPODCTL_UNAUTH = f"#!/bin/bash\necho 'Error: unauthorized, api key {SIM_SECRET} invalid' >&2\nexit 1\n"


def test_bootstrap_dies_without_runpodctl(tmp_path):
    r, ws = _simulate(tmp_path, runpodctl=None)
    assert r.returncode != 0
    assert "runpodctl missing" in r.stderr
    assert not (ws / ".cm" / "watchdog.pid").exists()


def test_bootstrap_dies_when_runpodctl_unauthorised(tmp_path):
    r, ws = _simulate(tmp_path, runpodctl=RUNPODCTL_UNAUTH)
    assert r.returncode != 0
    assert "runpodctl cannot reach the RunPod API" in r.stderr
    assert SIM_SECRET not in r.stdout + r.stderr
    assert not (ws / ".cm" / "watchdog.pid").exists()


def test_bootstrap_full_run_simulated(tmp_path):
    lora_busy = tmp_path / "ws" / ".cm" / "busy"
    lora_busy.parent.mkdir(parents=True)
    lora_busy.write_text("")  # `cm lora train` heartbeat must survive bootstrap
    # finishing well under the timeout also proves no orphaned `sleep 60` holds the pipes
    envdump = tmp_path / "comfy_env.json"
    r, ws = _simulate(tmp_path, runpodctl=RUNPODCTL_OK, wait_for=envdump)
    assert r.returncode == 0, r.stdout + r.stderr
    assert lora_busy.exists()
    assert not (ws / ".cm" / "busy.bootstrap").exists()
    assert (ws / ".cm" / "watchdog.pid").exists() and (ws / ".cm" / "comfyui.pid").exists()
    for _, dest in _print_downloads():
        assert Path(dest.replace("/workspace", str(ws))).is_file(), dest
    assert SIM_SECRET not in r.stdout + r.stderr
    comfy_env = json.loads(envdump.read_text())
    assert "RUNPOD_API_KEY" not in comfy_env and "HF_TOKEN" not in comfy_env
    assert "COMFY_URL" in comfy_env
