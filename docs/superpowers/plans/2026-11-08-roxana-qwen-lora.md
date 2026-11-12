# Roxana Qwen Dataset and LoRA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** From the chosen face `out/qwen-faces-2/phone-2.png`, build a Qwen-Image-Edit dataset, train a Qwen-Image 2512 LoRA with trigger `ohwxroxana`, and verify it on six scenes including the low-angle armchair.

**Architecture:** Add a `--workflows` directory to `cm batch` and a `--base qwen` training option, leaving FLUX defaults intact. Qwen graphs live in `workflows/qwen/`, models in `pod/qwen_models.yaml`. Production migration (`workflows/{face,dataset,photo}.json`, `pod/models.yaml`, `style_suffix`, Instagram scenes) stays in a later plan.

**Tech Stack:** Python 3.11+, typer, pytest; ComfyUI v0.40.0 API-format JSON; ai-toolkit at the commit pinned in `pod/versions.env`.

**Spec:** `docs/superpowers/specs/2026-11-08-roxana-photoreal-bakeoff-design.md` (Stage 2).

## Global Constraints

- No commit, push, publication, pod or volume change without the operator's explicit yes. Task 5 asks for each.
- No FLUX model or FLUX output (Kontext included) in the face, dataset or LoRA.
- `safety.py` tiers and ban lists are not changed. `character/profile.yaml` appearance must start with a stated adult age of 35–49.
- Power the pod off (`cm pod down`) as soon as each generation or training session ends, and confirm with `cm pod status`.
- Tests run as `.venv/bin/python -m pytest`; commands as `.venv/bin/cm`. Seven tests fail on macOS only for lack of `setsid` (`test_bootstrap_full_run_simulated` and six `test_lora` train-script tests); hold the suite to exactly those.
- `tests/test_config.py:11` and the current `config/settings.yaml` (RTX 5090, EUR-NO-1) already disagree; leave both until the later migration plan.

## Review Focus

1. `cm lora train` with no `--base`: FLUX behaviour, including the HF_TOKEN requirement, is unchanged (Task 3).
2. `--base qwen` with no `HF_TOKEN`: training starts, because Qwen is not gated (Task 3).
3. `--workflows` pointing at a directory without that kind: readable error, nothing queued (Task 1).
4. Unknown `--base` value: refused before any sync to the pod (Task 3).
5. Default `cm batch` still uses `workflows/` (Task 1).

---

### Task 1: Selectable workflow directory for `cm batch`

**Files:**
- Modify: `src/comfy_model/batch.py` (`run_batch`, `load_template` call at `:124`), `src/comfy_model/cli.py` (`batch`, `:78-`)
- Test: `tests/test_batch.py`

**Interfaces:**
- Produces: `run_batch(..., workflows_dir: Path = Path("workflows"))`; `cm batch ... --workflows DIR`.

- [ ] **Step 1: Write failing tests** in `tests/test_batch.py`, using that file's existing fake client and scene helpers:

```python
def test_workflows_dir_selects_the_template(tmp_path): ...    # a modified dataset.json in tmp dir is the graph queued
def test_default_workflows_dir_is_repo_workflows(tmp_path): ...  # no argument: same graph as before
def test_missing_kind_in_workflows_dir_queues_nothing(tmp_path): ...  # TemplateError (a ValueError), client.queue never called
```

- [ ] **Step 2: Run, expect FAIL.** Run: `.venv/bin/python -m pytest -q tests/test_batch.py`

- [ ] **Step 3: Implement.** Pass `workflows_dir` to `load_template(kind, workflows_dir)` before the output dir is created. CLI option `workflows: Path = typer.Option(Path("workflows"), "--workflows", help=...)`; `TemplateError` is already reported through the `ValueError` handler.

- [ ] **Step 4: Run tests, expect PASS.**

### Task 2: Qwen graphs, manifest, scenes

