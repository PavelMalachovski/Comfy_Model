from pathlib import Path

import pytest

from comfy_model.scenes import ASPECTS, VIDEO_ASPECTS, Scene, SceneError, load_scenes


def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "scenes.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_constants():
    assert ASPECTS == {"4:5": (896, 1120), "9:16": (768, 1344), "1:1": (1024, 1024)}
    assert VIDEO_ASPECTS == {"9:16": (704, 1280), "16:9": (1280, 704)}


def test_defaults_merged(tmp_path):
    p = write(tmp_path, """
defaults: {tier: social, count: 2}
scenes:
  - id: a
    prompt: at her desk
  - id: b
    prompt: on a balcony
    tier: fanvue
    count: 3
    seed: 7
    aspect: "1:1"
""")
    a, b = load_scenes(p, "photo")
    assert a == Scene(id="a", tier="social", prompt="at her desk", aspect="4:5",
                      count=2, seed=None, image=None)
    assert (b.tier, b.count, b.seed, b.aspect) == ("fanvue", 3, 7, "1:1")


def test_builtin_defaults(tmp_path):
    p = write(tmp_path, "scenes:\n  - {id: x, prompt: hello}\n")
    (s,) = load_scenes(p, "photo")
    assert (s.tier, s.count, s.aspect) == ("instagram", 4, "4:5")


def test_scene_is_frozen(tmp_path):
    p = write(tmp_path, "scenes:\n  - {id: x, prompt: hello}\n")
    (s,) = load_scenes(p, "face")
    with pytest.raises(Exception):
        s.id = "y"  # type: ignore[misc]


def test_video_defaults(tmp_path):
    p = write(tmp_path, "scenes:\n  - {id: v, prompt: walking, image: a.png}\n")
    (s,) = load_scenes(p, "video")
    assert (s.aspect, s.count, s.image) == ("9:16", 1, "a.png")


def test_video_aspect_uses_video_table(tmp_path):
    p = write(tmp_path, "scenes:\n  - {id: v, prompt: walking, image: a.png, aspect: '16:9'}\n")
    assert load_scenes(p, "video")[0].aspect == "16:9"
    p = write(tmp_path, "scenes:\n  - {id: v, prompt: walking, aspect: '4:5'}\n")
    with pytest.raises(SceneError, match="aspect"):
        load_scenes(p, "video")
    p = write(tmp_path, "scenes:\n  - {id: v, prompt: walking, aspect: '16:9'}\n")
    with pytest.raises(SceneError, match="aspect"):
        load_scenes(p, "photo")


def test_unknown_tier_rejected(tmp_path):
    p = write(tmp_path, "scenes:\n  - {id: x, prompt: hi, tier: onlyfans}\n")
    with pytest.raises(SceneError) as e:
        load_scenes(p, "photo")
    assert "scene 'x'" in str(e.value) and "tier" in str(e.value)


def test_unknown_aspect_rejected(tmp_path):
    p = write(tmp_path, "scenes:\n  - {id: x, prompt: hi, aspect: '2:3'}\n")
    with pytest.raises(SceneError, match=r"scene 'x': .*aspect"):
        load_scenes(p, "photo")


def test_duplicate_id_rejected(tmp_path):
    p = write(tmp_path, "scenes:\n  - {id: x, prompt: hi}\n  - {id: x, prompt: yo}\n")
    with pytest.raises(SceneError, match=r"scene 'x': duplicate id"):
        load_scenes(p, "photo")


def test_missing_prompt_rejected(tmp_path):
    p = write(tmp_path, "scenes:\n  - {id: x}\n")
    with pytest.raises(SceneError, match=r"scene 'x': .*prompt"):
        load_scenes(p, "photo")


@pytest.mark.parametrize("count", [0, 17, -1, "4", 2.5, True])
def test_count_must_be_1_to_16(tmp_path, count):
    p = write(tmp_path, f"scenes:\n  - {{id: x, prompt: hi, count: {count!r}}}\n".replace("'4'", '"4"'))
    with pytest.raises(SceneError, match=r"scene 'x': .*count"):
        load_scenes(p, "photo")


@pytest.mark.parametrize("count", [1, 16])
def test_count_bounds_ok(tmp_path, count):
    p = write(tmp_path, f"scenes:\n  - {{id: x, prompt: hi, count: {count}}}\n")
    assert load_scenes(p, "photo")[0].count == count


@pytest.mark.parametrize("bad", ["Desk Coffee", "-x", "a_b", "", "ä"])
def test_id_must_be_slug(tmp_path, bad):
    p = write(tmp_path, f"scenes:\n  - {{id: '{bad}', prompt: hi}}\n")
    with pytest.raises(SceneError, match=r"scene '.*': .*id"):
        load_scenes(p, "photo")


def test_numeric_id_rejected_with_index(tmp_path):
    p = write(tmp_path, "scenes:\n  - {id: 5, prompt: hi}\n")
    with pytest.raises(SceneError, match=r"scene '#1': .*id"):
        load_scenes(p, "photo")


def test_seed_must_be_non_negative_int(tmp_path):
    p = write(tmp_path, "scenes:\n  - {id: x, prompt: hi, seed: -1}\n")
    with pytest.raises(SceneError, match=r"scene 'x': .*seed"):
        load_scenes(p, "photo")
    p = write(tmp_path, "scenes:\n  - {id: x, prompt: hi, seed: abc}\n")
    with pytest.raises(SceneError, match=r"scene 'x': .*seed"):
        load_scenes(p, "photo")
    p = write(tmp_path, "scenes:\n  - {id: x, prompt: hi, seed: 0}\n")
    assert load_scenes(p, "photo")[0].seed == 0


