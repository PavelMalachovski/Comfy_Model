import json
import shutil
import subprocess
import sys

import pytest
from PIL import Image, ImageChops, ImageStat
from PIL.PngImagePlugin import PngInfo
from typer.testing import CliRunner

from comfy_model.cli import app
from comfy_model.export import export_image


def _make_png(path, color=(120, 90, 60), size=(64, 48), with_text=True):
    img = Image.new("RGB", size, color)
    info = None
    if with_text:
        info = PngInfo()
        info.add_text("prompt", '{"secret": "ohwxgreta in a bikini"}')
        info.add_text("workflow", '{"nodes": []}')
    img.save(path, pnginfo=info)
    return path


def test_workflow_metadata_stripped(tmp_path):
    src = _make_png(tmp_path / "a.png")
    out = export_image(src, tmp_path / "export")
    assert out == tmp_path / "export" / "a.jpg"
    with Image.open(out) as img:
        assert "prompt" not in img.info
        assert "workflow" not in img.info
    data = out.read_bytes()
    assert b"prompt" not in data
    assert b"ohwxgreta" not in data
    assert b"workflow" not in data


def test_ai_label_in_exif(tmp_path):
    src = _make_png(tmp_path / "a.png")
    out = export_image(src, tmp_path / "export")
    with Image.open(out) as img:
        exif = img.getexif()
        assert exif[0x010E] == "AI-generated image"
        assert exif[0x0131] == "AI-generated"
        assert img.format == "JPEG"
        assert img.mode == "RGB"


def test_grain_zero_is_near_identical(tmp_path):
    src = _make_png(tmp_path / "a.png")
    out = export_image(src, tmp_path / "export", grain=0)
    with Image.open(src) as a, Image.open(out) as b:
        diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
        assert sum(ImageStat.Stat(diff).mean) / 3 < 1


def test_grain_changes_image_and_is_monochrome(tmp_path):
    src = _make_png(tmp_path / "a.png", color=(100, 100, 100), size=(128, 128))
    out = export_image(src, tmp_path / "export", grain=0.05, quality=100)
    with Image.open(out) as img:
        r, g, b = img.split()
        assert ImageStat.Stat(r).stddev[0] > 4
        # the same noise is added to all channels (monochrome grain)
        assert ImageStat.Stat(ImageChops.difference(r, g)).mean[0] < 3


def test_grain_deterministic(tmp_path):
    src = _make_png(tmp_path / "a.png")
    o1 = export_image(src, tmp_path / "one", grain=0.05)
    o2 = export_image(src, tmp_path / "two", grain=0.05)
    assert o1.read_bytes() == o2.read_bytes()


def test_grain_depends_on_file_name(tmp_path):
    a = _make_png(tmp_path / "a.png")
    b = _make_png(tmp_path / "b.png")
    o1 = export_image(a, tmp_path / "e", grain=0.05)
    o2 = export_image(b, tmp_path / "e", grain=0.05)
    assert o1.read_bytes() != o2.read_bytes()


FAKE_FFMPEG = """#!{python}
import json, shutil, sys
argv = sys.argv[1:]
with open({log!r}, "a") as f:
    f.write(json.dumps(argv) + "\\n")
if {rc}:
    sys.stderr.write("fake ffmpeg failure\\n")
    sys.exit({rc})
shutil.copyfile(argv[argv.index("-i") + 1], argv[-1])
"""


