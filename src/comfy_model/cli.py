"""`cm` entry point. Later tasks attach sub-apps (pod, lora, export)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

import typer

from comfy_model.batch import run_batch
from comfy_model.comfy_client import ComfyClient, ComfyError
from comfy_model.export import export_image
from comfy_model.profile import load_profile
from comfy_model.scenes import SceneError

app = typer.Typer(help="cm: ComfyUI generation on rented RunPod GPUs.", no_args_is_help=True)

POD_STATE = Path(".cm/pod.json")
NO_POD = "no running pod — run `cm pod up`"


@app.callback()
def main() -> None:
    """Root command group."""


def _make_client(url: str) -> ComfyClient:
    return ComfyClient(url)


def _resolve_url(url: str | None) -> str | None:
    if url:
        return url
    # Task 8 replaces this direct read with current_pod().
    try:
        data = json.loads(POD_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get("comfy_url") if isinstance(data, dict) else None
    return value if isinstance(value, str) and value else None


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
