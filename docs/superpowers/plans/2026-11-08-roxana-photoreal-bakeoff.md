# Roxana Photoreal Bake-off Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `cm bakeoff` tool and four ComfyUI graphs so the operator can compare Qwen-Image 2512, Z-Image, Z-Image Turbo and HiDream-O1 on identical prompts, blind, at 100% crops, and name a winner.

**Architecture:** A self-contained `src/comfy_model/bakeoff.py` reuses `ComfyClient`, `render`, `load_profile`, `load_scenes` and `check_prompt`; production `cm batch`, `workflows/{face,dataset,photo,video}.json` and `pod/models.yaml` are untouched. Bake-off models live in their own manifest, selected at `cm pod up --models`, on a temporary volume.

**Tech Stack:** Python 3.11+, typer, Pillow, pytest, respx; ComfyUI API-format JSON (ComfyUI v0.40.0, Impact Pack as pinned in `pod/versions.env`).

**Spec:** `docs/superpowers/specs/2026-11-08-roxana-photoreal-bakeoff-design.md`. This plan covers Stage 1 only. Stages 2–3 (face, dataset, LoRA, pipeline migration) depend on the winner and get their own plan once it is named.

## Global Constraints

- No commit, push or publication without the operator's explicit yes. Task 6 asks; earlier tasks leave changes in the working tree.
- No pod or volume is created without the operator's command. Automated tests never reach RunPod or ComfyUI.
- `safety.py` tiers and ban lists are not changed.
- No FLUX model, FLUX output (including `out/mac-test/`) or the operator's style sample enters this tool.
- All bake-off scenes are aspect `4:5`, count `4`.
- Tests run as `.venv/bin/python -m pytest` (`uv` is not installed on this Mac).

## Review Focus

1. A frame where no face is detected: full image is saved, the run continues, the sheet shows a grey "no face" tile (Task 4).
2. A run killed by the watchdog (4 h limit) and repeated: finished frames are skipped, none regenerated, sheet letters stay stable (Task 4).
3. A model file missing on the volume: the run stops at the first validation error with ComfyUI's message, not after 96 failures (Task 4).
4. A prompt that violates its tier once appearance and suffix are joined: nothing is queued for any candidate (Task 4).
5. Sheets must not reveal the candidate: no model name in any sheet file name or label (Task 4).

---

### Task 1: Selectable model manifest on the pod

**Files:**
- Create: `pod/bakeoff_models.yaml`
- Modify: `pod/bootstrap.sh:15`, `src/comfy_model/cli.py:159` and `pod_up` (`:284`), `_provision` (`:254`), `src/comfy_model/workflow.py` `main` (`:225`)
- Test: `tests/test_bootstrap.py`, `tests/test_workflow.py`, `tests/test_bakeoff.py` (create)

**Interfaces:**
- Produces: `bootstrap_cmd(models: Path | None) -> str` in `cli.py`; `cm pod up --models pod/bakeoff_models.yaml`; `python -m comfy_model.workflow --check-urls [manifest]`; `BAKEOFF_MANIFEST = Path("pod/bakeoff_models.yaml")` in `bakeoff.py`.

- [ ] **Step 1: Install dev tools and record the baseline**

Run: `.venv/bin/pip install -q pytest respx shellcheck-py && .venv/bin/python -m pytest -q`
Expected: all tests pass. If not, stop and report before changing anything.

- [ ] **Step 2: Write `pod/bakeoff_models.yaml`** in the `models:` format of `pod/models.yaml`, exactly these entries:

| file | dest | repo | path |
|---|---|---|---|
| `qwen_image_2512_fp8_e4m3fn.safetensors` | diffusion_models | Comfy-Org/Qwen-Image_ComfyUI | split_files/diffusion_models/… |
| `qwen_2.5_vl_7b_fp8_scaled.safetensors` | text_encoders | Comfy-Org/Qwen-Image_ComfyUI | split_files/text_encoders/… |
| `qwen_image_vae.safetensors` | vae | Comfy-Org/Qwen-Image_ComfyUI | split_files/vae/… |
| `z_image_bf16.safetensors` | diffusion_models | Comfy-Org/z_image | split_files/diffusion_models/… |
| `z_image_turbo_bf16.safetensors` | diffusion_models | Comfy-Org/z_image_turbo | split_files/diffusion_models/… |
| `qwen_3_4b.safetensors` | text_encoders | Comfy-Org/z_image_turbo | split_files/text_encoders/… |
| `ae.safetensors` | vae | Comfy-Org/z_image_turbo | split_files/vae/… |
| `hidream_o1_image_bf16.safetensors` | checkpoints | Comfy-Org/HiDream-O1-Image | checkpoints/… |
| `gemma4_e4b_it_fp8_scaled.safetensors` | text_encoders | Comfy-Org/gemma-4 | text_encoders/… |
| `face_yolov8m.pt` | ultralytics/bbox | Bingsu/adetailer | face_yolov8m.pt |

- [ ] **Step 3: Write the failing tests**

```python
# tests/test_bootstrap.py
def test_print_downloads_honours_cm_manifest():  # run bootstrap.sh --print-downloads with CM_MANIFEST=<repo>/pod/bakeoff_models.yaml
    assert "z_image_bf16.safetensors" in out and "flux1-dev-fp8" not in out
# default run (no CM_MANIFEST) still prints flux1-dev-fp8.

# tests/test_cli.py
def test_bootstrap_cmd_default():
    assert bootstrap_cmd(None) == "bash /workspace/cm/pod/bootstrap.sh"
def test_bootstrap_cmd_manifest():
    assert bootstrap_cmd(Path("pod/bakeoff_models.yaml")) == "CM_MANIFEST=/workspace/cm/pod/bakeoff_models.yaml bash /workspace/cm/pod/bootstrap.sh"
def test_bootstrap_cmd_rejects_outside_pod():
    with pytest.raises(ValueError): bootstrap_cmd(Path("/etc/passwd"))
    with pytest.raises(ValueError): bootstrap_cmd(Path("pod/../x.yaml"))

# tests/test_workflow.py
def test_check_urls_accepts_manifest_argument(...):  # main(["--check-urls", str(path)]) reads that file (respx-mocked HEAD)
```

- [ ] **Step 4: Run them, expect FAIL.** Run: `.venv/bin/python -m pytest tests/test_bootstrap.py tests/test_cli.py tests/test_workflow.py -q`

- [ ] **Step 5: Implement.** `bootstrap.sh:15` becomes `MANIFEST="${CM_MANIFEST:-$HERE/models.yaml}"`. `bootstrap_cmd` accepts only a `pod/<name>.yaml` relative path without `..`. `pod_up` gains `models: Optional[Path] = typer.Option(None, "--models")`, validated before the pod is created, passed through `_provision`. `workflow.main` accepts `--check-urls` with an optional manifest path, default `pod/models.yaml`.

- [ ] **Step 6: Run the full suite, expect PASS** (includes shellcheck in `test_bootstrap.py`).

- [ ] **Step 7: Verify every URL is live.** Run: `PYTHONPATH=src .venv/bin/python -m comfy_model.workflow --check-urls pod/bakeoff_models.yaml`
Expected: `10/10 reachable`.

### Task 2: Scenes and profile for the bake-off

**Files:**
- Create: `scenes/bakeoff.yaml`, `character/bakeoff_profile.yaml`
- Test: `tests/test_bakeoff.py`

**Interfaces:**
- Produces: `BAKEOFF_SCENES = Path("scenes/bakeoff.yaml")`, `BAKEOFF_PROFILE = Path("character/bakeoff_profile.yaml")` used by Task 4.

- [ ] **Step 1: Write the failing tests**