def _stub_ffmpeg(tmp_path, monkeypatch, rc=0):
    """Put a fake `ffmpeg` (records argv, copies input to output) alone on PATH."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "ffmpeg-argv.jsonl"
    exe = bindir / "ffmpeg"
    exe.write_text(FAKE_FFMPEG.format(python=sys.executable, log=str(log), rc=rc))
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))
    return log


def _argv_log(log):
    return [json.loads(line) for line in log.read_text().splitlines()]


def test_mp4_remuxed_without_metadata_and_labelled(tmp_path, monkeypatch):
    log = _stub_ffmpeg(tmp_path, monkeypatch)
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"\x00\x00\x00\x18ftypmp42 fake video")
    out = export_image(src, tmp_path / "export")
    assert out == tmp_path / "export" / "clip.mp4"
    (argv,) = _argv_log(log)
    assert argv[argv.index("-i") + 1] == str(src)
    assert argv[argv.index("-map_metadata") + 1] == "-1"
    assert argv[argv.index("-c") + 1] == "copy"
    assert argv[argv.index("-metadata") + 1] == "comment=AI-generated"
    assert "-y" in argv
    assert argv[-1] == str(out)
    assert out.read_bytes() == src.read_bytes()


def test_mp4_ffmpeg_failure_raises_and_leaves_no_file(tmp_path, monkeypatch):
    _stub_ffmpeg(tmp_path, monkeypatch, rc=1)
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"video")
    with pytest.raises(ValueError, match="clip.mp4"):
        export_image(src, tmp_path / "export")
    assert not (tmp_path / "export" / "clip.mp4").exists()


def test_mp4_without_ffmpeg_copied_with_warning(tmp_path, monkeypatch):
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    warnings = []
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"\x00\x00\x00\x18ftypmp42 fake video")
    out = export_image(src, tmp_path / "export", warn=warnings.append)
    assert out == tmp_path / "export" / "clip.mp4"
    assert out.read_bytes() == src.read_bytes()
    assert len(warnings) == 1
    assert "ffmpeg" in warnings[0] and "metadata" in warnings[0] and "clip.mp4" in warnings[0]


def test_cli_export_mp4_without_ffmpeg_warns_but_succeeds(tmp_path, monkeypatch):
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    v = tmp_path / "v.mp4"
    v.write_bytes(b"video")
    result = CliRunner().invoke(app, ["export", str(v), "--to", str(tmp_path / "o")])
    assert result.exit_code == 0, result.output
    assert "warning" in result.output.lower() and "ffmpeg" in result.output
    assert (tmp_path / "o" / "v.mp4").exists()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_mp4_real_ffmpeg_strips_prompt_metadata(tmp_path):
    src = tmp_path / "real.mp4"
    made = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=32x32:d=0.2",
         # ComfyUI's SaveVideo writes prompt/workflow as custom mp4 tags (use_metadata_tags)
         "-c:v", "mpeg4", "-movflags", "use_metadata_tags", "-metadata", "prompt=LEAK-ohwxgreta", "-metadata", "comment=LEAK-workflow",
         str(src)],
        capture_output=True, text=True,
    )
    if made.returncode != 0:
        pytest.skip(f"ffmpeg cannot encode a test clip: {made.stderr[:200]}")
    assert b"LEAK-ohwxgreta" in src.read_bytes()
    out = export_image(src, tmp_path / "export")
    data = out.read_bytes()
    assert b"LEAK-" not in data
    assert b"AI-generated" in data


def test_unsupported_extension_names_file(tmp_path):
    src = tmp_path / "notes.txt"
    src.write_text("x")
    with pytest.raises(ValueError, match="notes.txt"):
        export_image(src, tmp_path / "export")


def test_cli_export_prints_paths(tmp_path, monkeypatch):
    _stub_ffmpeg(tmp_path, monkeypatch)
    a = _make_png(tmp_path / "a.png")
    v = tmp_path / "v.mp4"
    v.write_bytes(b"video")
    dest = tmp_path / "out"
    result = CliRunner().invoke(app, ["export", str(a), str(v), "--to", str(dest), "--grain", "0"])
    assert result.exit_code == 0, result.output
    assert str(dest / "a.jpg") in result.output
    assert str(dest / "v.mp4") in result.output
    assert (dest / "a.jpg").exists() and (dest / "v.mp4").exists()


def test_cli_export_missing_file_exits_1(tmp_path):
    result = CliRunner().invoke(app, ["export", str(tmp_path / "nope.png"), "--to", str(tmp_path / "o")])
    assert result.exit_code == 1
    assert "nope.png" in result.output


@pytest.mark.parametrize("grain", [0, 0.03])
def test_png_comment_text_not_leaked(tmp_path, grain):
    info = PngInfo()
    info.add_text("comment", "LEAK-comment")
    src = tmp_path / "c.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(src, pnginfo=info)
    out = export_image(src, tmp_path / "export", grain=grain)
    assert b"LEAK-comment" not in out.read_bytes()
    with Image.open(out) as img:
        assert "comment" not in img.info


@pytest.mark.parametrize("grain", [0, 0.03])
def test_jpeg_com_segment_not_leaked(tmp_path, grain):
    src = tmp_path / "j.jpg"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(src, comment=b"LEAK-jpeg")
    assert b"LEAK-jpeg" in src.read_bytes()
    out = export_image(src, tmp_path / "export", grain=grain)
    assert b"LEAK-jpeg" not in out.read_bytes()
