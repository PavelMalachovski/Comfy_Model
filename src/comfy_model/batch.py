"""Idempotent batch generation: scene file -> ComfyUI -> ``out_dir/<scene>_<nn>.<ext>``.

The whole scene file (and every input image) is validated before the first
prompt is queued. Outputs that already exist on disk are skipped, so an
interrupted run can simply be repeated: numbering is stable (``n`` is the
1-based index within the scene, independent of what ran before) and no GPU work
is repeated.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from comfy_model.comfy_client import ComfyClient, ComfyError, OutputFile
from comfy_model.profile import Profile
from comfy_model.scenes import ASPECTS, VIDEO_ASPECTS, Scene, load_scenes
from comfy_model.workflow import KINDS, load_template, render

VIDEO_LENGTH = 121
MANIFEST_NAME = "manifest.jsonl"


@dataclass
class BatchReport:
    done: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


def _ext(kind: str) -> str:
    return "mp4" if kind == "video" else "png"


def _pick(files: list[OutputFile], ext: str) -> list[OutputFile]:
    """Prefer files with the expected extension (e.g. skip preview images of a video run)."""
    matching = [f for f in files if f.filename.lower().endswith(f".{ext}")]
    return matching or files


def _resolve_image(scene: Scene, scenes_dir: Path) -> Path:
    p = Path(scene.image or "")
    return p if p.is_absolute() else scenes_dir / p


def _upload(client: ComfyClient, path: Path, cache: dict[Path, str]) -> str:
    """Upload once per file under ``<sha256[:12]>-<basename>`` (uploads overwrite by name)."""
    if path not in cache:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        cache[path] = client.upload_image(path, name=f"{digest}-{path.name}")
    return cache[path]


def run_batch(
    kind: str,
    scenes_path: Path,
    client: ComfyClient,
    profile: Profile,
    out_dir: Path,
    *,
    ref_image: Path | None = None,
    lora: str | None = None,
    lora_strength: float = 0.9,
    on_scene: Callable[[str, int, int, int], None] | None = None,
) -> BatchReport:
    """Run every scene of ``scenes_path``; ``on_scene(id, done, skipped, failed)`` fires per scene.

    Raises ``SceneError`` (invalid file) or ``ValueError`` (missing ``--lora`` /
    ``--ref`` / input image) before anything is queued. A ``ComfyError`` with
    ``is_validation`` (e.g. a model missing on the volume) aborts the batch; any
    other ``ComfyError`` is recorded in ``failed`` and the batch continues.
    """
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}; expected one of: {', '.join(KINDS)}")
    if kind == "photo" and not lora:
        raise ValueError("photo batches need a trained LoRA: pass --lora <file in models/loras>")
    if kind == "dataset" and (ref_image is None or not Path(ref_image).is_file()):
        raise ValueError(f"dataset batches need a reference image: pass --ref <image> (got {ref_image})")

    scenes_path = Path(scenes_path)
    scenes = load_scenes(scenes_path, kind)  # type: ignore[arg-type]

    images: dict[str, Path] = {}
    if kind == "video":
        problems = []
        for s in scenes:
            p = _resolve_image(s, scenes_path.parent)
            if p.is_file():
                images[s.id] = p
            else:
                problems.append(f"scene '{s.id}': image not found: {p}")
        if problems:
            raise ValueError("\n".join(problems))

    template = load_template(kind)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = _ext(kind)
    report = BatchReport()
    uploads: dict[Path, str] = {}

    def prompt_for(s: Scene) -> str:
        if kind in ("face", "photo"):
            return profile.photo_prompt(s.prompt, use_trigger=(kind == "photo"))
        return s.prompt  # dataset (Kontext edit instruction) and video: verbatim

    def build(s: Scene, prompt: str, seed: int) -> dict:
        values: dict = {"prompt": prompt, "seed": seed, "filename_prefix": f"cm/{s.id}"}
        if kind in ("face", "photo", "video"):
            w, h = (VIDEO_ASPECTS if kind == "video" else ASPECTS)[s.aspect]
            values.update(width=w, height=h)
        if kind == "face":
            values["batch_size"] = s.count
        elif kind == "photo":
            values.update(lora_name=lora, lora_strength=lora_strength)
        elif kind == "dataset":
            values["ref_image"] = _upload(client, Path(ref_image), uploads)  # type: ignore[arg-type]
        elif kind == "video":
            values.update(
                image=_upload(client, images[s.id], uploads),
                negative=profile.video_negative,
                length=VIDEO_LENGTH,
            )
        return render(template, values)

    def save(s: Scene, n: int, seed: int, prompt: str, f: OutputFile, dest: Path, manifest) -> None:
        client.download(f, dest)
        report.done.append(dest)
        manifest.write(json.dumps({
            "scene_id": s.id, "n": n, "seed": seed, "prompt": prompt, "file": dest.name, "kind": kind,
        }, ensure_ascii=False) + "\n")
        manifest.flush()

    with (out_dir / MANIFEST_NAME).open("a", encoding="utf-8") as manifest:
        for s in scenes:
            dests = {n: out_dir / f"{s.id}_{n:02d}.{ext}" for n in range(1, s.count + 1)}
            counts = (len(report.done), len(report.skipped), len(report.failed))
            report.skipped.extend(p for p in dests.values() if p.exists())
            todo = [n for n, p in dests.items() if not p.exists()]
            prompt = prompt_for(s)

            if todo and kind == "face":
                # One queue per scene (batch_size=count); history order maps to n=1..count.
                seed = s.seed if s.seed is not None else random.randrange(2**32)
                try:
                    entry = client.wait(client.queue(build(s, prompt, seed)))
                    outs = _pick(client.outputs(entry), ext)
                    for n in todo:
                        if n - 1 < len(outs):
                            save(s, n, seed, prompt, outs[n - 1], dests[n], manifest)
                        else:
                            report.failed.append((f"{s.id}_{n:02d}", f"ComfyUI returned {len(outs)} of {s.count} images"))
                except (ComfyError, TimeoutError) as e:
                    if isinstance(e, ComfyError) and e.is_validation:
                        raise
                    report.failed.append((f"{s.id}_{todo[0]:02d}", str(e)))
            else:
                for n in todo:
                    seed = s.seed + n - 1 if s.seed is not None else random.randrange(2**32)
                    try:
                        entry = client.wait(client.queue(build(s, prompt, seed)))
                        outs = _pick(client.outputs(entry), ext)
                        if not outs:
                            raise ComfyError(f"ComfyUI returned no output for {s.id}_{n:02d}")
                        save(s, n, seed, prompt, outs[0], dests[n], manifest)
                    except (ComfyError, TimeoutError) as e:
                        if isinstance(e, ComfyError) and e.is_validation:
                            raise
                        report.failed.append((f"{s.id}_{n:02d}", str(e)))

            if on_scene:
                on_scene(
                    s.id,
                    len(report.done) - counts[0],
                    len(report.skipped) - counts[1],
                    len(report.failed) - counts[2],
                )
    return report