**Files:**
- Create: `workflows/qwen/dataset.json`, `workflows/qwen/photo.json`, `pod/qwen_models.yaml`, `scenes/dataset_qwen.yaml`, `scenes/lora_check.yaml`
- Test: `tests/test_qwen_pipeline.py`

**Interfaces:**
- Produces: paths above; `QWEN_MANIFEST = Path("pod/qwen_models.yaml")` and `QWEN_WORKFLOWS = Path("workflows/qwen")` as test constants.

- [ ] **Step 1: Write failing tests**

```python
@pytest.mark.parametrize("kind", ["dataset", "photo"])
def test_placeholders_match_batch(kind):
    assert placeholders(load_template(kind, QWEN_WORKFLOWS)) == PLACEHOLDERS[kind]
@pytest.mark.parametrize("kind", ["dataset", "photo"])
def test_links_valid(kind): ...                 # same assertions as test_workflow.py::test_graph_links_valid
def test_manifest_covers_exactly_the_graphs():
    used = {v.split("/")[-1] for k in ("dataset", "photo") for v in model_files(load_template(k, QWEN_WORKFLOWS))}
    assert used == {m.file for m in load_manifest(QWEN_MANIFEST)}
def test_no_flux_in_qwen_graphs(): ...          # "flux1" and "kontext" absent from every model filename
def test_dataset_sampler():                     # KSampler steps 40, cfg 4, euler, simple, denoise 1, seed "{{seed}}"
def test_edit_encoder_has_the_reference():      # both TextEncodeQwenImageEditPlus link image1 to the scaled reference
def test_photo_has_lora_on_every_sampler():     # both KSampler models and FaceDetailer trace to the LoraLoaderModelOnly
def test_dataset_scenes():
    s = load_scenes(Path("scenes/dataset_qwen.yaml"), "dataset")
    assert len(s) == 30 and all(x.prompt.startswith("Keep the same woman's face and identity,") for x in s)
def test_check_scenes():
    s = load_scenes(Path("scenes/lora_check.yaml"), "photo")
    assert len(s) == 6 and "home-armchair-low-angle" in [x.id for x in s]
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Write `pod/qwen_models.yaml`:** the `qwen_image_2512_fp8_e4m3fn`, `qwen_2.5_vl_7b_fp8_scaled`, `qwen_image_vae` and `face_yolov8m.pt` entries from `pod/bakeoff_models.yaml`, plus `qwen_image_edit_2511_fp8mixed.safetensors` (dest `diffusion_models`, repo `Comfy-Org/Qwen-Image-Edit_ComfyUI`, path `split_files/diffusion_models/…`).

- [ ] **Step 4: Write `workflows/qwen/dataset.json`** from official template `image_qwen_image_edit_2511.json`, non-Lightning path, one reference: `LoadImage` (`{{ref_image}}`) → `FluxKontextImageScale`; `UNETLoader` (`qwen_image_edit_2511_fp8mixed`) → `ModelSamplingAuraFlow` 3.1 → `CFGNorm` 1; `CLIPLoader` (`qwen_2.5_vl_7b_fp8_scaled`, `qwen_image`); `VAELoader`; two `TextEncodeQwenImageEditPlus` (positive `{{prompt}}`, negative empty; `clip`, `vae`, `image1` = scaled reference), each through `FluxKontextMultiReferenceLatentMethod` `index_timestep_zero`; `VAEEncode` of the scaled reference; `KSampler` as tested; `VAEDecode`; `SaveImage` `{{filename_prefix}}`.

- [ ] **Step 5: Write `workflows/qwen/photo.json`:** copy `workflows/bakeoff/qwen_2512.json`, insert `LoraLoaderModelOnly` (`{{lora_name}}`, `{{lora_strength}}`) between `ModelSamplingAuraFlow` and all model consumers, remove the `{{filename_prefix_face}}` SaveImage, replace literal width and height placeholders as batch fills them.

- [ ] **Step 6: Write `scenes/dataset_qwen.yaml`:** copy `scenes/dataset.yaml` without `swimsuit-beach-walk`, `swimsuit-sunlounger`, `car-back-seat`, `boutique-shopping`, `restaurant-dinner`, `rain-umbrella`, `bookshelf-reading`, `mirror-reflection`, `elevator-glass`, `desert-camel-sunset`.

- [ ] **Step 7: Write `scenes/lora_check.yaml`,** kind `photo`, tier `instagram`, count 1, aspect `4:5`, six scenes: `penthouse-skyline-gown`, `boardroom-head-of-table`, `yacht-deck-white-linen`, `glass-desk-office`, verbatim from `scenes/instagram.yaml`; `mirror-selfie-home`, verbatim from `scenes/bakeoff.yaml`; and `home-armchair-low-angle`: `seated in a deep black leather armchair in her modern living room at home, legs crossed, black silk blouse and tailored black trousers, warm evening lamp light, camera very low near the floor looking up at her, she looks down into the lens with a cold confident gaze`.

- [ ] **Step 8: Run tests and verify URLs.** Run: `PYTHONPATH=src .venv/bin/python -m comfy_model.workflow --check-urls pod/qwen_models.yaml`. Expected: `5/5 reachable`.

### Task 3: Qwen training option and the chosen look

**Files:**
- Create: `training/lora_qwen.yaml`
- Modify: `src/comfy_model/lora.py`, `src/comfy_model/cli.py` (`lora_train`, HF check `:515-522`, config render `:531`), `pod/train_lora.sh` (HF check, `FLUX` comment), `character/profile.yaml`
- Test: `tests/test_lora.py`, `tests/test_profile.py`

**Interfaces:**
- Produces: `TEMPLATES: dict[str, Path] = {"flux": Path("training/lora_flux.yaml"), "qwen": Path("training/lora_qwen.yaml")}` in `lora.py`; `cm lora train --base flux|qwen` (default `flux`).

- [ ] **Step 1: Write failing tests**

```python
def test_qwen_training_config():
    cfg = yaml.safe_load(render_training_config(PROFILE, 1, TEMPLATES["qwen"]))
    p = cfg["config"]["process"][0]
    assert p["model"]["name_or_path"] == "Qwen/Qwen-Image-2512" and p["model"]["arch"] == "qwen_image"
    assert p["model"]["qtype"] == "qfloat8" and p["train"]["steps"] == 2000
    assert p["trigger_word"] == "ohwxroxana" and "{{" not in yaml.safe_dump(cfg)
