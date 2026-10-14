import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from comfy_model import cli, lora, remote
from comfy_model.cli import app
from comfy_model.config import Secrets
from comfy_model.profile import Profile, load_profile
from comfy_model.runpod_pod import PodInfo

REPO = Path(__file__).resolve().parent.parent
TRAIN_SCRIPT = REPO / "pod" / "train_lora.sh"
POD = PodInfo(id="abc", ssh_host="203.0.113.7", ssh_port=40122, comfy_url="https://abc-8188.proxy.runpod.net")

PROFILE = Profile(name="Greta", trigger="ohwxgreta", appearance="28-year-old woman",
                  style_suffix="photo", video_negative="blurry")


def make_images(d: Path, n: int, ext: str = "png") -> list[Path]:
    d.mkdir(parents=True, exist_ok=True)
    files = []
    for i in range(1, n + 1):
        f = d / f"s{i:02d}_01.{ext}"
        f.write_bytes(b"img%d" % i)
        files.append(f)
    return files


# -- prepare ------------------------------------------------------------------------
def test_prepare_numbers_and_captions(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "dataset" / "ohwxgreta"
    make_images(src, 16)
    assert lora.prepare_dataset(src, dest, PROFILE) == 16
    assert sorted(p.name for p in dest.glob("*.png")) == [f"img_{i:03d}.png" for i in range(1, 17)]
    assert (dest / "img_001.png").read_bytes() == b"img1"  # sorted by source name
    assert (dest / "img_016.png").read_bytes() == b"img16"
    assert (dest / "img_001.txt").read_text() == "ohwxgreta, a photo of a woman"


def test_prepare_uses_manifest_prompt(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "dest"
    make_images(src, 15)
    (src / "manifest.jsonl").write_text(
        json.dumps({"scene_id": "s01", "n": 1, "seed": 1, "prompt": "sitting in a cafe",
                    "file": "s01_01.png", "kind": "dataset"}) + "\nnot json\n"
        + json.dumps({"scene_id": "gone", "n": 1, "seed": 2, "prompt": "deleted one",
                      "file": "gone_01.png", "kind": "dataset"}) + "\n")
    lora.prepare_dataset(src, dest, PROFILE)
    assert (dest / "img_001.txt").read_text() == "ohwxgreta, sitting in a cafe"
    assert (dest / "img_002.txt").read_text() == "ohwxgreta, a photo of a woman"


def test_prepare_rejects_too_few(tmp_path):
    src = tmp_path / "src"
    make_images(src, 14)
    with pytest.raises(ValueError, match="14"):
        lora.prepare_dataset(src, tmp_path / "dest", PROFILE)
    assert not (tmp_path / "dest" / "img_001.png").exists()


def test_prepare_rejects_too_many(tmp_path):
    src = tmp_path / "src"
    make_images(src, 61)
    with pytest.raises(ValueError, match="61"):
        lora.prepare_dataset(src, tmp_path / "dest", PROFILE)


def test_prepare_keeps_extension_and_ignores_other_files(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "dest"
    make_images(src, 15, "jpg")
    (src / "notes.txt").write_text("x")
    (src / "manifest.jsonl").write_text("")
    assert lora.prepare_dataset(src, dest, PROFILE) == 15
    assert (dest / "img_015.jpg").is_file() and (dest / "img_015.txt").is_file()
    assert sorted(p.name for p in dest.iterdir()).count("notes.txt") == 0


def test_prepare_clears_old_files_on_rerun(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "dest"
    files = make_images(src, 20)
    lora.prepare_dataset(src, dest, PROFILE)
    for f in files[:5]:
        f.unlink()
    assert lora.prepare_dataset(src, dest, PROFILE) == 15
    assert sorted(p.name for p in dest.glob("img_*.png")) == [f"img_{i:03d}.png" for i in range(1, 16)]
    assert len(list(dest.glob("img_*.txt"))) == 15


def test_prepare_missing_src(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        lora.prepare_dataset(tmp_path / "nope", tmp_path / "dest", PROFILE)


# -- training config ------------------------------------------------------------------
def test_training_config_values():
    cfg = yaml.safe_load(lora.render_training_config(load_profile(), 1))
    assert cfg["job"] == "extension"
    assert cfg["config"]["name"] == "ohwxgreta_v1"
    p = cfg["config"]["process"][0]
    assert p["type"] == "sd_trainer"
    assert p["training_folder"] == "/workspace/ai-toolkit/output"
    assert p["trigger_word"] == "ohwxgreta"
    assert p["network"] == {"type": "lora", "linear": 16, "linear_alpha": 16}
    assert p["save"]["save_every"] == 500
    ds = p["datasets"][0]
    assert ds["folder_path"] == "/workspace/dataset/ohwxgreta"
    assert ds["resolution"] == [512, 768, 1024]
    assert p["train"]["steps"] == 2000
    assert p["train"]["lr"] == 1e-4
    assert p["train"]["batch_size"] == 1
    assert p["model"]["name_or_path"] == "black-forest-labs/FLUX.1-dev"
    assert p["model"]["is_flux"] is True and p["model"]["quantize"] is True
    assert len(p["sample"]["prompts"]) == 3
    assert all("ohwxgreta" in s for s in p["sample"]["prompts"])


def test_training_config_version_in_name():
    cfg = yaml.safe_load(lora.render_training_config(load_profile(), 3))
    assert cfg["config"]["name"] == "ohwxgreta_v3"


# -- remote script --------------------------------------------------------------------
def test_train_remote_command_has_heartbeat():
    src = TRAIN_SCRIPT.read_text()
    assert "/workspace/.cm/busy" in src
    assert "/workspace/.cm/train.log" in src
    assert "setsid nohup" in src
    assert "AI_TOOLKIT_COMMIT" in src
    assert "/proc/1/environ" in src and "HF_TOKEN=*" in src
    assert "RUNPOD_API_KEY" not in src  # training needs only HF_TOKEN
    assert "set -x" not in src
    assert "/workspace/ComfyUI/models/loras" in src
    cmd = lora.train_command("ohwxgreta", 1)
    assert "train_lora.sh" in cmd and "ohwxgreta_v1" in cmd


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck not installed")
def test_train_script_shellcheck():
    r = subprocess.run(["shellcheck", str(TRAIN_SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_train_script_syntax():
    r = subprocess.run(["bash", "-n", str(TRAIN_SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# -- CLI ----------------------------------------------------------------------------------
@pytest.fixture
def fake_remote(monkeypatch):
    calls = []
    monkeypatch.setattr(remote, "run", lambda argv: calls.append(argv) or 0)
    monkeypatch.setattr(cli, "_current_pod", lambda: POD)
    monkeypatch.setattr(cli, "load_secrets", lambda: Secrets({"HF_TOKEN": "hf_x"}))
    return calls


def test_cli_prepare(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "character").mkdir()
    shutil.copy(REPO / "character" / "profile.yaml", tmp_path / "character" / "profile.yaml")
    make_images(tmp_path / "out", 16)
    r = CliRunner().invoke(app, ["lora", "prepare", "out"])
    assert r.exit_code == 0, r.output
    assert len(list((tmp_path / "dataset" / "ohwxgreta").glob("img_*.png"))) == 16
    assert "16" in r.output


def test_cli_prepare_too_few_exits_1(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "character").mkdir()
    shutil.copy(REPO / "character" / "profile.yaml", tmp_path / "character" / "profile.yaml")
    make_images(tmp_path / "out", 3)
    r = CliRunner().invoke(app, ["lora", "prepare", "out"])
    assert r.exit_code == 1
    assert "3" in r.output


def _train_cwd(tmp_path, monkeypatch, n=16):
    monkeypatch.chdir(tmp_path)
    for d in ("character", "training", "pod"):
        shutil.copytree(REPO / d, tmp_path / d)
    src = tmp_path / "out"
    make_images(src, n)
    lora.prepare_dataset(src, tmp_path / "dataset" / "ohwxgreta", PROFILE)
    return tmp_path


def test_cli_train_syncs_and_launches(tmp_path, monkeypatch, fake_remote):
    _train_cwd(tmp_path, monkeypatch)
    r = CliRunner().invoke(app, ["lora", "train", "--version", "2"])
    assert r.exit_code == 0, r.output
    flat = [" ".join(a) for a in fake_remote]
    assert any(a[0] == "rsync" and "/workspace/dataset/" in a[-1] for a in fake_remote)
    assert any(a[0] == "rsync" and a[-1].endswith(":/workspace/cm/training/") for a in fake_remote)
    assert any(a[0] == "rsync" and a[-2].endswith("ohwxgreta_v2.yaml") for a in fake_remote)
    assert any(a[0] == "rsync" and "pod" in a and a[-1].endswith(":/workspace/cm/") for a in fake_remote)
    ssh_cmds = [a[-1] for a in fake_remote if a[0] == "ssh"]
    assert any("train_lora.sh" in c and "ohwxgreta_v2" in c for c in ssh_cmds)
    assert "cm lora status" in r.output
    assert "hf_x" not in r.output + "".join(flat)  # token is never sent from the laptop
    cfg = yaml.safe_load((tmp_path / ".cm" / "training" / "ohwxgreta_v2.yaml").read_text())
    assert cfg["config"]["name"] == "ohwxgreta_v2"


def test_cli_train_no_pod(tmp_path, monkeypatch, fake_remote):
    _train_cwd(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "_current_pod", lambda: None)
    r = CliRunner().invoke(app, ["lora", "train"])
    assert r.exit_code == 1
    assert "no running pod" in r.output
    assert fake_remote == []


def test_cli_train_no_hf_token(tmp_path, monkeypatch, fake_remote):
    _train_cwd(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "load_secrets", lambda: Secrets())
    r = CliRunner().invoke(app, ["lora", "train"])
    assert r.exit_code == 1
    assert "HF_TOKEN" in r.output and "license" in r.output
    assert fake_remote == []


def test_cli_train_no_dataset(tmp_path, monkeypatch, fake_remote):
    _train_cwd(tmp_path, monkeypatch)
    shutil.rmtree(tmp_path / "dataset")
    r = CliRunner().invoke(app, ["lora", "train"])
    assert r.exit_code == 1
    assert "cm lora prepare" in r.output
    assert fake_remote == []


def test_cli_train_rsync_failure_stops(tmp_path, monkeypatch, fake_remote):
    _train_cwd(tmp_path, monkeypatch)
    monkeypatch.setattr(remote, "run", lambda argv: 23)
    r = CliRunner().invoke(app, ["lora", "train"])
    assert r.exit_code == 1


def test_cli_status(monkeypatch, fake_remote):
    r = CliRunner().invoke(app, ["lora", "status"])
    assert r.exit_code == 0, r.output
    cmd = fake_remote[0][-1]
    assert "tail -n 40 /workspace/.cm/train.log" in cmd
    assert "train.pid" in cmd


def test_cli_status_no_pod(monkeypatch, fake_remote):
    monkeypatch.setattr(cli, "_current_pod", lambda: None)
    r = CliRunner().invoke(app, ["lora", "status"])
    assert r.exit_code == 1
    assert "no running pod — run `cm pod up`" in r.output


# -- train_lora.sh simulation ---------------------------------------------------------
# A copy of the script with /workspace and /proc/1/environ rewritten into tmp_path,
# stub git/python3; exercises the real control flow without network or GPU.
STUB_GIT = '#!/bin/bash\nif [ "$1" = init ]; then mkdir -p "$3/.git"; fi\nexit 0\n'
STUB_PY3 = """#!/bin/bash
# python3 -m venv --system-site-packages DIR
dir="${@: -1}"
mkdir -p "$dir/bin"
cp "$CM_STUB_VENV_PY" "$dir/bin/python"
chmod +x "$dir/bin/python"
"""
STUB_VENV_PY = """#!/bin/bash
if [ "$1" = -m ]; then exit 0; fi   # pip install
if [ "$1" = run.py ]; then
  name="$(basename "$2" .yaml)"
  [ -z "$CM_STUB_FAIL" ] || exit 3
  mkdir -p "output/$name"
  if [ -z "$CM_STUB_NO_OUTPUT" ]; then echo weights > "output/$name/$name.safetensors"; fi
  exit 0
fi
exit 1
"""


def _sim_train(tmp_path, token: str | None = "hf_SIM", fail: bool = False, no_output: bool = False):
    ws = tmp_path / "ws"
    pod = ws / "cm" / "pod"
    pod.mkdir(parents=True)
    environ = tmp_path / "environ"
    environ.write_bytes(b"FOO=bar\0" + (f"HF_TOKEN={token}\0".encode() if token else b"") + b"RUNPOD_API_KEY=secret\0")
    text = TRAIN_SCRIPT.read_text().replace("/proc/1/environ", str(environ)).replace("/workspace", str(ws))
    (pod / "train_lora.sh").write_text(text)
    shutil.copy(REPO / "pod" / "versions.env", pod / "versions.env")
    (ws / "cm" / "training").mkdir()
    (ws / "cm" / "training" / "ohwxgreta_v1.yaml").write_text("x: 1\n")
    (ws / "dataset" / "ohwxgreta").mkdir(parents=True)
    (ws / "ComfyUI" / "models").mkdir(parents=True)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name, body in {"git": STUB_GIT, "python3": STUB_PY3, "venv_python": STUB_VENV_PY}.items():
        (bindir / name).write_text(body)
        (bindir / name).chmod(0o755)
    env = {"PATH": f"{bindir}:/usr/bin:/bin", "HOME": str(tmp_path), "CM_STUB_VENV_PY": str(bindir / "venv_python"), "CM_TRAIN_GRACE_S": "1"}
    if fail:
        env["CM_STUB_FAIL"] = "1"
    if no_output:
        env["CM_STUB_NO_OUTPUT"] = "1"
    r = subprocess.run(["bash", str(pod / "train_lora.sh"), "ohwxgreta_v1", "ohwxgreta"],
                       capture_output=True, text=True, env=env, timeout=40)
    return r, ws


def _wait_done(ws: Path) -> str:
    import time
    log = ws / ".cm" / "train.log"
    for _ in range(100):
        text = log.read_text() if log.exists() else ""
        if "DONE:" in text or "FAILED" in text:
            time.sleep(0.5)  # let the EXIT trap run
            return text
        time.sleep(0.1)
    raise AssertionError("training did not finish: " + (log.read_text() if log.exists() else ""))


def test_train_script_full_run_simulated(tmp_path):
    r, ws = _sim_train(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "started training" in r.stdout
    log = _wait_done(ws)
    assert "DONE:" in log
    assert (ws / "ComfyUI" / "models" / "loras" / "ohwxgreta_v1.safetensors").read_text() == "weights\n"
    assert not (ws / ".cm" / "busy").exists()
    assert not (ws / ".cm" / "train.pid").exists()
    assert (ws / "ai-toolkit" / ".git" / "cm-ref").read_text().strip() == \
        dict(ln.split("=", 1) for ln in (REPO / "pod" / "versions.env").read_text().splitlines()
             if ln and not ln.startswith("#"))["AI_TOOLKIT_COMMIT"]
    assert "secret" not in log + r.stdout + r.stderr


def test_train_script_failure_clears_busy(tmp_path):
    r, ws = _sim_train(tmp_path, fail=True)
    assert r.returncode != 0  # died within the launcher's grace period: reported to the operator
    assert "FAILED: training exited with code 3" in r.stderr
    assert "FAILED: training exited with code 3" in _wait_done(ws)
    assert not (ws / ".cm" / "busy").exists()
    assert not (ws / "ComfyUI" / "models" / "loras" / "ohwxgreta_v1.safetensors").exists()


def test_train_script_missing_output_is_failure(tmp_path):
    r, ws = _sim_train(tmp_path, no_output=True)
    assert r.returncode != 0
    assert "does not exist" in _wait_done(ws)
    assert not (ws / "ComfyUI" / "models" / "loras" / "ohwxgreta_v1.safetensors").exists()


def test_train_script_requires_hf_token(tmp_path):
    r, ws = _sim_train(tmp_path, token=None)
    assert r.returncode != 0
    assert "HF_TOKEN" in r.stderr and "license" in r.stderr
    assert not (ws / ".cm" / "busy").exists()
    assert not (ws / ".cm" / "train.pid").exists()
