"""`cm` entry point: batch, export, pod (up|status|down|ssh), lora (prepare|train|status)."""
from __future__ import annotations

import shlex
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from comfy_model import lora as lora_mod
from comfy_model import remote, runpod_pod
from comfy_model.batch import run_batch
from comfy_model.comfy_client import ComfyClient, ComfyError
from comfy_model.config import ConfigError, Secrets, load_secrets, load_settings
from comfy_model.export import export_image
from comfy_model.profile import load_profile
from comfy_model.runpod_pod import PodError, PodInfo
from comfy_model.scenes import SceneError

app = typer.Typer(help="cm: ComfyUI generation on rented RunPod GPUs.", no_args_is_help=True)

NO_POD = "no running pod — run `cm pod up`"


@app.callback()
def main() -> None:
    """Root command group."""


def _make_client(url: str) -> ComfyClient:
    return ComfyClient(url)


def _configure() -> Secrets:
    """Load secrets and hand the RunPod API key (if any) to the SDK wrapper."""
    secrets = load_secrets()
    runpod_pod.configure(secrets)
    return secrets


def _redact(text: str, secrets: Secrets) -> str:
    for value in secrets.values():
        if value and len(value) >= 4:
            text = text.replace(value, "***")
    return text


def _current_pod() -> PodInfo | None:
    """``runpod_pod.current_pod()`` with every failure turned into a clean exit 1."""
    secrets: Secrets = Secrets()
    try:
        secrets = _configure()
        return runpod_pod.current_pod()
    except (ConfigError, PodError) as e:
        raise _fail(str(e)) from None
    except Exception as e:  # RunPod API / network
        raise _fail(_redact(f"cannot check the pod via the RunPod API: {type(e).__name__}: {e}", secrets)) from None


def _resolve_url(url: str | None) -> str | None:
    if url:
        return url
    pod = _current_pod()  # stale state (pod already gone) is cleared -> None
    return pod.comfy_url if pod else None


def _fail(message: str) -> typer.Exit:
    typer.echo(message, err=True)
    return typer.Exit(1)


@app.command()
def batch(
    kind: str = typer.Argument(..., help="face | dataset | photo | video"),
    scenes: Path = typer.Argument(..., help="Scene YAML file."),
    out: Optional[Path] = typer.Option(None, "--out", help="Output dir (default out/<date>-<kind>)."),
    ref: Optional[Path] = typer.Option(None, "--ref", help="Reference image (dataset)."),
    lora: Optional[str] = typer.Option(None, "--lora", help="LoRA file name on the pod (photo)."),
    strength: float = typer.Option(0.9, "--strength", help="LoRA strength (photo)."),
    url: Optional[str] = typer.Option(None, "--url", help="ComfyUI URL (default: running pod)."),
) -> None:
    """Generate every scene of SCENES; re-running skips outputs that already exist."""
    if kind not in ("face", "dataset", "photo", "video"):
        raise _fail(f"unknown kind {kind!r}; expected face, dataset, photo or video")
    base = _resolve_url(url)
    if base is None:
        raise _fail(NO_POD)
    out_dir = out or Path("out") / f"{date.today().isoformat()}-{kind}"

    def progress(scene_id: str, done: int, skipped: int, failed: int) -> None:
        typer.echo(f"{scene_id}: {done} done, {skipped} skipped, {failed} failed")

    try:
        profile = load_profile()
        client = _make_client(base)
        try:
            report = run_batch(
                kind, scenes, client, profile, out_dir,
                ref_image=ref, lora=lora, lora_strength=strength, on_scene=progress,
            )
        finally:
            close = getattr(client, "close", None)
            if close:
                close()
    except SceneError as e:
        raise _fail(str(e)) from None
    except ValueError as e:
        raise _fail(str(e)) from None
    except ComfyError as e:
        raise _fail(f"aborted: {e}") from None

    typer.echo(
        f"total: {len(report.done)} done, {len(report.skipped)} skipped, "
        f"{len(report.failed)} failed -> {out_dir}"
    )
    for name, msg in report.failed:
        typer.echo(f"  failed {name}: {msg}", err=True)
    if report.failed:
        raise typer.Exit(1)


@app.command()
def export(
    files: list[Path] = typer.Argument(..., help="Images (.png/.jpg/.webp) or videos (.mp4)."),
    to: Path = typer.Option(Path("export"), "--to", help="Destination directory."),
    grain: float = typer.Option(0.03, "--grain", help="Film grain strength (0 = none)."),
) -> None:
    """Strip metadata, add the AI label and grain; write posting-ready files."""
    missing = [f for f in files if not f.is_file()]
    if missing:
        raise _fail("file not found: " + ", ".join(str(f) for f in missing))
    for f in files:
        try:
            out = export_image(f, to, grain=grain)
        except (ValueError, OSError) as e:
            raise _fail(str(e)) from None
        typer.echo(str(out))


