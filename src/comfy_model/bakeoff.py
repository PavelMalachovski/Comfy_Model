"""Blind model comparison on the same prompts: ``cm bakeoff run`` and ``cm bakeoff sheets``."""
from __future__ import annotations

import json
import random
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from PIL import Image, ImageDraw, ImageFont, ImageOps

from comfy_model.batch import DEFAULT_WAIT_TIMEOUT_S, BUSY_MESSAGE, BatchReport
from comfy_model.comfy_client import ComfyClient, ComfyError
from comfy_model.profile import load_profile
from comfy_model.safety import check_prompt
from comfy_model.scenes import Scene, load_scenes
from comfy_model.workflow import TemplateError, render

BAKEOFF_MANIFEST = Path("pod/bakeoff_models.yaml")
BAKEOFF_SCENES = Path("scenes/bakeoff.yaml")
BAKEOFF_PROFILE = Path("character/bakeoff_profile.yaml")


@dataclass(frozen=True)
class Candidate:
    """A model under test; ``width``/``height`` is the size of its first sampling pass."""

    name: str
    width: int
    height: int


CANDIDATES: tuple[Candidate, ...] = (
    Candidate("qwen_2512", 1024, 1280),
    Candidate("z_image", 1024, 1280),
    Candidate("z_image_turbo", 1024, 1280),
    Candidate("hidream_o1", 1792, 2304),
)
GRAPH_DIR = Path("workflows/bakeoff")
GRAPH_PLACEHOLDERS = {"prompt", "seed", "width", "height", "filename_prefix", "filename_prefix_face"}


def load_graph(name: str, directory: Path = GRAPH_DIR) -> dict:
    """The ComfyUI API-format graph of candidate ``name``."""
    if name not in {c.name for c in CANDIDATES}:
        raise TemplateError(f"unknown candidate {name!r}")
    path = Path(directory) / f"{name}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise TemplateError(f"bake-off graph not found: {path}") from None


MAX_CONSECUTIVE_FAILURES = 3
NO_FACE_MAX_PX = 64  # FaceDetailer returns a 64x64 black image when it detects no face
_FACE_MARK = "_face_"
_FRAME_W, _FRAME_H = 512, 640
_FACE_TILE = 512


def _checked_prompts(scenes: list[Scene]) -> dict[str, str]:
    """scene id -> full prompt; raises ``ValueError`` before anything can be queued."""
    profile = load_profile(BAKEOFF_PROFILE)
    prompts = {s.id: profile.photo_prompt(s.prompt, use_trigger=False) for s in scenes}
    problems = [f"{s.id}: {v}" for s in scenes for v in check_prompt(prompts[s.id], s.tier)]
    if problems:
        raise ValueError("bake-off prompts rejected:\n" + "\n".join(problems))
    return prompts


def _save_crop(client: ComfyClient, f, dest: Path) -> bool:
    """Download a face crop; False (nothing kept) if FaceDetailer found no face."""
    client.download(f, dest)
    with Image.open(dest) as im:
        found = max(im.size) > NO_FACE_MAX_PX
    if not found:
        dest.unlink()
    return found


def run_bakeoff(
    names: Sequence[str],
    client: ComfyClient,
    out_dir: Path,
    *,
    limit: int | None = None,
    on_item: Callable[[str], None] | None = None,
) -> BatchReport:
    """Render every scene for each candidate; finished frames are skipped on a re-run.

    ``limit`` caps new frames per candidate. A ComfyUI validation error (e.g. a model
    missing on the volume) propagates; a timeout stops the run with ``report.aborted``.
    """
    by_name = {c.name: c for c in CANDIDATES}
    unknown = [n for n in names if n not in by_name]
    if unknown:
        raise ValueError(f"unknown candidate(s): {', '.join(unknown)} (expected: {', '.join(by_name)})")
    scenes = load_scenes(BAKEOFF_SCENES, "face")
    prompts = _checked_prompts(scenes)
    report = BatchReport()
    streak = 0  # consecutive failed frames: a repeating error must not burn GPU on all 96

    for name in names:
        c = by_name[name]
        graph = load_graph(name)
        cand_dir = Path(out_dir) / name
        cand_dir.mkdir(parents=True, exist_ok=True)
        new = 0
        with (cand_dir / "manifest.jsonl").open("a", encoding="utf-8") as manifest:
            for s in scenes:
                for n in range(1, s.count + 1):
                    stem = f"{s.id}_{n:02d}"
                    dest = cand_dir / f"{stem}.png"
                    if dest.exists():
                        report.skipped.append(dest)
                        continue
                    if limit is not None and new >= limit:
                        continue
                    new += 1
                    item = f"{name}/{stem}"
                    if on_item:
                        on_item(item)
                    seed = s.seed + n - 1
                    workflow = render(graph, {
                        "prompt": prompts[s.id], "seed": seed, "width": c.width, "height": c.height,
                        "filename_prefix": f"bakeoff/{name}/{stem}",
                        "filename_prefix_face": f"bakeoff/{name}/{stem}{_FACE_MARK.rstrip('_')}",
                    })
                    try:
                        entry = client.wait(client.queue(workflow), timeout_s=DEFAULT_WAIT_TIMEOUT_S)
                        outs = client.outputs(entry)
                        full = [f for f in outs if _FACE_MARK not in f.filename]
                        crops = [f for f in outs if _FACE_MARK in f.filename]
                        if not full:
                            raise ComfyError(f"ComfyUI returned no image for {item}")
                        # The full image goes last: its presence marks the frame as finished.
                        has_face = bool(crops) and _save_crop(client, crops[0], cand_dir / f"{stem}_face.png")
                        client.download(full[0], dest)
                    except TimeoutError as e:
                        report.failed.append((item, str(e)))
                        report.aborted = BUSY_MESSAGE.format(item=item, timeout=DEFAULT_WAIT_TIMEOUT_S)
                        return report
                    except ComfyError as e:
                        if e.is_validation:
                            raise
                        report.failed.append((item, str(e)))
                        streak += 1
                        if streak >= MAX_CONSECUTIVE_FAILURES:
                            report.aborted = (
                                f"{streak} frames in a row failed, last: {e}. Fix the cause or check that "
                                "the pod is alive (`cm pod status`), then re-run; finished frames are skipped."
                            )
                            return report
                        continue
                    streak = 0
                    report.done.append(dest)
                    manifest.write(json.dumps({
                        "candidate": name, "scene_id": s.id, "n": n, "seed": seed, "tier": s.tier,
                        "prompt": prompts[s.id], "file": dest.name, "no_face": not has_face,
                    }, ensure_ascii=False) + "\n")
                    manifest.flush()
    return report