def test_safety_violation_reported_with_id(tmp_path):
    lines = [f"  - {{id: s{i}, prompt: 'at the beach'}}" for i in range(1, 41)]
    lines[36] = "  - {id: s37, prompt: 'posing in black lingerie'}"
    p = write(tmp_path, "scenes:\n" + "\n".join(lines) + "\n")
    with pytest.raises(SceneError) as e:
        load_scenes(p, "photo")
    msg = str(e.value)
    assert "scene 's37': " in msg and "lingerie" in msg
    assert "s36" not in msg and "s38" not in msg


def test_safety_depends_on_tier(tmp_path):
    p = write(tmp_path, "scenes:\n  - {id: x, prompt: 'black lingerie', tier: fanvue}\n")
    assert load_scenes(p, "photo")[0].tier == "fanvue"


def test_all_errors_reported_at_once(tmp_path):
    p = write(tmp_path, """
scenes:
  - {id: one, prompt: hi, tier: nope}
  - {id: two, prompt: hi, count: 99}
""")
    with pytest.raises(SceneError) as e:
        load_scenes(p, "photo")
    msg = str(e.value)
    assert "scene 'one'" in msg and "scene 'two'" in msg
    assert all(line.startswith(("scene '", "file: ")) for line in msg.splitlines())


def test_multiple_errors_in_one_scene_each_on_own_line(tmp_path):
    p = write(tmp_path, "scenes:\n  - {id: x, tier: nope, count: 0}\n")
    with pytest.raises(SceneError) as e:
        load_scenes(p, "photo")
    lines = str(e.value).splitlines()
    assert len(lines) == 3 and all(l.startswith("scene 'x': ") for l in lines)


def test_video_scene_requires_image(tmp_path):
    p = write(tmp_path, "scenes:\n  - {id: v, prompt: walking}\n")
    with pytest.raises(SceneError, match=r"scene 'v': .*image"):
        load_scenes(p, "video")


def test_photo_scene_with_image_rejected(tmp_path):
    p = write(tmp_path, "scenes:\n  - {id: x, prompt: hi, image: a.png}\n")
    for kind in ("face", "dataset", "photo"):
        with pytest.raises(SceneError, match=r"scene 'x': .*image"):
            load_scenes(p, kind)


def test_unknown_key_rejected(tmp_path):
    p = write(tmp_path, "scenes:\n  - {id: x, promt: hi}\n")
    with pytest.raises(SceneError) as e:
        load_scenes(p, "photo")
    assert "promt" in str(e.value) and "scene 'x'" in str(e.value)


def test_unknown_key_in_defaults_and_top_level(tmp_path):
    p = write(tmp_path, "defaults: {tierr: social}\nextra: 1\nscenes:\n  - {id: x, prompt: hi}\n")
    with pytest.raises(SceneError) as e:
        load_scenes(p, "photo")
    msg = str(e.value)
    assert "tierr" in msg and "extra" in msg
    assert all(line.startswith(("scene '", "file: ")) for line in msg.splitlines())


def test_defaults_cannot_set_id(tmp_path):
    p = write(tmp_path, "defaults: {id: x}\nscenes:\n  - {id: y, prompt: hi}\n")
    with pytest.raises(SceneError, match=r"file: .*id"):
        load_scenes(p, "photo")


def test_default_prompt_and_image_allowed(tmp_path):
    p = write(tmp_path, "defaults: {prompt: base}\nscenes:\n  - {id: x}\n")
    assert load_scenes(p, "photo")[0].prompt == "base"


def test_scene_without_id_uses_index(tmp_path):
    p = write(tmp_path, "scenes:\n  - {id: a, prompt: hi}\n  - {id: b, prompt: hi}\n  - {prompt: hi}\n")
    with pytest.raises(SceneError, match=r"scene '#3': .*id"):
        load_scenes(p, "photo")


def test_scene_not_a_mapping(tmp_path):
    p = write(tmp_path, "scenes:\n  - just a string\n")
    with pytest.raises(SceneError, match=r"scene '#1': "):
        load_scenes(p, "photo")


def test_malformed_yaml(tmp_path):
    p = write(tmp_path, "scenes: [unclosed\n")
    with pytest.raises(SceneError, match=r"^file: "):
        load_scenes(p, "photo")


@pytest.mark.parametrize("text", ["", "defaults: {}\n", "scenes: []\n", "scenes: {a: 1}\n", "- x\n"])
def test_file_level_problems(tmp_path, text):
    with pytest.raises(SceneError, match=r"^file: "):
        load_scenes(write(tmp_path, text), "photo")


def test_missing_file(tmp_path):
    with pytest.raises(SceneError, match=r"^file: "):
        load_scenes(tmp_path / "nope.yaml", "photo")


def test_defaults_not_a_mapping(tmp_path):
    p = write(tmp_path, "defaults: 3\nscenes:\n  - {id: x, prompt: hi}\n")
    with pytest.raises(SceneError, match=r"^file: .*defaults"):
        load_scenes(p, "photo")


def test_scene_error_is_value_error():
    assert issubclass(SceneError, ValueError)