```python
def test_six_scenes_right_tiers():
    s = load_scenes(BAKEOFF_SCENES, "face")
    assert [x.tier for x in s].count("instagram") == 4 and [x.tier for x in s].count("social") == 2
    assert all(x.aspect == "4:5" and x.count == 4 and x.seed is not None for x in s)
def test_social_prompts_verbatim():  # latex-dress-penthouse and pov-from-floor prompts == scenes/social.yaml
def test_full_prompts_pass_their_tier():  # check_prompt(profile.photo_prompt(s.prompt, False), s.tier) == [] for every scene
def test_profile_states_adult_age():
    assert load_profile(BAKEOFF_PROFILE).appearance.startswith("42-year-old woman")
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Write `character/bakeoff_profile.yaml`.** `name: Roxana`, `trigger: ohwxroxana`, `video_negative` copied from `character/profile.yaml`, and:

`appearance`: `42-year-old woman, clearly in her forties, mature face with fine lines at the outer corners of her eyes, forehead lines, soft nasolabial folds and slightly tired under-eyes, long sleek dark brunette hair in a high ponytail, dark brown eyes, defined cheekbones, soft matte red lips, oxblood nails, natural uneven skin with visible pores, flyaway hairs`

`style_suffix`: `no retouching`

- [ ] **Step 4: Write `scenes/bakeoff.yaml`.** Defaults `aspect: "4:5"`, `count: 4`; each scene a fixed `seed` (1001, 2001, … 6001), so every model sees the same seeds. Tier `instagram`:

| id | prompt |
|---|---|
| `mirror-selfie-home` | `amateur iPhone mirror selfie, half-body shot with the whole face visible, phone in a plain black case with no logos held low to the side, dim bedroom at night, warm bedside lamp, black silk blouse, casual unposed, cold confident gaze, slight grain` |
| `car-back-seat` | `amateur iPhone photo taken from the back seat of a luxury car at night, black blazer, city lights through the window, mixed dim light, casual unposed, slight grain` |
| `terrace-coffee` | `amateur iPhone photo on a Dubai penthouse terrace in morning sunlight, silk blouse, coffee cup, skyline behind, natural daylight, casual unposed, slight grain` |
| `rooftop-flash` | `amateur iPhone photo with direct phone flash at a Dubai rooftop bar in the evening, black dress, cocktail glass, night skyline behind, casual unposed, slight grain` |

Tier `social`: `latex-dress-penthouse` and `pov-from-floor`, prompts copied verbatim from `scenes/social.yaml`, aspect overridden to `4:5`.

- [ ] **Step 5: Run the tests, expect PASS.**

### Task 3: Four ComfyUI graphs

**Files:**
- Create: `workflows/bakeoff/{qwen_2512,z_image,z_image_turbo,hidream_o1}.json`, `src/comfy_model/bakeoff.py`
- Test: `tests/test_bakeoff.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) class Candidate: name: str; width: int; height: int`; `CANDIDATES: tuple[Candidate, ...]`; `load_graph(name: str, directory: Path = Path("workflows/bakeoff")) -> dict`; `GRAPH_PLACEHOLDERS = {"prompt", "seed", "width", "height", "filename_prefix", "filename_prefix_face"}`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("c", CANDIDATES, ids=lambda c: c.name)
def test_graph_contract(c):
    g = load_graph(c.name)
    assert placeholders(g) == GRAPH_PLACEHOLDERS
    # link validity: same assertions as tests/test_workflow.py::test_graph_links_valid
    assert sum(n["class_type"] == "SaveImage" for n in g.values()) == 2
    assert {f.split("/")[-1] for f in model_files(g)} <= {m.file for m in load_manifest(BAKEOFF_MANIFEST)}
    assert "FaceDetailer" in {n["class_type"] for n in g.values()}
def test_face_save_uses_cropped_refined():  # the filename_prefix_face SaveImage links to [<FaceDetailer id>, 1]
def test_base_sizes():
    assert {(c.name, c.width, c.height) for c in CANDIDATES} == {
        ("qwen_2512", 1024, 1280), ("z_image", 1024, 1280), ("z_image_turbo", 1024, 1280), ("hidream_o1", 1536, 1920)}
@pytest.mark.parametrize("name,steps,cfg,sampler,sched", [
    ("qwen_2512", 50, 4, "euler", "simple"),
    ("z_image", 25, 4, "res_multistep", "simple"),
    ("z_image_turbo", 8, 1, "res_multistep", "simple"),
])
def test_base_sampler_settings(name, steps, cfg, sampler, sched):  # the KSampler with denoise 1.0
def test_refine_pass():  # latent graphs: ImageScaleBy lanczos scale_by 1.5, then a KSampler with denoise 0.25
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Write the three latent graphs**, node for node:

`UNETLoader` (weight_dtype default) → `ModelSamplingAuraFlow`; `CLIPLoader` (type `qwen_image` for Qwen, `lumina2` for Z-Image); `VAELoader`; positive `CLIPTextEncode` with `{{prompt}}`; negative per table; `EmptySD3LatentImage` with `{{width}}`/`{{height}}`, batch 1; base `KSampler` (`{{seed}}`, denoise 1.0) → `VAEDecode` → `ImageScaleBy` (lanczos, 1.5) → `VAEEncode` → refine `KSampler` (same seed, sampler, steps, cfg; denoise 0.25) → `VAEDecode` → `FaceDetailer` → `SaveImage` (`{{filename_prefix}}`), plus `SaveImage` (`{{filename_prefix_face}}`) on FaceDetailer output 1.

| graph | model | shift | negative | detailer steps |
|---|---|---|---|---|
| `qwen_2512` | `qwen_image_2512_fp8_e4m3fn` + `qwen_2.5_vl_7b_fp8_scaled` + `qwen_image_vae` | 3.1 | text from official template `image_qwen_Image_2512.json` | 25 |
| `z_image` | `z_image_bf16` + `qwen_3_4b` + `ae` | 3 | empty `CLIPTextEncode` | 20 |
| `z_image_turbo` | `z_image_turbo_bf16` + `qwen_3_4b` + `ae` | 3 | `ConditioningZeroOut` of positive | 8 |

FaceDetailer: copy all inputs from `workflows/photo.json` node 10 except: `guide_size` 768, `steps` per table, and `cfg`, `sampler_name`, `scheduler` from the graph's base sampler. `UltralyticsDetectorProvider` as in node 9.

- [ ] **Step 4: Write `hidream_o1.json`** by converting `templates/image_hidream_o1.json` from `Comfy-Org/workflow_templates` (`main`) to API format: text-to-image path only, the prompt-enhancer switch off, no reference images. `EmptyHiDreamO1LatentImage` takes `{{width}}`/`{{height}}`; `SamplerCustom` noise seed is `{{seed}}`; keep its steps (40), `dpmpp_2m_sde_gpu`, cfg 5, `ModelNoiseScale` 8 and `HiDreamO1PatchSeamSmoothing` values. No refine pass: it generates at 1536×1920 directly. FaceDetailer takes the patched model, `sampler_name` `dpmpp_2m_sde_gpu`, `scheduler` `normal`, `cfg` 5, steps 20.

- [ ] **Step 5: Implement `load_graph` and `CANDIDATES`; run tests, expect PASS.**

### Task 4: Runner and blind sheets

**Files:**
- Modify: `src/comfy_model/bakeoff.py`, `src/comfy_model/cli.py`
- Test: `tests/test_bakeoff.py`

**Interfaces:**
- Consumes: Task 2 and 3 names; `ComfyClient.queue/wait/outputs/download`; `ComfyError.is_validation`.
- Produces: `run_bakeoff(names: Sequence[str], client: ComfyClient, out_dir: Path, *, limit: int | None = None, on_item: Callable[[str], None] | None = None) -> BatchReport` (reuse `batch.BatchReport`); `make_sheets(out_dir: Path) -> Path` returning the sheet dir `out_dir/sheets`; CLI `cm bakeoff run [--out] [--only a,b] [--limit N] [--url]`, `cm bakeoff sheets --out DIR`.

Output layout: `<out>/<candidate>/<scene>_<nn>.png`, `<scene>_<nn>_face.png`, `manifest.jsonl`. Sheets: `<out>/sheets/<scene>.jpg` (frames, 512 px wide), `<out>/sheets/<scene>_faces.jpg` (face crops unscaled), `<out>/key.json` (`{"A": "<candidate>", …}`, outside `sheets/`). One column per letter, one row per seed. Seed of frame `n` is `scene.seed + n - 1`.

- [ ] **Step 1: Write the failing tests**, using a fake client class that records queued graphs and returns two `OutputFile`s (`…_00001_.png`, `…_face_00001_.png`):

```python
def test_same_seeds_across_candidates(): ...           # each candidate queued with identical seed sequence
def test_rerun_skips_finished_frames(): ...            # second run queues nothing, report.skipped has all
def test_limit_counts_only_new_frames(): ...           # limit=1 twice yields 2 distinct frames
def test_no_face_output_keeps_frame(): ...             # one OutputFile only: full saved, manifest "no_face": true, run continues
def test_validation_error_stops_run(): ...             # ComfyError(is_validation=True) propagates after 1 queue
def test_timeout_stops_run(): ...                      # TimeoutError: report.aborted set, nothing more queued
def test_prompt_violation_queues_nothing(tmp_path, monkeypatch): ...  # a banned term in any scene: ValueError, 0 queued
def test_sheets_are_blind(tmp_path):
    # no candidate name appears in any path under sheets/; key.json maps letters to all candidates