def test_cli_train_qwen_needs_no_hf_token(...): ...        # fake_remote: exit 0, launches, without HF_TOKEN
def test_cli_train_default_still_needs_hf_token(...): ...  # existing behaviour, no flag
def test_cli_train_unknown_base_syncs_nothing(...): ...    # exit 1, fake_remote never called
def test_train_script_skips_hf_check_for_qwen(tmp_path):   # a qwen config: "HF_TOKEN" not in stderr, whatever happens after
def test_train_script_still_requires_hf_for_flux(tmp_path): ...  # config naming black-forest-labs: dies with HF_TOKEN message

# tests/test_profile.py
def test_profile_is_the_chosen_look():
    assert load_profile().appearance.startswith("37-year-old woman, strikingly attractive")
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Write `training/lora_qwen.yaml`** from `config/examples/train_lora_qwen_image_24gb.yaml` at the pinned commit, in the shape of `training/lora_flux.yaml` (same placeholders, `trigger_word`, `save_every: 500`, `max_step_saves_to_keep: 4`, dataset path, `sample_every: 500`, `prompts: "{{sample_prompts}}"`), with `name_or_path: Qwen/Qwen-Image-2512`, `arch: qwen_image`, `quantize: true`, `qtype: qfloat8`, `quantize_te: true`, `qtype_te: qfloat8`, `low_vram: true`, `cache_text_embeddings: true`, `lr: 0.0001`, `guidance_scale: 3`, `sample_steps: 25`.

