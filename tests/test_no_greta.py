"""The old persona (Greta) must not leak into code, scenes or the operator guide."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEFTOVER = re.compile(r"greta|vaitkut|vilnius|lithuan|\bгрет\w*|вильнюс|литв\w*", re.I)
SKIP_PREFIXES = ("docs/superpowers/",)
SKIP_FILES = {"uv.lock", "tests/test_no_greta.py"}


def test_no_greta_leftovers():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    hits = []
    for rel in files:
        if rel in SKIP_FILES or rel.startswith(SKIP_PREFIXES):
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if LEFTOVER.search(line):
                hits.append(f"{rel}:{n}: {line.strip()[:80]}")
    assert not hits, "\n".join(hits)