def _letters(out_dir: Path) -> dict[str, str]:
    """letter -> candidate, kept in ``key.json``; candidates seen later get new letters."""
    present = [c.name for c in CANDIDATES if any((out_dir / c.name).glob("*.png"))]
    if not present:
        raise ValueError(f"no frames found under {out_dir}; run `cm bakeoff run` first")
    path = out_dir / "key.json"
    key: dict[str, str] = json.loads(path.read_text()) if path.exists() else {}
    new = [n for n in present if n not in key.values()]
    random.SystemRandom().shuffle(new)
    free = [ch for ch in string.ascii_uppercase if ch not in key]
    key.update(zip(free, new))
    path.write_text(json.dumps(dict(sorted(key.items())), indent=2) + "\n")
    return key


def _tile(path: Path, size: tuple[int, int], label: str, missing_text: str, *, scale: bool = True) -> Image.Image:
    font = ImageFont.load_default(size=28)
    if path.is_file():
        with Image.open(path) as src:
            rgb = src.convert("RGB")
        if scale:
            tile = ImageOps.pad(rgb, size, method=Image.LANCZOS, color=(90, 90, 90))
        else:  # crops differ in size: keep 100% pixels on a grey cell
            tile = Image.new("RGB", size, (90, 90, 90))
            tile.paste(rgb, (0, 0))
    else:
        tile = Image.new("RGB", size, (90, 90, 90))
        ImageDraw.Draw(tile).text((16, size[1] // 2), missing_text, fill="white", font=font)
    draw = ImageDraw.Draw(tile)
    draw.rectangle((0, 0, 48, 40), fill="black")
    draw.text((10, 4), label, fill="white", font=font)
    return tile


def _sheet(tiles: list[list[Image.Image]], dest: Path) -> None:
    w, h = tiles[0][0].size
    sheet = Image.new("RGB", (w * len(tiles[0]), h * len(tiles)), "white")
    for r, row in enumerate(tiles):
        for c, tile in enumerate(row):
            sheet.paste(tile, (c * w, r * h))
    sheet.save(dest, "JPEG", quality=95, subsampling=0)  # full chroma: sheets are for judging skin


def _crop_size(paths: list[Path]) -> tuple[int, int]:
    """The largest crop of a sheet, so crops are shown without shrinking."""
    sizes = []
    for p in paths:
        if p.is_file():
            with Image.open(p) as im:
                sizes.append(im.size)
    if not sizes:
        return (_FACE_TILE, _FACE_TILE)
    return (max(s[0] for s in sizes), max(s[1] for s in sizes))


def make_sheets(out_dir: Path) -> Path:
    """One frame sheet and one face-crop sheet per scene, labelled only by letter."""
    out_dir = Path(out_dir)
    key = _letters(out_dir)
    sheets = out_dir / "sheets"
    sheets.mkdir(exist_ok=True)
    letters = sorted(key)
    for s in load_scenes(BAKEOFF_SCENES, "face"):
        stems = [f"{s.id}_{n:02d}" for n in range(1, s.count + 1)]
        _sheet([[_tile(out_dir / key[ch] / f"{st}.png", (_FRAME_W, _FRAME_H), ch, "no frame") for ch in letters]
                for st in stems], sheets / f"{s.id}.jpg")
        crops = [out_dir / key[ch] / f"{st}_face.png" for st in stems for ch in letters]
        size = _crop_size(crops)
        _sheet([[_tile(out_dir / key[ch] / f"{st}_face.png", size, ch, "no face", scale=False) for ch in letters]
                for st in stems], sheets / f"{s.id}_faces.jpg")
    return sheets