- [ ] **Step 4: Implement.** `lora_train` gains `base: str = typer.Option("flux", "--base")`, rejected before any remote call if not in `TEMPLATES`; the HF_TOKEN check runs only for `flux`. In `train_lora.sh`, require `HF_TOKEN` only when `$CONFIG_DIR/$NAME.yaml` contains `black-forest-labs`, after the config-exists check.

- [ ] **Step 5: Set `appearance` in `character/profile.yaml`** to: `37-year-old woman, strikingly attractive, naturally plump full lips with soft matte red lipstick, smooth healthy skin with natural texture and visible pores, long sleek glossy dark brunette hair in a high ponytail, dark brown eyes with a sultry half-lidded gaze, defined cheekbones, elegant makeup, oxblood nails, full bust, slim waist, toned curvy figure`. `style_suffix` stays until the migration plan.

- [ ] **Step 6: Run the full suite.** Expected: only the seven macOS failures.

### Task 4: Operator guide

**Files:**
- Create: `docs/guide/09-qwen-lora.md`
- Test: `tests/test_docs.py`

- [ ] **Step 1: Write the guide (Russian):** growing `bakeoff-no` to 200 GB because the Hugging Face cache needs about 58 GB more; dataset session (`cm pod up --models pod/qwen_models.yaml`; `cm batch dataset scenes/dataset_qwen.yaml --ref out/qwen-faces-2/phone-2.png --workflows workflows/qwen --out out/qwen-dataset`; `cm pod down`); culling to 15–30 by face match; `cm lora prepare out/qwen-dataset`; training on a fresh pod (`cm lora train --base qwen`, `cm lora status`, because `cm lora train` refuses a pod older than 1 h); verification (`cm batch photo scenes/lora_check.yaml --lora ohwxroxana_v1.safetensors --workflows workflows/qwen`); `cm pod down`; expected cost $5–7 as an estimate.

- [ ] **Step 2: Run** `.venv/bin/python -m pytest -q tests/test_docs.py`. Expected: PASS.

### Task 5: Hand-off and pod sessions (operator's go-ahead required)

- [ ] **Step 1: Ask the operator** about committing, showing `git status`; commit only on a yes, with the session's attribution line.

- [ ] **Step 2: Confirm prerequisites with the operator:** reverse image search of `phone-2.png` is clear; RunPod topped up by about $10; permission to grow `bakeoff-no` to 200 GB (about $14/month until deleted).

- [ ] **Step 3: Dataset session.** Bring the pod up, run one frame by a temporary one-scene copy of the file, open it and check the face matches `phone-2`, then the 30 scenes. `cm pod down`, confirm with `cm pod status`. Send the numbered contact sheet.
Expected: 30 images, reference pose not copied in most. If the face drifts in most frames, stop and report.

- [ ] **Step 4: Operator culls, then texture pass.** At the start of the training pod run `cm lora refine out/qwen-dataset --out out/qwen-dataset-refined`, then `cm lora prepare out/qwen-dataset-refined`. Added at the operator's request: Qwen-Edit gloss. Expected: 15–30 images and captions in `dataset/ohwxroxana/`.

- [ ] **Step 5: Training session.** Fresh pod; `cm lora train --base qwen`. After the first 500-step sample, open it to confirm training is sane. If the 4-hour limit or a crash ends training, report rather than restart.
Expected: `ohwxroxana_v1.safetensors` in ComfyUI's loras folder.

- [ ] **Step 6: Verification.** On the same pod, run `scenes/lora_check.yaml`. `cm pod down`, confirm. Send the six frames.
Expected per `docs/guide/03-train-lora.md`: the same face across angles, living skin, frames not copying the dataset. On failure, per spec, one dataset rebuild and retrain, with the operator's go-ahead.