# -- cm pod ---------------------------------------------------------------------
pod_app = typer.Typer(help="Rent, inspect and release the RunPod GPU pod.", no_args_is_help=True)
app.add_typer(pod_app, name="pod")

SYNC_PATHS = [Path("pod"), Path("workflows"), Path("src/comfy_model/watchdog.py")]
REMOTE_DIR = "/workspace/cm/"
PREP_CMD = (
    "mkdir -p /workspace/cm && (command -v rsync >/dev/null || "
    "(export DEBIAN_FRONTEND=noninteractive; apt-get update -qq && apt-get install -y -qq rsync >/dev/null))"
)
BOOTSTRAP_CMD = "bash /workspace/cm/pod/bootstrap.sh"
# kill -0 alone could match an unrelated process reusing a pid from an old pidfile
# (the pidfile lives on the persistent network volume).
WATCHDOG_CHECK = (
    'pid=$(cat /workspace/.cm/watchdog.pid) && kill -0 "$pid" && grep -qa watchdog.py "/proc/$pid/cmdline"'
)
SSH_TIMEOUT_S = 180
COMFY_TIMEOUT_S = 600

# Indirection so tests can run the polling loops instantly.
_sleep = time.sleep
_clock = time.monotonic


class _UpError(RuntimeError):
    pass


def _clear_known_hosts() -> None:
    Path(remote.KNOWN_HOSTS).unlink(missing_ok=True)


def _remote_ok(argv: list[str], what: str) -> None:
    rc = remote.run(argv)
    if rc != 0:
        raise _UpError(f"{what} failed (exit {rc})")


def _wait_ssh(pod: PodInfo) -> None:
    deadline = _clock() + SSH_TIMEOUT_S
    while remote.run(remote.ssh_argv(pod, "true")) != 0:
        if _clock() >= deadline:
            raise _UpError(f"SSH to root@{pod.ssh_host}:{pod.ssh_port} not available after {SSH_TIMEOUT_S}s")
        _sleep(5)


def _wait_comfy(url: str) -> None:
    client = _make_client(url)
    try:
        deadline = _clock() + COMFY_TIMEOUT_S
        while not client.ping():
            if _clock() >= deadline:
                raise _UpError(
                    f"ComfyUI did not answer at {url} within {COMFY_TIMEOUT_S // 60} min "
                    "(log: /workspace/.cm/comfyui.out on the pod)"
                )
            _sleep(10)
    finally:
        close = getattr(client, "close", None)
        if close:
            close()


def _provision(pod_id: str, comfy_port: int) -> PodInfo:
    info = runpod_pod.wait_ready(pod_id, comfy_port=comfy_port)
    _clear_known_hosts()
    runpod_pod.save_state(info)  # lets `cm pod down` find the pod if this process dies
    typer.echo(f"pod {pod_id} started (ssh root@{info.ssh_host} -p {info.ssh_port}); bootstrapping ...")
    _wait_ssh(info)
    _remote_ok(remote.ssh_argv(info, PREP_CMD), "preparing /workspace/cm on the pod")
    _remote_ok(remote.rsync_argv(info, SYNC_PATHS, REMOTE_DIR), "rsync to the pod")
    _remote_ok(remote.ssh_argv(info, BOOTSTRAP_CMD), "pod bootstrap")
    if remote.run(remote.ssh_argv(info, WATCHDOG_CHECK)) != 0:
        raise _UpError("watchdog is not running on the pod (see /workspace/.cm/watchdog.out); "
                       "refusing to leave an unsupervised pod")
    typer.echo("watchdog running; waiting for ComfyUI ...")
    _wait_comfy(info.comfy_url)
    return info


def _teardown(pod_id: str, secrets: Secrets) -> None:
    try:
        runpod_pod.terminate(pod_id)
    except Exception as e:
        typer.echo(_redact(
            f"FAILED to terminate pod {pod_id} ({type(e).__name__}: {e}); it may still be billing — "
            "run `cm pod down` or terminate it in the RunPod console", secrets), err=True)
        return
    runpod_pod.clear_state()
    _clear_known_hosts()
    typer.echo(f"terminated pod {pod_id}", err=True)


