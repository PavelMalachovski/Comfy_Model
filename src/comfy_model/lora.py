"""LoRA dataset preparation and the ai-toolkit training config / remote command."""
from __future__ import annotations

import json
import re
import shlex
import shutil
from pathlib import Path
from typing import Any

import yaml

from comfy_model.profile import Profile

MIN_IMAGES = 15
MAX_IMAGES = 60
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")
MANIFEST_NAME = "manifest.jsonl"
DEFAULT_CAPTION = "a photo of a woman"
TEMPLATE_PATH = Path("training/lora_flux.yaml")
# Every scenes/dataset.yaml instruction starts with this Kontext edit phrase; it says
# nothing about the image, so it is not part of the training caption.
_KONTEXT_PREFIX = re.compile(r"^keep the same woman's face and identity,\s*", re.IGNORECASE)

REMOTE_DATASET_ROOT = "/workspace/dataset"
REMOTE_TRAINING_DIR = "/workspace/cm/training"
REMOTE_TRAIN_SCRIPT = "/workspace/cm/pod/train_lora.sh"
TRAIN_LOG = "/workspace/.cm/train.log"
TRAIN_PID = "/workspace/.cm/train.pid"

# Sample images rendered during training (trigger prepended via Profile.photo_prompt).
SAMPLE_SCENES = (
    "standing on a street in Vilnius in autumn, looking at the camera",
    "sitting in a cafe with a laptop, smiling",
    "walking along a beach in a casual summer dress",
)


def _caption_text(prompt: str) -> str:
    """Manifest prompt -> caption body: whitespace collapsed, Kontext prefix dropped."""
    return _KONTEXT_PREFIX.sub("", " ".join(prompt.split())).strip()


def _manifest_prompts(src_dir: Path) -> dict[str, str]:
    """file name -> caption text from the dataset batch manifest (last entry wins)."""
    path = src_dir / MANIFEST_NAME
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
            out[entry["file"]] = _caption_text(str(entry["prompt"]))
        except (ValueError, KeyError, TypeError):
            continue  # blank / truncated / foreign line
    return out


def prepare_dataset(src_dir: Path, dest_dir: Path, profile: Profile) -> int:
    """Copy the curated images of ``src_dir`` to ``dest_dir/img_NNN.<ext>`` with a
    ``img_NNN.txt`` caption each. Returns the image count (15-60 or ValueError)."""
    src_dir, dest_dir = Path(src_dir), Path(dest_dir)
    if not src_dir.is_dir():
        raise ValueError(f"source directory not found: {src_dir}")
    images = sorted(
        (p for p in src_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS),
        key=lambda p: p.name,
    )
    if not MIN_IMAGES <= len(images) <= MAX_IMAGES:
        raise ValueError(
            f"found {len(images)} image(s) in {src_dir}; a LoRA dataset needs "
            f"{MIN_IMAGES}-{MAX_IMAGES} (delete more of the weak ones, or generate more)"
        )
    prompts = _manifest_prompts(src_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for old in dest_dir.glob("img_*"):  # earlier run: keep numbering consistent
        if old.is_file():
            old.unlink()
    for i, img in enumerate(images, start=1):
        stem = f"img_{i:03d}"
        shutil.copyfile(img, dest_dir / f"{stem}{img.suffix.lower()}")
        caption = f"{profile.trigger}, {prompts.get(img.name) or DEFAULT_CAPTION}"
        (dest_dir / f"{stem}.txt").write_text(caption, encoding="utf-8")
    return len(images)


def run_name(profile: Profile, version: int) -> str:
    return f"{profile.trigger}_v{version}"


def _fill(node: Any, values: dict[str, str], prompts: list[str]) -> Any:
    if isinstance(node, dict):
        return {k: _fill(v, values, prompts) for k, v in node.items()}
    if isinstance(node, list):
        return [_fill(v, values, prompts) for v in node]
    if isinstance(node, str):
        if node == "{{sample_prompts}}":
            return list(prompts)
        for key, val in values.items():
            node = node.replace("{{" + key + "}}", val)
    return node


def render_training_config(profile: Profile, version: int, template: Path = TEMPLATE_PATH) -> str:
    """ai-toolkit YAML for ``<trigger>_v<version>``, from ``training/lora_flux.yaml``."""
    try:
        raw = yaml.safe_load(Path(template).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"training template not found: {template}") from None
    values = {"name": run_name(profile, version), "trigger": profile.trigger}
    prompts = [profile.photo_prompt(s, use_trigger=True) for s in SAMPLE_SCENES]
    return yaml.safe_dump(_fill(raw, values, prompts), sort_keys=False, allow_unicode=True)


def train_command(trigger: str, version: int) -> str:
    """Remote shell command that launches (detached) training; returns quickly."""
    name = f"{trigger}_v{version}"
    return f"bash {REMOTE_TRAIN_SCRIPT} {shlex.quote(name)} {shlex.quote(trigger)}"


def status_command() -> str:
    return (
        f"tail -n 40 {TRAIN_LOG} 2>/dev/null || echo '(no training log yet)'; "
        f'pid=$(cat {TRAIN_PID} 2>/dev/null); '
        'if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && grep -qa train_lora.sh "/proc/$pid/cmdline" 2>/dev/null; '
        'then echo "== training RUNNING (pid $pid)"; else echo "== training not running"; fi'
    )
