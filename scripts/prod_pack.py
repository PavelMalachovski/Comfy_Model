"""Build ready-to-post folders out/prod/dayN/<name>.jpg from scenes/prod_days.yaml.

Raw renders get the phone finish (scripts/phone_finish.py, --hdr 0.5). Sources stay where they are.
    .venv/bin/python scripts/prod_pack.py [day1 day2 ...] [--force]
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from phone_finish import finish  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROD = ROOT / "out" / "prod"


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    plan = yaml.safe_load((ROOT / "scenes" / "prod_days.yaml").read_text())
    for day, items in plan.items():
        if args and day not in args:
            continue
        dest = PROD / day
        dest.mkdir(parents=True, exist_ok=True)
        for i, (name, cands) in enumerate(items.items()):
            src = next((ROOT / c for c in cands if (ROOT / c).exists()), None)
            out = dest / f"{name}.jpg"
            if src is None:
                print(f"{day}/{name}: missing")
                continue
            if out.exists() and not force and out.stat().st_mtime >= src.stat().st_mtime:
                print(f"{day}/{name}: up to date")
                continue
            im = finish(Image.open(src), long_edge=2000, grain=5.0, quality=86, seed=i, hdr=0.5)
            im.save(out, "JPEG", quality=95)
            print(f"{day}/{name}: {src.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