def test_sheet_letters_stable(): ...                   # second make_sheets keeps key.json unchanged
def test_sheet_missing_frame_is_grey_tile(): ...       # missing image does not raise
def test_bakeoff_commands_registered(): ...            # CliRunner: `bakeoff run --help`, `bakeoff sheets --help` exit 0
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement.** Check every full prompt for every scene before the first queue. A frame counts as finished when its full image exists. Timeout per frame: `batch.DEFAULT_WAIT_TIMEOUT_S`. `key.json` letters are assigned once by `random.shuffle` and reused if the file exists. `cli.py`: add `bakeoff_app` typer group following `batch` (`:77-128`) for `_resolve_url`, `_make_client`, `NO_POD`, and `--out` default `out/bakeoff`.

- [ ] **Step 4: Run the full suite, expect PASS.**

### Task 5: Operator guide

**Files:**
- Create: `docs/guide/08-bakeoff.md`
- Test: `tests/test_docs.py` (existing checks)

- [ ] **Step 1: Write the guide (Russian)** covering: creating a separate 150 GB network volume in EU-RO-1, and putting its ID in `RUNPOD_VOLUME_ID` for the bake-off; `cm pod up --models pod/bakeoff_models.yaml`; smoke test `cm bakeoff run --limit 1`; full run `cm bakeoff run`; repeating after the 4-hour watchdog stop; `cm bakeoff sheets --out out/bakeoff`; choosing a winner before opening `key.json`; `cm pod down`; deleting the temporary volume and restoring `RUNPOD_VOLUME_ID`; expected cost $3–5 plus volume. Note that these images are for evaluation only.

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_docs.py -q`. Expected: PASS.

### Task 6: Hand-off, then the pod run (operator's go-ahead required)

- [ ] **Step 1: Ask the operator** whether to commit the work, and show `git status`. Commit only on a yes, with the session's attribution line.

- [ ] **Step 2: Operator prepares** RunPod balance, temporary volume, `.env`. Confirm the 4090 price in the console.

- [ ] **Step 3: On the operator's command:** `cm pod up --models pod/bakeoff_models.yaml`, then `cm bakeoff run --limit 1` for one frame of each candidate.
Expected: 4 frames with face crops. Open each and check it is a coherent image. If HiDream's FaceDetailer fails, one debugging attempt; failing that, remove that node from `hidream_o1.json`, keep the candidate, and tell the operator its frames have no second face pass.

- [ ] **Step 4: Full run:** `cm bakeoff run`, repeating after a watchdog stop. Expected: 96 frames across 4 candidates. `cm pod down` when finished; confirm with `cm pod status`.

- [ ] **Step 5: Build and send sheets:** `cm bakeoff sheets --out out/bakeoff`. The operator names the winning letter(s). Only then read `key.json` and report the model.