@pod_app.command("up")
def pod_up() -> None:
    """Create the pod, sync files, bootstrap ComfyUI + watchdog, wait until ComfyUI answers."""
    try:
        settings = load_settings()
        secrets = _configure()
    except ConfigError as e:
        raise _fail(str(e)) from None
    missing = [str(p) for p in SYNC_PATHS if not p.exists()]
    if missing:
        raise _fail("run `cm pod up` from the repository root; missing: " + ", ".join(missing))
    existing = _current_pod()
    if existing:
        raise _fail(f"pod {existing.id} already running: {existing.comfy_url} (use it, or `cm pod down`)")

    try:
        pod_id = runpod_pod.create(settings, secrets)
    except ConfigError as e:
        raise _fail(str(e)) from None
    except Exception as e:
        raise _fail(_redact(f"pod creation failed: {type(e).__name__}: {e}", secrets)) from None
    typer.echo(f"created pod {pod_id}; waiting for it to start ...")

    try:
        info = _provision(pod_id, settings.comfy_port)
    except (Exception, KeyboardInterrupt) as e:
        msg = str(e) if isinstance(e, _UpError) else f"{type(e).__name__}: {e}"
        typer.echo(_redact(f"error: {msg}", secrets), err=True)
        _teardown(pod_id, secrets)
        raise typer.Exit(1)

    runpod_pod.save_state(info)
    typer.echo(f"ComfyUI: {info.comfy_url}")
    typer.echo(f"ssh: cm pod ssh  (root@{info.ssh_host} -p {info.ssh_port})")
    typer.echo(f"auto-off after {settings.idle_timeout_min:g} min idle / {settings.max_runtime_h:g} h max")


@pod_app.command("status")
def pod_status() -> None:
    """Show the running pod (clears stale state if the pod is gone)."""
    pod = _current_pod()
    if pod is None:
        typer.echo(NO_POD)
        return
    data = runpod_pod.load_state() or {}
    typer.echo(f"pod {pod.id} running (since {data.get('created_at', '?')})")
    client = _make_client(pod.comfy_url)
    try:
        up = client.ping()
    finally:
        close = getattr(client, "close", None)
        if close:
            close()
    typer.echo(f"ComfyUI: {pod.comfy_url} ({'up' if up else 'not responding'})")
    typer.echo(f"ssh: root@{pod.ssh_host} -p {pod.ssh_port}")


@pod_app.command("down")
def pod_down() -> None:
    """Terminate the pod and delete the local state."""
    pod = _current_pod()
    if pod is None:
        typer.echo("no running pod")
        return
    try:
        runpod_pod.terminate(pod.id)
    except Exception as e:
        raise _fail(_redact(
            f"terminate failed for pod {pod.id}: {type(e).__name__}: {e}; state kept — retry `cm pod down`",
            load_secrets())) from None
    runpod_pod.clear_state()
    _clear_known_hosts()
    typer.echo(f"terminated pod {pod.id}")


@pod_app.command("ssh")
def pod_ssh() -> None:
    """Open an interactive shell on the pod."""
    pod = _current_pod()
    if pod is None:
        raise _fail(NO_POD)
    raise typer.Exit(remote.run(remote.ssh_argv(pod)))


# -- cm lora --------------------------------------------------------------------
lora_app = typer.Typer(help="Prepare a LoRA dataset and train it on the pod.", no_args_is_help=True)
app.add_typer(lora_app, name="lora")

LORA_LOCAL_CONFIG_DIR = Path(".cm/training")
TRAIN_SYNC_PATHS = [Path("pod")]
# The watchdog's hard cap counts from pod start, so a first training run (~35 GB of
# downloads + install + 2000 steps, up to ~3 h) must start on a young pod.
MAX_POD_AGE_MIN = 60


def _pod_age_min(pod_id: str) -> float | None:
    """Minutes since the pod was created, from .cm/pod.json (None if unknown)."""
    try:
        data = runpod_pod.load_state()
        if not data or data.get("id") != pod_id:
            return None
        created = datetime.fromisoformat(str(data["created_at"]))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - created).total_seconds() / 60
    except (PodError, KeyError, ValueError, TypeError):
        return None


@lora_app.command("prepare")
def lora_prepare(
    src: Path = typer.Argument(..., help="Dataset batch output dir, after deleting the bad images."),
    to: Optional[Path] = typer.Option(None, "--to", help="Destination (default dataset/<trigger>)."),
) -> None:
    """Number the surviving images and write caption files for training."""
    try:
        profile = load_profile()
        dest = to or Path("dataset") / profile.trigger
        count = lora_mod.prepare_dataset(src, dest, profile)
    except (ValueError, OSError) as e:
        raise _fail(str(e)) from None
    typer.echo(f"prepared {count} images + captions in {dest}")
    typer.echo("next: cm pod up (if no pod is running), then cm lora train")


