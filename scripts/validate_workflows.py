"""Validate workflows/*.json against the pinned ComfyUI + Impact Pack/Subpack, on CPU.

Usage:  uv run python scripts/validate_workflows.py [--workdir DIR] [--keep]

In a work directory this script clones ComfyUI at ``COMFYUI_TAG`` and the two
Impact repos at the commits pinned in ``pod/versions.env``, creates a venv with
torch (from PyPI) and every repo's requirements, puts an *empty* placeholder
file for each ``pod/models.yaml`` entry (plus a dummy persona LoRA) into
``ComfyUI/models/``, starts ``main.py --cpu --port 18188`` and uploads a 64x64
input image. Each template is rendered with small sample values and sent to
``POST /prompt``: ComfyUI validates node classes, required inputs, input types,
enum values and that model filenames exist in its folder lists. HTTP 200 with
empty ``node_errors`` is OK; anything else is FAIL. After each accepted prompt
the queue is cleared and the run interrupted so nothing heavy executes (the
empty model files would fail to load anyway).

Prints one OK/FAIL line per workflow; exit code 1 on any FAIL, 2 when the
environment could not be set up (clone/install/server start).

``--workdir DIR`` reuses DIR between runs (repos and venv are only reinstalled
when a pin changes); without it a temp dir is used and deleted at exit unless
``--keep`` is given. The ComfyUI server is always stopped on exit.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from comfy_model.workflow import KINDS, PLACEHOLDERS, load_manifest, load_template, render  # noqa: E402

PORT = 18188
URL = f"http://127.0.0.1:{PORT}"
LORA_NAME = "ohwxgreta_v1.safetensors"
INPUT_IMAGE = "cm_validate.png"
STARTUP_TIMEOUT_S = 600
REPOS = {
    # dir under workdir (custom nodes live inside ComfyUI): (url, versions.env key)
    "ComfyUI": ("https://github.com/comfyanonymous/ComfyUI", "COMFYUI_TAG"),
    "ComfyUI/custom_nodes/ComfyUI-Impact-Pack": ("https://github.com/ltdrdata/ComfyUI-Impact-Pack", "IMPACT_PACK_COMMIT"),
    "ComfyUI/custom_nodes/ComfyUI-Impact-Subpack": ("https://github.com/ltdrdata/ComfyUI-Impact-Subpack", "IMPACT_SUBPACK_COMMIT"),
}


class SetupError(RuntimeError):
    pass


def log(msg: str) -> None:
    print(f"[validate] {msg}", flush=True)


def read_versions(path: Path = ROOT / "pod" / "versions.env") -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip("'\"")
    return out


def run(cmd: list[str], **kw) -> None:
    log("$ " + " ".join(str(c) for c in cmd))
    r = subprocess.run(cmd, **kw)
    if r.returncode != 0:
        raise SetupError(f"command failed ({r.returncode}): {' '.join(str(c) for c in cmd)}")


def sample_values(kind: str) -> dict:
    vals = {
        "prompt": "test", "negative": "blurry", "seed": 1,
        "width": 64, "height": 64, "batch_size": 1, "length": 5,
        "lora_name": LORA_NAME, "lora_strength": 0.9,
        "filename_prefix": "cm/validate", "ref_image": INPUT_IMAGE, "image": INPUT_IMAGE,
    }
    return {k: vals[k] for k in PLACEHOLDERS[kind]}


# -- setup -----------------------------------------------------------------------
def ensure_repo(dest: Path, url: str, ref: str) -> bool:
    """Shallow-fetch ``ref`` into ``dest``; returns True when (re)checked out."""
    stamp = dest / ".git" / "cm-ref"
    if stamp.is_file() and stamp.read_text().strip() == ref:
        return False
    log(f"fetching {url} @ {ref}")
    if not (dest / ".git").is_dir():
        dest.mkdir(parents=True, exist_ok=True)
        run(["git", "init", "-q", str(dest)])
        run(["git", "-C", str(dest), "remote", "add", "origin", url])
    run(["git", "-C", str(dest), "fetch", "-q", "--depth", "1", "origin", ref])
    run(["git", "-C", str(dest), "checkout", "-q", "-f", "FETCH_HEAD"])
    stamp.write_text(ref + "\n")
    return True


def ensure_venv(workdir: Path, repos: list[Path], pins: str) -> Path:
    venv = workdir / "venv"
    py = venv / "bin" / "python"
    stamp = venv / "cm-installed"
    if stamp.is_file() and stamp.read_text() == pins:
        return py
    uv = shutil.which("uv")
    if not py.exists():
        log(f"creating venv {venv}")
        if uv:
            run([uv, "venv", "-q", "--python", sys.executable, str(venv)])
        else:
            run([sys.executable, "-m", "venv", str(venv)])
    if uv:
        pip = [uv, "pip", "install", "--python", str(py)]
    else:
        pip = [str(py), "-m", "pip", "install", "-q", "--disable-pip-version-check"]
    # download.pytorch.org may be unreachable: take torch from PyPI (CUDA build, runs fine with --cpu)
    log("installing torch (PyPI) + requirements; first run downloads a few GB")
    run(pip + ["torch", "torchvision", "torchaudio"])
    for repo in repos:
        req = repo / "requirements.txt"
        if req.is_file():
            run(pip + ["-r", str(req)])
    stamp.write_text(pins)
    return py


def place_models(comfy: Path) -> None:
    models = comfy / "models"
    files = [(m.dest, m.file) for m in load_manifest(ROOT / "pod" / "models.yaml")]
    files.append(("loras", LORA_NAME))
    for dest, name in files:
        p = models / dest / name
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.touch()


# -- server ----------------------------------------------------------------------
def start_server(py: Path, comfy: Path, logfile: Path) -> subprocess.Popen:
    log(f"starting ComfyUI --cpu on port {PORT} (log: {logfile})")
    env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "RUNPOD_API_KEY", "HF_TOKEN")}
    out = open(logfile, "ab")
    return subprocess.Popen(
        [str(py), "main.py", "--cpu", "--listen", "127.0.0.1", "--port", str(PORT), "--disable-auto-launch"],
        cwd=comfy, env=env, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def stop_server(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    log("stopping ComfyUI")
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=10)
    except ProcessLookupError:
        pass


def wait_ready(http: httpx.Client, proc: subprocess.Popen, logfile: Path) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise SetupError(f"ComfyUI exited with {proc.returncode}; last log lines:\n{tail(logfile)}")
        try:
            if http.get("/system_stats", timeout=5).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise SetupError(f"ComfyUI not up after {STARTUP_TIMEOUT_S}s; last log lines:\n{tail(logfile)}")


def tail(path: Path, n: int = 40) -> str:
    try:
        return "\n".join(path.read_text(errors="replace").splitlines()[-n:])
    except FileNotFoundError:
        return "(no log)"


def import_failures(logfile: Path) -> list[str]:
    text = logfile.read_text(errors="replace").splitlines()
    return [ln.strip() for ln in text if "IMPORT FAILED" in ln or "Cannot import" in ln]


def upload_image(http: httpx.Client) -> None:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (128, 128, 128)).save(buf, format="PNG")
    r = http.post("/upload/image", files={"image": (INPUT_IMAGE, buf.getvalue(), "image/png")},
                  data={"overwrite": "true"})
    if r.status_code != 200 or r.json().get("name") != INPUT_IMAGE:
        raise SetupError(f"image upload failed: HTTP {r.status_code} {r.text[:300]}")


def drain(http: httpx.Client) -> None:
    """Drop anything queued and stop whatever is executing; wait until idle."""
    http.post("/queue", json={"clear": True})
    http.post("/interrupt")
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        q = http.get("/queue").json()
        if not q.get("queue_running") and not q.get("queue_pending"):
            return
        http.post("/interrupt")
        time.sleep(0.5)
    log("warning: queue did not become idle within 60s")


def describe_rejection(status: int, body) -> str:
    if not isinstance(body, dict):
        return f"HTTP {status}: {body!r}"[:2000]
    lines = [f"HTTP {status}"]
    err = body.get("error")
    if isinstance(err, dict):
        lines[0] += f": {err.get('message', '')} {err.get('details', '')}".rstrip()
    elif err:
        lines[0] += f": {err}"
    for nid, ne in sorted((body.get("node_errors") or {}).items()):
        cls = ne.get("class_type", "?") if isinstance(ne, dict) else "?"
        for e in (ne.get("errors", []) if isinstance(ne, dict) else [ne]):
            if isinstance(e, dict):
                lines.append(f"  node {nid} ({cls}): {e.get('message', '')}: {e.get('details', '')}")
            else:
                lines.append(f"  node {nid} ({cls}): {e}")
    return "\n".join(lines)


def validate(http: httpx.Client, kind: str) -> tuple[bool, str]:
    graph = render(load_template(kind, ROOT / "workflows"), sample_values(kind))
    r = http.post("/prompt", json={"prompt": graph, "client_id": f"cm-validate-{uuid.uuid4().hex[:8]}"})
    try:
        body = r.json()
    except json.JSONDecodeError:
        body = r.text
    ok = r.status_code == 200 and isinstance(body, dict) and not body.get("node_errors")
    if r.status_code == 200:
        drain(http)
    return ok, ("" if ok else describe_rejection(r.status_code, body))


# -- main ------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workdir", type=Path, help="reusable work dir (default: a fresh temp dir)")
    ap.add_argument("--keep", action="store_true", help="keep the temp work dir after the run")
    args = ap.parse_args(argv)

    temp = args.workdir is None
    workdir = Path(tempfile.mkdtemp(prefix="cm-validate-")) if temp else args.workdir.resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    proc = None
    # make `kill` behave like Ctrl-C so the finally block still stops the server
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    try:
        versions = read_versions()
        refs = {d: (url, versions[key]) for d, (url, key) in REPOS.items()}
        for d, (url, ref) in refs.items():
            ensure_repo(workdir / d, url, ref)
        pins = json.dumps({d: ref for d, (_, ref) in refs.items()}, sort_keys=True)
        py = ensure_venv(workdir, [workdir / d for d in refs], pins)
        comfy = workdir / "ComfyUI"
        place_models(comfy)

        logfile = workdir / "comfyui.log"
        logfile.write_bytes(b"")
        proc = start_server(py, comfy, logfile)
        with httpx.Client(base_url=URL, timeout=60, trust_env=False) as http:
            wait_ready(http, proc, logfile)
            for line in import_failures(logfile):
                log(f"custom node import problem: {line}")
            upload_image(http)
            results = {}
            for kind in KINDS:
                results[kind] = validate(http, kind)
    except (SetupError, httpx.HTTPError) as e:
        log(f"SETUP FAILED: {e}")
        return 2
    finally:
        stop_server(proc)
        if temp and not args.keep:
            shutil.rmtree(workdir, ignore_errors=True)
        elif temp:
            log(f"kept work dir {workdir}")

    print()
    for kind, (ok, detail) in results.items():
        print(f"{'OK  ' if ok else 'FAIL'} {kind}")
        if detail:
            print("     " + detail.replace("\n", "\n     "))
    failed = [k for k, (ok, _) in results.items() if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} workflows valid")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
