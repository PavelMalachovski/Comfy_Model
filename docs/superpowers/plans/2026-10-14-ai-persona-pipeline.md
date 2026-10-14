# AI Persona Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A repo from which a ComfyUI beginner (but experienced DevOps engineer) brings up a rented RTX 4090 with one command and batch-generates consistent photos/short videos of one fictional adult persona, with safety rules enforced in code and a Russian step-by-step guide.

**Architecture:** A local Python CLI `cm` drives everything: it creates/terminates a RunPod pod with a persistent network volume, rsyncs `pod/` + `workflows/` to it over SSH and runs an idempotent bootstrap (ComfyUI + models + idle watchdog). Generation is done by rendering ComfyUI API-format workflow templates from YAML scene files and submitting them to the pod's ComfyUI HTTP API; every prompt passes a safety check before any GPU time is spent. LoRA training runs on the same pod with ostris/ai-toolkit.

**Tech Stack:** Python 3.11+, uv, typer, httpx, PyYAML, Pillow, runpod SDK; pytest + respx. On the pod: ComfyUI (pinned tag), ComfyUI-Impact-Pack + Impact-Subpack, ai-toolkit (pinned commit); models FLUX.1-dev fp8, FLUX.1 Kontext dev fp8, Wan 2.2 TI2V-5B, RealESRGAN x4plus, face_yolov8m.

**Spec:** `docs/superpowers/specs/2026-10-14-ai-model-it-girl-design.md`

## Global Constraints