def _remote_step(argv: list[str], what: str) -> None:
    rc = remote.run(argv)
    if rc != 0:
        raise _fail(f"{what} failed (exit {rc})")


@lora_app.command("train")
def lora_train(
    version: int = typer.Option(1, "--version", min=1, help="LoRA version; output is <trigger>_v<N>."),
    force: bool = typer.Option(False, "--force", help=f"Train even if the pod is older than {MAX_POD_AGE_MIN} min."),
) -> None:
    """Upload dataset + config, start ai-toolkit training detached on the pod (~2 h)."""
    try:
        profile = load_profile()
        hf_token = load_secrets().get("HF_TOKEN")
    except (ValueError, ConfigError) as e:
        raise _fail(str(e)) from None
    if not hf_token:
        raise _fail(
            "HF_TOKEN is missing: FLUX.1-dev is a gated model. Accept the FLUX.1-dev license on "
            "Hugging Face (black-forest-labs/FLUX.1-dev), create a read token and put "
            "HF_TOKEN=... in .env; then recreate the pod (`cm pod down`, `cm pod up`)."
        )
    dataset = Path("dataset") / profile.trigger
    n_images = sum(1 for p in dataset.glob("img_*") if p.suffix.lower() in lora_mod.IMAGE_EXTS) if dataset.is_dir() else 0
    if n_images < lora_mod.MIN_IMAGES:
        raise _fail(f"no prepared dataset in {dataset} ({n_images} images): run `cm lora prepare <dataset-output-dir>`")
    if not all(p.exists() for p in TRAIN_SYNC_PATHS):
        raise _fail("run `cm lora train` from the repository root; missing: pod/")
    try:
        config_text = lora_mod.render_training_config(profile, version)
    except ValueError as e:
        raise _fail(str(e)) from None

    pod = _current_pod()
    if pod is None:
        raise _fail(NO_POD)

    age = _pod_age_min(pod.id)
    if age is not None and age > MAX_POD_AGE_MIN and not force:
        raise _fail(
            f"the pod has been up {age:.0f} min; training needs up to ~3 h and the pod auto-stops "
            "at 4 h from its start. Run `cm pod down && cm pod up` first (or pass --force)."
        )

    name = lora_mod.run_name(profile, version)
    config_file = LORA_LOCAL_CONFIG_DIR / f"{name}.yaml"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(config_text, encoding="utf-8")

    trig = shlex.quote(profile.trigger)
    prep = (f"mkdir -p {lora_mod.REMOTE_DATASET_ROOT} {lora_mod.REMOTE_TRAINING_DIR} /workspace/.cm "
            f"&& rm -rf {lora_mod.REMOTE_DATASET_ROOT}/{trig}")  # no stale images from an older prepare
    typer.echo(f"uploading {n_images} images + config to the pod ...")
    _remote_step(remote.ssh_argv(pod, prep), "preparing the pod directories")
    _remote_step(remote.rsync_argv(pod, TRAIN_SYNC_PATHS, REMOTE_DIR), "rsync of pod/ scripts")
    _remote_step(remote.rsync_argv(pod, [dataset], lora_mod.REMOTE_DATASET_ROOT + "/"), "rsync of the dataset")
    _remote_step(remote.rsync_argv(pod, [config_file], lora_mod.REMOTE_TRAINING_DIR + "/"), "rsync of the training config")
    _remote_step(remote.ssh_argv(pod, lora_mod.train_command(profile.trigger, version)), "starting training")
    typer.echo(f"training {name} started on the pod (about 2 h; the pod stays up while it runs)")
    typer.echo("note: the pod hard-stops 4 h after its start (watchdog), whatever is running")
    typer.echo("follow progress: cm lora status")
    typer.echo(f"when done the LoRA is /workspace/ComfyUI/models/loras/{name}.safetensors (cm batch photo ... --lora {name}.safetensors)")


@lora_app.command("status")
def lora_status() -> None:
    """Show the last 40 lines of the training log and whether training is running."""
    pod = _current_pod()
    if pod is None:
        raise _fail(NO_POD)
    rc = remote.run(remote.ssh_argv(pod, lora_mod.status_command()))
    if rc != 0:
        raise _fail(f"ssh failed (exit {rc})")
