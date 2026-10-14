"""The operator guide must only mention real `cm` commands and cover AI labelling."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import typer.main
from typer.testing import CliRunner

from comfy_model import cli

ROOT = Path(__file__).resolve().parent.parent
GUIDE_DIR = ROOT / "docs" / "guide"
DOC_FILES = sorted(GUIDE_DIR.glob("*.md")) + [ROOT / "README.md"]

# `cm pod up`, `cm batch face scenes/face.yaml`, `cm export a.png` ...
CM_CALL = re.compile(r"(?<![\w/.-])cm((?:[ \t]+[a-z][a-z-]*){1,2})(?![\w/.-])")


def _groups() -> dict[str, set[str]]:
    """Top-level command name -> subcommand names (empty set for plain commands)."""
    root = typer.main.get_command(cli.app)
    return {
        name: set(getattr(cmd, "commands", {}) or {})
        for name, cmd in root.commands.items()
    }


def _mentioned_commands() -> set[tuple[str, ...]]:
    groups = _groups()
    found: set[tuple[str, ...]] = set()
    for path in DOC_FILES:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            for m in CM_CALL.finditer(line):
                words = m.group(1).split()
                if words[0] not in groups:
                    # prose like "cm is ..." is not a command; real typos are caught below
                    if len(words) == 1 or words[0] in ("cm",):
                        continue
                    found.add((words[0],))
                    continue
                if groups[words[0]] and len(words) > 1:
                    found.add((words[0], words[1]))
                else:
                    found.add((words[0],))
    return found


def test_guide_files_exist():
    names = {p.name for p in GUIDE_DIR.glob("*.md")}
    assert {
        "01-setup.md", "02-create-face.md", "03-train-lora.md",
        "04-daily.md", "05-video.md", "06-launch.md",
    } <= names
    assert (ROOT / "README.md").exists()


def test_guide_commands_exist():
    commands = _mentioned_commands()
    assert commands, "the guide mentions no `cm` commands at all"
    runner = CliRunner()
    # sanity: the main workflow is documented
    assert {("pod", "up"), ("pod", "down"), ("lora", "train"), ("export",)} <= commands
    for argv in sorted(commands):
        result = runner.invoke(cli.app, [*argv, "--help"])
        assert result.exit_code == 0, f"`cm {' '.join(argv)}` does not exist: {result.output}"


def test_guide_mentions_ai_label():
    text = (GUIDE_DIR / "06-launch.md").read_text(encoding="utf-8")
    assert "ИИ" in text
    for platform in ("Instagram", "Reddit", "X", "Telegram", "Fanvue"):
        section = _section(text, platform)
        assert "ИИ" in section, f"06-launch.md: no AI-label instruction in the {platform} section"


def _section(text: str, platform: str) -> str:
    """Body of the `## ...<platform>...` heading, up to the next `## ` heading."""
    parts = re.split(r"(?m)^## ", text)
    for part in parts[1:]:
        heading = part.splitlines()[0]
        if re.search(rf"(?<![A-Za-z]){re.escape(platform)}(?![A-Za-z])", heading):
            return part
    pytest.fail(f"06-launch.md has no `## ` section for {platform}")