- Budget ceiling $50–70/month; GPU auto-terminates after **15 min** idle and after **4 h** hard max runtime (both configurable).
- Persona is fictional, clearly adult (27–29), resembles no real person; AI label everywhere.
- v1 content level: swimwear / lingerie / suggestive poses; **no nudity on any tier**. Instagram tier: no lingerie/underwear either.
- Telegram is a free teaser channel; Fanvue is the only monetization in v1.
- Operator-facing docs (`docs/guide/`, `character/bible.md`) are in **Russian**; persona-facing text (captions, prompt text, example posts) in **English**.
- Scripts may assume CLI/SSH/Docker fluency; no GUI wrappers.
- Secrets only via `.env` (git-ignored): `RUNPOD_API_KEY`, `RUNPOD_VOLUME_ID`, `HF_TOKEN`. Never committed.
- Persona name/handle (planner's call, operator may change in `character/profile.yaml`): **Zofia "Zosia" Wrona**, 28, Kraków, SRE; LoRA trigger token **`ohwxzosia`**.

## Review Focus

1. **Pod already terminated by watchdog while `.cm/pod.json` still references it** → `cm pod status`/`cm batch` say "no running pod, run `cm pod up`" and clear the stale state; never hang on a dead URL. (Task 8 test `test_status_clears_stale_state`.)
2. **Batch interrupted midway (network drop, pod killed) and re-run** → already-downloaded outputs are skipped, numbering stays stable, no duplicate GPU work. (Task 5 test `test_rerun_skips_existing_outputs`.)
3. **Scene file with a typo, unknown tier/aspect, duplicate id or banned term in scene #37** → whole file rejected with scene id + reason *before* anything is queued. (Task 3 tests + Task 5 `test_invalid_file_queues_nothing`.)
4. **Banned term written with case/punctuation variants** ("School-Girl", "TEEN", "18yo", "nude_") → caught. (Task 1 parametrized test.)
5. **ComfyUI rejects a prompt because a model file is missing on the volume** → error names the node and the missing file, batch stops, nothing hangs. (Task 4 test `test_queue_node_error_is_readable`.)

---

## File Structure

```
pyproject.toml                 # package comfy_model, entry point `cm`
.env.example  .gitignore
config/settings.yaml           # gpu, datacenter, image tag, timeouts, paths
character/bible.md             # RU: persona bible
character/profile.yaml         # appearance text, trigger, style suffix, video negative
scenes/{face,dataset,instagram,social,fanvue,video}.yaml
workflows/{face,dataset,photo,video}.json   # ComfyUI API-format templates
pod/bootstrap.sh  pod/models.yaml  pod/versions.env
training/lora_flux.yaml        # ai-toolkit config template
src/comfy_model/
  __init__.py cli.py config.py
  safety.py profile.py scenes.py workflow.py
  comfy_client.py batch.py export.py
  watchdog.py   # stdlib-only, copied to pod
  remote.py runpod_pod.py lora.py
scripts/validate_workflows.py  # CPU ComfyUI graph validation
docs/guide/01-setup.md … 06-launch.md   # RU
tests/…
```

---

### Task 1: Project skeleton, config, safety rules

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `config/settings.yaml`, `src/comfy_model/{__init__,cli,config,safety}.py`
- Test: `tests/test_safety.py`, `tests/test_config.py`

**Interfaces:**
- Produces:
  - `Tier = Literal["instagram", "social", "fanvue"]`
  - `safety.check_prompt(text: str, tier: Tier) -> list[str]` — list of human-readable violations, empty = OK
  - `safety.normalize(text: str) -> str`
  - `config.Settings` dataclass: `gpu_type: str, datacenter: str, image: str, volume_gb: int, idle_timeout_min: int, max_runtime_h: float, comfy_port: int, remote_root: str`; `config.load_settings(path: Path = Path("config/settings.yaml")) -> Settings`; `config.load_secrets() -> dict[str, str]` (reads `.env` + env, raises `ConfigError` naming the missing key on access via `require(name)`)
  - `cli.app: typer.Typer` (entry point `cm`), sub-apps added by later tasks.

- [ ] **Step 1: Scaffold.** `uv init --package`, deps `typer httpx pyyaml pillow runpod`, dev deps `pytest respx`. `.gitignore`: `.env .cm/ out/ dataset/ __pycache__ .venv`. `config/settings.yaml` values: `gpu_type: "NVIDIA GeForce RTX 4090"`, `datacenter: "EU-RO-1"`, `image:` current `runpod/pytorch` tag with CUDA 12.8 (pin exact tag), `volume_gb: 100`, `idle_timeout_min: 15`, `max_runtime_h: 4`, `comfy_port: 8188`, `remote_root: "/workspace"`.

- [ ] **Step 2: Write failing tests.**

```python
@pytest.mark.parametrize("text", ["a teen girl", "School-Girl outfit", "TEENAGER", "18yo woman",
    "17 year old", "loli style", "young girl", "high-school uniform", "underage"])
def test_age_terms_banned_everywhere(text):
    for tier in ("instagram", "social", "fanvue"):
        assert check_prompt(text, tier)

@pytest.mark.parametrize("text", ["nude on bed", "Topless", "naked_", "nipples", "explicit", "NSFW"])
def test_nudity_banned_all_tiers_v1(text):
    for tier in ("instagram", "social", "fanvue"):
        assert check_prompt(text, tier)

@pytest.mark.parametrize("text", ["black lingerie", "lace bra", "panties", "underwear"])
def test_lingerie_banned_only_on_instagram(text):
    assert check_prompt(text, "instagram")
    assert check_prompt(text, "social") == []
    assert check_prompt(text, "fanvue") == []

@pytest.mark.parametrize("text", ["looks like Margot Robbie", "celebrity lookalike", "resembling a famous actress"])
def test_real_person_likeness_banned(text):
    assert check_prompt(text, "fanvue")

def test_clean_prompt_passes():
    assert check_prompt("28-year-old woman at her desk, three monitors, morning light, bikini on a boat", "instagram") == []

def test_settings_defaults_load():
    s = load_settings()
    assert s.idle_timeout_min == 15 and s.max_runtime_h == 4
```

- [ ] **Step 3: Run** `uv run pytest tests/test_safety.py tests/test_config.py -v` → FAIL (import errors).

- [ ] **Step 4: Implement.** `normalize`: lowercase, `[-_]` → space, collapse whitespace. Rules are word-boundary regexes over normalized text; age regex also matches `\b([1-9]|1\d|20)\s?(yo|y o|year old|years old)\b`. Rule table keyed by tier so later tiers (explicit Fanvue) are a one-line change; violation strings name the matched term.

- [ ] **Step 5: Run tests** → PASS. **Commit** `feat: project skeleton, settings, prompt safety rules`.

---

### Task 2: Character bible and prompt profile

**Files:**
- Create: `character/bible.md`, `character/profile.yaml`, `src/comfy_model/profile.py`
- Test: `tests/test_profile.py`

**Interfaces:**
- Consumes: `safety.check_prompt`
- Produces: `profile.Profile` dataclass `name: str, trigger: str, appearance: str, style_suffix: str, video_negative: str`; `profile.load_profile(path: Path = Path("character/profile.yaml")) -> Profile`; `Profile.photo_prompt(scene_prompt: str, use_trigger: bool) -> str` = `"{trigger + ', ' if use_trigger}{appearance}, {scene_prompt}, {style_suffix}"`.

- [ ] **Step 1: Write failing tests.**

```python
def test_profile_has_adult_anchor():
    p = load_profile()
    assert re.search(r"\b(2[5-9]|[3-9]\d)-year-old woman\b", p.appearance)

def test_profile_text_passes_strictest_tier():
    p = load_profile()
    assert check_prompt(p.appearance + " " + p.style_suffix, "instagram") == []

def test_trigger_only_when_requested():
    p = load_profile()
    assert p.photo_prompt("at desk", use_trigger=True).startswith("ohwxzosia, ")
    assert "ohwxzosia" not in p.photo_prompt("at desk", use_trigger=False)

def test_video_negative_blocks_minors():
    assert "child" in load_profile().video_negative
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Write `character/profile.yaml`.** `name: "Zofia Wrona"`, `trigger: "ohwxzosia"`, `appearance`: one fixed English sentence starting `"28-year-old Polish woman"` (light ash-blonde hair, light grey-blue eyes, high cheekbones, athletic but not muscular build, natural skin texture with faint freckles); `style_suffix`: candid smartphone photo realism (natural light, slight film grain, realistic skin pores, no heavy makeup); `video_negative` includes `child, teen, underage, deformed, extra limbs, blurry`.

- [ ] **Step 4: Write `character/bible.md` (Russian).** Sections: Кто она (биография: Kraków, SRE ~5 лет, удалёнка в западной компании, Kubernetes/CI/CD/on-call), Внешность (дублирует profile.yaml + стиль «днём худи и очки, вечером платье»), Характер и голос (умная, саркастичная, nerd, контраст), Как она пишет (английский с лёгкими восточноевропейскими оборотами; 10 примеров постов для Instagram/X/Reddit на английском, IT-юмор), Как она общается на Fanvue (тон, границы), Запреты (из анти-целей спеки дословно: не похожа на реальных людей, только взрослая, пометка ИИ, не утверждает что она реальный человек), Отложено: персонаж №2 (психолог).

- [ ] **Step 5: Implement `profile.py`; run tests** → PASS. **Commit** `feat: character bible and prompt profile`.

---

### Task 3: Scene files: schema and validation

**Files:**
- Create: `src/comfy_model/scenes.py`
- Test: `tests/test_scenes.py`

**Interfaces:**
- Consumes: `safety.check_prompt`, `Tier`
- Produces:
  - `ASPECTS = {"4:5": (896, 1120), "9:16": (768, 1344), "1:1": (1024, 1024)}` (photo); video uses `{"9:16": (704, 1280), "16:9": (1280, 704)}` as `VIDEO_ASPECTS`
  - `Scene` dataclass: `id: str, tier: Tier, prompt: str, aspect: str, count: int, seed: int | None, image: str | None`
  - `SceneError(ValueError)` — message always starts with `"scene '<id>': "` (or `"file: "` for file-level problems)
  - `load_scenes(path: Path, kind: Literal["face", "dataset", "photo", "video"]) -> list[Scene]` — validates the **whole** file, collects all errors, raises one `SceneError` listing every problem.

File format (top-level `defaults:` merged into each `scenes:` item):
```yaml
defaults: {tier: instagram, aspect: "4:5", count: 4}
scenes:
  - id: desk-morning-coffee
    prompt: "at her desk with three monitors, morning light, oversized hoodie, glasses, holding coffee"
```

- [ ] **Step 1: Write failing tests** (YAML via `tmp_path`):
  - `test_defaults_merged` — scene without tier gets `instagram`, count 4.
  - `test_unknown_tier_rejected` — `tier: onlyfans` → `SceneError` containing `"scene 'x'"` and `"tier"`.
  - `test_unknown_aspect_rejected`, `test_duplicate_id_rejected`, `test_missing_prompt_rejected`, `test_count_must_be_1_to_16`.
  - `test_id_must_be_slug` — `"Desk Coffee"` rejected (ids become filenames; `^[a-z0-9][a-z0-9-]*$`).
  - `test_safety_violation_reported_with_id` — scene 37 of 40 has "lingerie" on instagram → message names that id.
  - `test_all_errors_reported_at_once` — two bad scenes → both ids in one message.
  - `test_video_scene_requires_image` — `kind="video"` without `image` rejected; photo scene with `image` rejected.
  - `test_unknown_key_rejected` — `promt:` typo → error names `promt`.

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS. **Step 5: Commit** `feat: scene file loader with full-file validation`.

---

### Task 4: ComfyUI workflow templates and HTTP client

**Files:**
- Create: `workflows/{face,dataset,photo,video}.json`, `src/comfy_model/workflow.py`, `src/comfy_model/comfy_client.py`, `pod/models.yaml`
- Test: `tests/test_workflow.py`, `tests/test_comfy_client.py`

**Interfaces:**
- Produces:
  - `workflow.PLACEHOLDERS: dict[str, set[str]]` =
    - `face`: `{prompt, seed, width, height, batch_size, filename_prefix}`
    - `dataset`: `{prompt, seed, ref_image, filename_prefix}`
    - `photo`: `{prompt, seed, width, height, lora_name, lora_strength, filename_prefix}`
    - `video`: `{prompt, negative, seed, image, width, height, length, filename_prefix}`
  - `workflow.load_template(kind: str) -> dict`; `workflow.render(template: dict, values: dict[str, Any]) -> dict` — deep copy; any string exactly `"{{name}}"` replaced by `values[name]` keeping its type; raises `TemplateError` for an unfilled placeholder or an unused value.
  - `workflow.model_files(template: dict) -> set[str]` — every `*_name` / `ckpt_name` / `unet_name` / `vae_name` / `clip_name*` / `model_name` input value that is a literal string.
  - `comfy_client.OutputFile(filename: str, subfolder: str, type: str)`
  - `comfy_client.ComfyError(RuntimeError)`
  - `comfy_client.ComfyClient(base_url: str, timeout_s: float = 30)` with `queue(workflow: dict) -> str`, `wait(prompt_id: str, timeout_s: float = 900, poll_s: float = 2) -> dict`, `outputs(history_entry: dict) -> list[OutputFile]`, `download(f: OutputFile, dest: Path) -> Path`, `upload_image(path: Path) -> str`, `ping() -> bool`.

Workflow graphs (API format, core nodes unless noted):
- **face:** `CheckpointLoaderSimple(flux1-dev-fp8.safetensors)` → `CLIPTextEncode` → `FluxGuidance(2.5)` → `EmptySD3LatentImage(width,height,batch_size)` → `KSampler(euler, beta, 28 steps, cfg 1.0)` → `VAEDecode` → `SaveImage`.
- **dataset:** FLUX.1 Kontext: `UNETLoader(flux1-dev-kontext_fp8_scaled.safetensors)`, `DualCLIPLoader(clip_l, t5xxl_fp8_e4m3fn_scaled, flux)`, `VAELoader(ae.safetensors)`, `LoadImage(ref_image)` → `FluxKontextImageScale` → `VAEEncode` → `ReferenceLatent` → `FluxGuidance(2.5)` → `KSampler(euler, simple, 24 steps, cfg 1.0)` → `VAEDecode` → `SaveImage`.
- **photo:** face graph + `LoraLoaderModelOnly(lora_name, lora_strength)` + Impact Pack `FaceDetailer` (bbox from `UltralyticsDetectorProvider(bbox/face_yolov8m.pt)`, denoise 0.35) + `UpscaleModelLoader(RealESRGAN_x4plus.pth)` → `ImageUpscaleWithModel` → `ImageScaleBy(0.5)` → `SaveImage`.
- **video:** Wan 2.2 TI2V-5B: `UNETLoader(wan2.2_ti2v_5B_fp16.safetensors)`, `CLIPLoader(umt5_xxl_fp8_e4m3fn_scaled.safetensors, wan)`, `VAELoader(wan2.2_vae.safetensors)`, `LoadImage(image)` → `Wan22ImageToVideoLatent(width,height,length)` → `ModelSamplingSD3(shift 8)` → `KSampler(uni_pc, simple, 30 steps, cfg 5)` → `VAEDecode` → `CreateVideo(fps 24)` → `SaveVideo(mp4)`.
- `pod/models.yaml`: list of `{file, repo, path, dest}` (dest = ComfyUI `models/` subfolder) for every model above; URL = `https://huggingface.co/{repo}/resolve/main/{path}` except RealESRGAN (`url:` GitHub release `xinntao/Real-ESRGAN` v0.1.0). HF sources: `Comfy-Org/flux1-dev`, `Comfy-Org/flux1-kontext-dev_ComfyUI`, `comfyanonymous/flux_text_encoders`, `Comfy-Org/Lumina_Image_2.0_Repackaged` (ae), `Comfy-Org/Wan_2.2_ComfyUI_Repackaged`, `Comfy-Org/Wan_2.1_ComfyUI_repackaged` (umt5), `Bingsu/adetailer`.

- [ ] **Step 1: Write failing tests.**
  - `test_each_template_has_exact_placeholders` — for each kind, placeholders found == `PLACEHOLDERS[kind]`.
  - `test_render_keeps_types` — `seed=42` stays `int` in output.
  - `test_render_unfilled_raises` / `test_render_unused_value_raises`.
  - `test_graph_links_valid` — every `[node_id, idx]` input references an existing node id.
  - `test_every_model_file_in_manifest` — `model_files(t)` ⊆ `{m.file for m in models.yaml}` for all templates (LoRA placeholder excluded).
  - `test_manifest_dests_are_comfy_folders` — dest ∈ `{checkpoints, diffusion_models, text_encoders, vae, loras, upscale_models, ultralytics/bbox}`.
  - Client (respx): `test_queue_returns_prompt_id`; `test_queue_node_error_is_readable` — 400 body with `node_errors` for `UNETLoader` `value_not_in_list` → `ComfyError` message contains node class and `wan2.2_ti2v_5B_fp16.safetensors`; `test_wait_polls_until_history_present`; `test_wait_raises_on_execution_error` (history `status.status_str == "error"`); `test_wait_timeout`; `test_outputs_collects_images_and_videos` (keys `images`, `gifs`, `videos`); `test_download_writes_file`; `test_upload_image_returns_name`.

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** templates, `workflow.py`, `comfy_client.py` (httpx; endpoints `POST /prompt`, `GET /history/{id}`, `GET /view?filename=&subfolder=&type=`, `POST /upload/image`, `GET /system_stats` for ping). **Step 4: Run** → PASS. **Step 5: Commit** `feat: ComfyUI workflow templates, model manifest, API client`.

---

### Task 5: Batch runner and `cm batch`

**Files:**
- Create: `src/comfy_model/batch.py`; Modify: `src/comfy_model/cli.py`
- Test: `tests/test_batch.py`

**Interfaces:**
- Consumes: `load_scenes`, `Profile.photo_prompt`, `load_template`, `render`, `ComfyClient`, `config`
- Produces:
  - `BatchReport` dataclass `done: list[Path], skipped: list[Path], failed: list[tuple[str, str]]`
  - `run_batch(kind: str, scenes_path: Path, client: ComfyClient, profile: Profile, out_dir: Path, *, ref_image: Path | None = None, lora: str | None = None, lora_strength: float = 0.9) -> BatchReport`
  - Output naming: `out_dir/<scene_id>_<n:02d>.<png|mp4>` (n from 1); `out_dir/manifest.jsonl` one line per output `{scene_id, n, seed, prompt, file, kind}`.
  - CLI: `cm batch {face|dataset|photo|video} SCENES [--out out/<date>-<kind>] [--ref PATH] [--lora NAME] [--strength 0.9]`
- Rules: whole file validated before first queue; `seed = scene.seed + n - 1` if set else random 0..2**32-1 (recorded); `use_trigger = (kind == "photo")`; dataset scenes are Kontext instructions and use `ref_image` uploaded once; video scenes upload `scene.image` and use `profile.video_negative`, `length = 121`. `face` kind queues once per scene with `batch_size = count` (outputs numbered from history order). One scene failing (`ComfyError`) is recorded in `failed` and the batch continues, except a node-validation error (missing model) which aborts the batch.

- [ ] **Step 1: Write failing tests** (fake client object implementing the client methods):
  - `test_rerun_skips_existing_outputs` — pre-create `desk_01.png`; scene count 2 → only n=2 queued; report.skipped has `desk_01.png`.
  - `test_invalid_file_queues_nothing` — one invalid scene → `SceneError`, fake client `queue` never called.
  - `test_seed_from_scene_is_deterministic` — seed 100, count 3 → seeds 100,101,102 in manifest.
  - `test_photo_uses_trigger_and_lora` — rendered workflow contains `"ohwxzosia, "` prefix and `lora_name`.
  - `test_photo_requires_lora` — `kind="photo"` with `lora=None` → `ValueError` mentioning `--lora`.
  - `test_dataset_requires_ref`.
  - `test_execution_error_recorded_and_batch_continues`.
  - `test_missing_model_aborts_batch`.
  - `test_manifest_lines_written`.

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** `run_batch` + CLI command (ComfyUI URL from `--url`, else key `comfy_url` read directly from `.cm/pod.json`; Task 8 later swaps this for `current_pod()`; prints a summary line per scene). **Step 4: Run** → PASS. **Step 5: Commit** `feat: idempotent batch generation`.

---

### Task 6: Export for posting (`cm export`)

**Files:**
- Create: `src/comfy_model/export.py`; Modify: `cli.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Produces: `export_image(src: Path, dest_dir: Path, *, grain: float = 0.03, quality: int = 92) -> Path`; CLI `cm export FILES... [--to export/] [--grain 0.03]`. Videos (`.mp4`) are copied as-is.
- Behavior: output JPEG `dest_dir/<stem>.jpg`; all PNG text chunks (ComfyUI embeds `prompt`/`workflow` — would leak prompts) dropped; EXIF `ImageDescription = "AI-generated image"` and `Software = "AI-generated"` set; monochrome gaussian grain with std `grain * 255`, deterministic seed from file name.

- [ ] **Step 1: Write failing tests:** `test_workflow_metadata_stripped` (source PNG with `prompt` text chunk → output has no `prompt` in `img.info` nor bytes); `test_ai_label_in_exif`; `test_grain_zero_is_near_identical` (mean abs diff < 1 at grain 0 aside from JPEG); `test_grain_deterministic`; `test_mp4_copied`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (Pillow + `random.Random`/`Image.effect_noise`). **Step 4: Run** → PASS. **Step 5: Commit** `feat: export with AI label and prompt-metadata stripping`.

---

### Task 7: Idle watchdog (runs on the pod)

**Files:**
- Create: `src/comfy_model/watchdog.py` (**stdlib only** — it is copied to the pod and run with system python)
- Test: `tests/test_watchdog.py`

**Interfaces:**
- Produces:
  - `decide(now: float, started_at: float, last_busy_at: float, busy: bool, idle_timeout_s: float, max_runtime_s: float) -> str | None` — returns `"max_runtime"` if `now - started_at >= max_runtime_s`, else `"idle"` if `not busy and now - last_busy_at >= idle_timeout_s`, else `None`.
  - `comfy_busy(base_url: str) -> bool` — `GET /queue`; busy if `queue_running` or `queue_pending` non-empty; **an unreachable ComfyUI counts as not busy**.
  - `ssh_busy() -> bool` — true if a file `/workspace/.cm/busy` exists with mtime < 10 min (written by `cm lora train` heartbeats, Task 9).
  - `main()` — env `IDLE_TIMEOUT_MIN`, `MAX_RUNTIME_H`, `COMFY_URL`; polls every 30 s; on decision logs reason to `/workspace/.cm/watchdog.log` and runs `runpodctl remove pod $RUNPOD_POD_ID` (network-volume pods are terminated, not stopped; all state lives on `/workspace`).

- [ ] **Step 1: Write failing tests:** `test_idle_after_timeout`; `test_busy_resets_idle` (busy at t=14 min → no shutdown at t=20 min with timeout 15 if last_busy_at=14 min); `test_max_runtime_wins_even_when_busy`; `test_unreachable_comfy_is_not_busy` (port with nothing listening); `test_queue_parsing_busy` (local `http.server` stub returning `{"queue_running": [[1]], "queue_pending": []}`); `test_module_imports_only_stdlib` (parse AST imports, all in `sys.stdlib_module_names`).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS. **Step 5: Commit** `feat: pod idle/max-runtime watchdog`.

---

### Task 8: Pod lifecycle (`cm pod up|status|down`) and bootstrap

**Files:**
- Create: `src/comfy_model/runpod_pod.py`, `src/comfy_model/remote.py`, `pod/bootstrap.sh`, `pod/versions.env`; Modify: `cli.py`
- Test: `tests/test_runpod_pod.py`, `tests/test_remote.py`, `tests/test_bootstrap.py`

**Interfaces:**
- Consumes: `Settings`, `load_secrets`, `watchdog.py` (copied), `pod/models.yaml`, `workflows/`
- Produces:
  - `PodInfo` dataclass `id: str, ssh_host: str, ssh_port: int, comfy_url: str` (`comfy_url = f"https://{id}-{port}.proxy.runpod.net"`)
  - `runpod_pod.create(settings, secrets) -> str` (pod id; `runpod.create_pod` with `gpu_type_id`, `cloud_type="SECURE"`, `network_volume_id`, `volume_mount_path="/workspace"`, `ports="8188/http,22/tcp"`, `support_public_ip=True`, env `PUBLIC_KEY` = `~/.ssh/id_ed25519.pub` contents, `RUNPOD_API_KEY`, `HF_TOKEN`, `IDLE_TIMEOUT_MIN`, `MAX_RUNTIME_H`)
  - `runpod_pod.wait_ready(pod_id, timeout_s=600) -> PodInfo` (polls `runpod.get_pod` until public port 22 mapping appears)
  - `runpod_pod.terminate(pod_id) -> None`; `runpod_pod.exists(pod_id) -> bool`
  - `runpod_pod.current_pod(state: Path = Path(".cm/pod.json")) -> PodInfo | None` — returns `None` **and deletes the state file** if the pod no longer exists.
  - `remote.rsync_argv(pod: PodInfo, local: list[Path], remote_dir: str) -> list[str]`; `remote.ssh_argv(pod: PodInfo, command: str) -> list[str]` (`-o StrictHostKeyChecking=accept-new -p <port> root@<host>`); `remote.run(argv) -> int` (subprocess, streams output).
  - `cm batch` (Task 5) switched to `current_pod()` so a stale state gives the "no running pod" message.
  - CLI: `cm pod up` (refuse if a pod is already running; create → wait → rsync `pod/ workflows/ src/comfy_model/watchdog.py` to `/workspace/cm/` → ssh `bash /workspace/cm/pod/bootstrap.sh` → poll `ComfyClient.ping` up to 10 min → write state → print ComfyUI URL and "auto-off after 15 min idle / 4 h max"); `cm pod status`; `cm pod down` (terminate + delete state); `cm pod ssh`.
- `pod/bootstrap.sh` (idempotent, `set -euo pipefail`): venv at `/workspace/venv`; clone ComfyUI at `$COMFYUI_TAG` and custom nodes `ComfyUI-Impact-Pack`, `ComfyUI-Impact-Subpack` at pinned commits from `pod/versions.env` only if missing; install their requirements; download each `pod/models.yaml` entry to `/workspace/ComfyUI/models/<dest>/<file>` only if missing (curl `-fL -C -`, `Authorization: Bearer $HF_TOKEN` when set, to `.part` then `mv`); symlink nothing outside `/workspace`; start ComfyUI with `nohup … --listen 0.0.0.0 --port 8188` unless already listening; start `watchdog.py` with `nohup` unless running (pidfile `/workspace/.cm/watchdog.pid`).
- `pod/versions.env`: `COMFYUI_TAG`, `IMPACT_PACK_COMMIT`, `IMPACT_SUBPACK_COMMIT`, `AI_TOOLKIT_COMMIT` — latest release tag / HEAD commit at implementation time, pinned.

- [ ] **Step 1: Write failing tests** (monkeypatch `runpod` module functions):
  - `test_create_passes_volume_and_env` — call kwargs include `network_volume_id`, `cloud_type="SECURE"`, env keys above; no secret value appears in any log output captured.
  - `test_missing_api_key_message` — no `RUNPOD_API_KEY` → `ConfigError` mentioning `.env`.
  - `test_wait_ready_parses_ssh_port`.
  - `test_status_clears_stale_state` — state file present, `get_pod` returns None → `current_pod()` is None and file gone; CLI `cm pod status` exit 0 printing `no running pod`.
  - `test_up_refuses_when_running`.
  - `test_ssh_argv` / `test_rsync_argv` exact lists.
  - `test_bootstrap_shellcheck` — `shellcheck pod/bootstrap.sh` exits 0 (skip if shellcheck absent).
  - `test_bootstrap_reads_manifest_paths` — run bootstrap's manifest-to-paths helper (`bootstrap.sh --print-downloads` mode that prints `url dest` lines without downloading) against `pod/models.yaml`; every model file appears once.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS. **Step 5: Verify model URLs resolve:** `uv run python -m comfy_model.config --check-urls` (or a one-off script) issues HEAD for each manifest URL → all 200/302 (gated ones may 401 without `HF_TOKEN`; none should 404). **Step 6: Commit** `feat: RunPod pod lifecycle and idempotent bootstrap`.

---

### Task 9: LoRA dataset prep and training (`cm lora prepare|train`)

**Files:**
- Create: `src/comfy_model/lora.py`, `training/lora_flux.yaml`; Modify: `cli.py`, `pod/versions.env` (already has `AI_TOOLKIT_COMMIT`)
- Test: `tests/test_lora.py`

**Interfaces:**
- Consumes: `manifest.jsonl` from Task 5 dataset batch, `Profile`, `PodInfo`, `remote`
- Produces:
  - `prepare_dataset(src_dir: Path, dest_dir: Path, profile: Profile) -> int` — copies the operator's curated images (whatever remains in `src_dir` after manual deletion) to `dest_dir/img_NNN.png` + `img_NNN.txt` caption = `"{trigger}, {scene prompt from manifest}"`; images without a manifest line get caption `"{trigger}, a photo of a woman"`; returns count; raises `ValueError` if count < 15 or > 60.
  - `render_training_config(profile: Profile, version: int) -> str` — from `training/lora_flux.yaml`: ai-toolkit `sd_trainer`, base `black-forest-labs/FLUX.1-dev`, `is_flux: true`, `quantize: true`, network `lora` rank 16 / alpha 16, `lr: 1e-4`, `steps: 2000`, `save_every: 500`, `resolution: [512, 768, 1024]`, `batch_size: 1`, `trigger_word` = profile.trigger, dataset `/workspace/dataset/<trigger>`, output name `<trigger>_v<version>`, sample prompts = 3 lines from profile.
  - CLI: `cm lora prepare SRC [--to dataset/<trigger>]`; `cm lora train [--version 1]` → rsync dataset + rendered config, ssh: install ai-toolkit at pinned commit into `/workspace/ai-toolkit` if missing, run training under `nohup` with a heartbeat loop touching `/workspace/.cm/busy` every 60 s (so the watchdog does not kill training), on finish copy final `.safetensors` to `/workspace/ComfyUI/models/loras/`; `cm lora status` tails the log.
- [ ] **Step 1: Write failing tests:** `test_prepare_numbers_and_captions`; `test_prepare_uses_manifest_prompt`; `test_prepare_rejects_too_few`; `test_training_config_values` (parse rendered YAML: trigger `ohwxzosia`, rank 16, steps 2000, lr 1e-4, output name `ohwxzosia_v1`); `test_train_remote_command_has_heartbeat` (built ssh command string contains `/workspace/.cm/busy`).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS. **Step 5: Commit** `feat: LoRA dataset prep and remote training`.

---

### Task 10: Scene libraries

**Files:**
- Create: `scenes/face.yaml` (6 scenes × count 4: neutral portraits, different light), `scenes/dataset.yaml` (40 Kontext instructions: angles front/¾/profile, close-up/half/full body, 6+ outfits incl. hoodie+glasses, dress, gym wear, swimsuit; indoor/outdoor; day/evening light — every one starts "Keep the same woman's face and identity, "), `scenes/instagram.yaml` (≥20), `scenes/social.yaml` (≥15, may use lingerie), `scenes/fanvue.yaml` (≥15, lingerie/suggestive, no nudity), `scenes/video.yaml` (≥6, `image:` pointing at `export/` examples, subtle motion: hair in wind, typing, sipping coffee, turning to camera).
- Test: `tests/test_scene_library.py`

- [ ] **Step 1: Write failing test** `test_all_library_files_valid` — each file loads with its kind (`face`, `dataset`, `photo` ×3, `video`) without `SceneError`; tiers match file names; `test_instagram_has_it_content` — ≥5 instagram prompts contain one of `monitor|laptop|terminal|server|keyboard|on-call`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Write the YAML files** (English prompts; IT-life + lifestyle + travel per bible). **Step 4: Run** → PASS. **Step 5: Commit** `feat: scene libraries per platform`.

---

### Task 11: Validate workflows against real ComfyUI (CPU)

**Files:**
- Create: `scripts/validate_workflows.py`
- Test: the script itself is the check (exit code).

**Interfaces:**
- Consumes: `pod/versions.env`, `pod/models.yaml`, `workflow.render`, `load_template`, `PLACEHOLDERS`
- Behavior: in a temp dir clone ComfyUI at `COMFYUI_TAG` + the two Impact repos at pinned commits, install CPU torch + requirements, create **empty placeholder files** for every manifest model and a dummy `ohwxzosia_v1.safetensors` LoRA and a 64×64 input image, start `main.py --cpu --port 18188`, render every template with sample values, `POST /prompt`, require HTTP 200 with empty `node_errors`, then `POST /interrupt` + clear queue, stop server. Prints a per-workflow OK/FAIL table; exit 1 on any FAIL.

- [ ] **Step 1: Run** `uv run python scripts/validate_workflows.py` → expect FAIL first time only if templates have wrong node names/inputs; fix templates (Task 4 files) until all four print OK.
- [ ] **Step 2: Run** `uv run pytest` → all PASS.
- [ ] **Step 3: Commit** `test: validate workflow graphs against pinned ComfyUI`.

---

### Task 12: Russian operator guide and launch checklist

**Files:**
- Create: `docs/guide/01-setup.md`, `02-create-face.md`, `03-train-lora.md`, `04-daily.md`, `05-video.md`, `06-launch.md`, `README.md` (RU, short, links to guide)
- Test: `tests/test_docs.py`

Content (Russian, commands copy-pasteable):
- **01-setup:** RunPod account + top-up ($10 to start), API key, create 100 GB network volume in the EU datacenter from settings, HuggingFace account + accept FLUX.1-dev license + read token, SSH key, `.env` from `.env.example`, `uv sync`, `cm pod up`, open ComfyUI URL, `cm pod down`. Cost table from the spec §7.
- **02-create-face:** `cm batch face scenes/face.yaml` → choose one face (check: adult-looking, not resembling anyone famous — reverse image search via Google Lens/Yandex), `cm batch dataset scenes/dataset.yaml --ref …` → delete bad ones by hand.
- **03-train-lora:** `cm lora prepare`, `cm lora train`, `cm lora status`, how to judge samples, retrain with `--version 2`.
- **04-daily:** the 2–3 h routine from spec §8.7; `cm batch photo scenes/instagram.yaml --lora ohwxzosia_v1.safetensors`, picking, `cm export`, how to add own scenes.
- **05-video:** `cm batch video scenes/video.yaml`.
- **06-launch:** platform checklist — Instagram (creator account, "AI info" label on every post, SFW only), Reddit and X (AI disclosure in profile, read each subreddit's AI rules), Telegram (free teaser channel, link to Fanvue), Fanvue (ID verification as operator, AI-creator labeling, payout to EU bank), legal (EU AI Act labeling, declare income as self-employed per country), content plan from spec §6 table, 3-month target $500+/mo net ≈ $625 gross, weekly metrics to track (followers per platform, Fanvue subs, revenue).

- [ ] **Step 1: Write failing test** `test_guide_commands_exist` — every `cm <group> <cmd>` mentioned in `docs/guide/*.md` exists in `cli.app` (via `typer.testing.CliRunner` `--help`); `test_guide_mentions_ai_label` — `06-launch.md` contains "ИИ" label instructions for each of Instagram, Reddit, X, Telegram, Fanvue.
- [ ] **Step 2: Run** → FAIL. **Step 3: Write docs.** **Step 4: Run** → PASS; `uv run pytest` all green. **Step 5: Commit** `docs: Russian operator guide and launch checklist`.

---

## Out of scope (from spec §3)

Second persona, explicit Fanvue tier, autoposting, chat bot, paid Telegram, local PC.
