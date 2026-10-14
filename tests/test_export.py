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


def test_mp4_copied(tmp_path):
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"\x00\x00\x00\x18ftypmp42 fake video")
    out = export_image(src, tmp_path / "export")
    assert out == tmp_path / "export" / "clip.mp4"
    assert out.read_bytes() == src.read_bytes()


def test_unsupported_extension_names_file(tmp_path):
    src = tmp_path / "notes.txt"
    src.write_text("x")
    with pytest.raises(ValueError, match="notes.txt"):
        export_image(src, tmp_path / "export")


def test_cli_export_prints_paths(tmp_path):
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
