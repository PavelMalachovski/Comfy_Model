# Roxana Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Greta persona with Roxana across the repo and give the operator everything for phase 1: a tiered safety filter for the femdom niche on Flux, Roxana's profile and bible, the starter scene libraries (30 Instagram photos, 3–5 Reels, X/Reddit/Telegram set, face and LoRA dataset), a Mac setup guide and a 3-month warm-up plan.

**Architecture:** No new subsystems. The existing `cm` pipeline (Flux on RunPod) stays; this plan changes data (profile, bible, scenes), one rule table in `safety.py`, test fixtures and the Russian guide. Phases 2–4 of the spec (feet detailer, SDXL Fanvue tier, reply-draft tool) are separate plans.

**Tech Stack:** Python 3.11+, uv, pytest; YAML scene files; Markdown docs (RU).

**Spec:** `docs/superpowers/specs/2026-11-07-roxana-femdom-design.md` (phase 1 per §11). Base pipeline spec: `docs/superpowers/specs/2026-10-14-ai-model-it-girl-design.md`.

## Global Constraints

- Persona: Roxana ("Roxy"), about 40, clearly adult, brunette, white/European look, very sexy and uninhibited; dominant Mistress/"queen", treats men as slaves (roleplay); from Siberia, lives in Dubai; ex-top-manager; light Russian accent in English; oxblood manicure + pedicure as signature; no surname.
- LoRA trigger token: `ohwxroxana`.
- Audience English; operator docs Russian; persona-written text English.
- Tiers in phase 1: `instagram` (SFW showcase: no lingerie, no latex/fetish cues), `social` (X, Reddit, free + paid Telegram: latex, lingerie, boots, heels allowed), `fanvue` (same as social in phase 1 — topless with pasties arrives in phase 3). No nudity, minors, real-person likeness on any tier (unchanged).
- Public text never attacks men as a group (Instagram hate-speech rules); contempt only as roleplay, harsher only behind paywall.
- AI label in every profile and in captions where the platform supports it.
- Greta removed everywhere except `docs/superpowers/` (history).
- Budget, GPU, watchdog, export behaviour: unchanged.

## Review Focus

1. **Operator writes an Instagram scene with a fetish cue** ("latex catsuit", "foot worship", "slave kneeling") → rejected on `instagram` with the term named, accepted on `social`. (Task 1 tests.)
2. **Fetish-safe words must not trip the Instagram filter** ("leather trench coat", "knee-high boots", "heels", "power suit") → pass on `instagram`; "stockings"/"fishnets" are banned there as fetish cues. (Task 1 `test_instagram_allows_power_dressing`.)
3. **A stray `ohwxgreta` / "Greta" left in code, scenes or guide** makes the operator train or prompt the wrong persona → a repo-wide test fails on any leftover. (Task 4 `test_no_greta_leftovers`.)
4. **Profile age drifts** (operator edits appearance to a younger age) → profile test enforces a stated age 35–49. (Task 2.)
5. **Guide commands drift from the CLI** → existing `tests/test_docs.py` keeps every `cm <group> <cmd>` valid; Mac guide commands included. (Task 4.)

---

### Task 1: Instagram fetish tier in the safety filter

**Files:**
- Modify: `src/comfy_model/safety.py` (rule table)
- Test: `tests/test_safety.py`

**Interfaces:**
- Produces: unchanged `check_prompt(text: str, tier: Tier) -> list[str]`; new rule category `"fetish"` applied to `instagram` only.

- [ ] **Step 1: Write failing tests**

```python
@pytest.mark.parametrize("text", ["black latex catsuit", "PVC dress", "vinyl gloves", "rubber outfit",
    "foot worship", "bare feet close-up", "soles to the camera", "toes", "slave kneeling", "mistress",
    "dominatrix", "femdom", "fetish", "bdsm", "riding crop", "whip", "collar and leash", "stockings", "fishnets"])
def test_fetish_cues_banned_on_instagram_only(text):
    assert check_prompt(text, "instagram")
    assert check_prompt(text, "social") == []
    assert check_prompt(text, "fanvue") == []

@pytest.mark.parametrize("text", ["leather trench coat", "knee-high leather boots", "red-soled heels",
    "black satin evening gown", "tailored power suit", "sitting on a velvet throne-like armchair"])
def test_instagram_allows_power_dressing(text):
    assert check_prompt(text, "instagram") == []
```

- [ ] **Step 2: Run** `uv run pytest tests/test_safety.py -q` → new tests FAIL.
- [ ] **Step 3: Implement** a `_FETISH` rule (category `"fetish"`, `_words(...)` over normalized text) with stems `latex`, `pvc`, `vinyl`, `rubber`, `foot\s?worship`, `feet`, `foot`, `soles?`, `toes?`, `slaves?`, `mistress\w*`, `dominatrix`, `femdom`, `fetish\w*`, `bdsm`, `riding\s?crop`, `whips?`, `collars?`, `leash\w*`, `stockings?`, `fishnets?`, `kneel\w*`; set `TIER_RULES["instagram"] = [*_BASE, _LINGERIE, _FETISH]`. Update the module docstring tier description.
- [ ] **Step 4: Run** `uv run pytest -q` → all pass (if a shipped scene file now fails on `instagram`, that is expected: Task 3 rewrites the libraries — mark only `tests/test_scene_library.py` failures as expected, and note them in the commit message).
- [ ] **Step 5: Commit** `feat: instagram tier bans fetish cues`.

---

### Task 2: Roxana profile and bible (Greta removed)

**Files:**
- Modify: `character/profile.yaml`, `character/bible.md` (rewrite), `tests/test_profile.py`

**Interfaces:**
- Consumes: `Profile`, `load_profile`, `check_prompt`.
- Produces: `name: "Roxana"`, `trigger: "ohwxroxana"`, `appearance` starting `"40-year-old woman"`.

- [ ] **Step 1: Update tests in `tests/test_profile.py`:**
  - `test_profile_has_adult_anchor`: `re.match(r"(3[5-9]|4\d)-year-old woman\b", p.appearance)`.
  - `test_name_and_trigger`: `p.name == "Roxana"` and `p.trigger == "ohwxroxana"`.
  - `test_trigger_only_when_requested`: prefix `"ohwxroxana, "`.
  - `test_profile_text_passes_strictest_tier` stays (`instagram`).
  - `test_bible_example_posts_pass_instagram_rules`: Instagram example posts in the bible pass `instagram`; X/Reddit/Telegram example posts pass `social`. Keep a structure the test can parse (e.g. headings `### Instagram`, `### X`, `### Reddit`, `### Telegram` with posts as `> ` blockquotes under each).
  - New `test_bible_has_platform_bios`: bible contains a bio template per platform (Instagram, X, Reddit, Telegram, Fanvue) each including the literal `AI-generated`.
- [ ] **Step 2: Run** `uv run pytest tests/test_profile.py -q` → FAIL.
- [ ] **Step 3: Write `character/profile.yaml`:** `name: "Roxana"`, `trigger: "ohwxroxana"`, `appearance`: one English sentence starting `40-year-old woman` — long glossy dark brunette hair (sleek or high ponytail), dark brown eyes, defined cheekbones, red lipstick, oxblood manicure, tall, curvy-athletic, confident cold gaze, natural mature skin texture. `style_suffix`: luxury editorial photo, dramatic soft light, sharp focus, realistic skin texture, photorealistic. `video_negative`: keep current terms. Update the header comment to "stated adult age (35–49)".
- [ ] **Step 4: Rewrite `character/bible.md` (Russian; persona text English):** Кто она (Сибирь → Дубай, бывший топ-менеджер, около 40), Внешность (дублирует profile + фирменный oxblood), Характер и голос (Госпожа/королева, мужчины — рабы в ролевой игре; короткие холодные приказы, насмешка, лёгкий русский акцент), Публично vs за пэйволлом (публично — превосходство, без нападок на мужчин как группу; жёстче — только Telegram платный/Fanvue), Примеры постов (≥5 Instagram, ≥3 X, ≥2 Reddit, ≥2 Telegram), Шаблоны bio по площадкам с `AI-generated`, Правила переписки (не обещать встреч, не выдавать себя за реального человека, без давления ради денег, findom не продвигаем), Запреты (из анти-целей спеки §4). Remove all Greta content.
- [ ] **Step 5: Run** `uv run pytest tests/test_profile.py -q` → PASS. **Commit** `feat: Roxana profile and bible replace Greta`.

---

### Task 3: Roxana scene libraries

**Files:**
- Rewrite: `scenes/face.yaml`, `scenes/dataset.yaml`, `scenes/instagram.yaml`, `scenes/social.yaml`, `scenes/fanvue.yaml`, `scenes/video.yaml`
- Modify: `tests/test_scene_library.py`

**Interfaces:**
- Consumes: `load_scenes(path, kind)`, tiers from Task 1, profile from Task 2 (appearance/style auto-prepended to face/photo prompts — scene prompts describe only setting, outfit, pose, light, camera).

- [ ] **Step 1: Update `tests/test_scene_library.py`:**
  - keep: all files valid per kind, header comment with `cm batch`, no implied-nudity cues, no hyphen breaks, social header not targeting Telegram→ **replace** with `test_social_header_mentions_telegram_paid` (social tier now feeds X, Reddit and Telegram).
  - `test_instagram_library_shape`: exactly 30 scenes, `count` 2 each (60 renders → operator picks 30), mix of `4:5` and `9:16`.
  - `test_instagram_has_dubai_luxury`: ≥5 prompts contain one of `dubai|penthouse|yacht|desert|boutique|skyline`.
  - `test_social_library_shape`: ≥15 scenes; ≥5 contain `latex`; ≥3 contain `boots|heels`.
  - `test_fanvue_library_shape`: ≥10 scenes, tier `fanvue`.
  - `test_video_library_shape`: 3–5 scenes, aspect `9:16`, tier `instagram`.
  - `test_dataset_library_shape`: 40 scenes, each prompt starts `"Keep the same woman's face and identity, "`, no lingerie/latex (passes `instagram`).
  - `test_face_library_shape`: 6 scenes × count 4.
  - remove `test_instagram_has_it_content`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Write the YAML files** (English prompts, headers with the run command using `--lora ohwxroxana_v1.safetensors`):
  - **face:** 6 mature-portrait lights (window, golden hour, studio softbox, low-key dramatic, night city neon, warm lamp).
  - **dataset:** 40 Kontext instructions; angles/framing/outfits (power suit, evening gown, leather trench, sportswear, casual cashmere, swimsuit) and Dubai indoor/outdoor light.
  - **instagram (30):** Dubai luxury + power: penthouse with skyline, desert dunes at sunset in a black gown, yacht deck, boutique, rooftop bar, office boardroom, luxury car, throne-like armchair, gloves, leather trench, knee-high boots, red-soled heels.
  - **social (≥15):** latex dresses/catsuits, corsets, lingerie under blazer, boots/heels, POV from below ("camera at floor level looking up"), throne, riding crop, black lingerie on a velvet chair. Opaque, named garments only; no feet close-ups (phase 2).
  - **fanvue (≥10):** same level as social, more intimate settings (bedroom, hotel suite, bath robe belted closed over lingerie); no topless (phase 3).
  - **video (3–5):** 9:16 motion-only prompts: slow walk in heels, pulling on leather gloves, turning to camera with a smirk, hair over shoulder on a yacht; `image:` placeholders `../export/<name>.jpg` with a header comment saying to replace them.
- [ ] **Step 4: Run** `uv run pytest -q` → all pass. **Commit** `feat: Roxana scene libraries`.

---

### Task 4: Greta leftovers, Mac guide, warm-up plan

**Files:**
- Modify: `README.md`, `docs/guide/01-setup.md` … `06-launch.md`, `src/comfy_model/lora.py` (docstrings only, if any), `scripts/validate_workflows.py:49` (`LORA_NAME = "ohwxroxana_v1.safetensors"`), test fixtures in `tests/test_batch.py`, `tests/test_lora.py`, `tests/test_export.py` (rename `greta`/`ohwxgreta` → `roxana`/`ohwxroxana`)
- Create: `docs/guide/00-mac.md`, `docs/guide/07-warmup.md`, `tests/test_no_greta.py`

**Interfaces:**
- Consumes: CLI commands as they exist (`cm pod|batch|lora|export`); trigger `ohwxroxana`.

- [ ] **Step 1: Write failing test `tests/test_no_greta.py::test_no_greta_leftovers`:** walk tracked files (`git ls-files`), skip `docs/superpowers/` and `uv.lock`, assert none contains (case-insensitive) `greta`, `ohwxgreta`, `vaitkut`, `vilnius`, `lithuan`. Extend `tests/test_docs.py` so `docs/guide/00-mac.md` and `07-warmup.md` are included in the command check and must exist.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Rename fixtures and leftovers** listed above; update README (Roxana, phases, link to 00 and 07).
- [ ] **Step 4: Write `docs/guide/00-mac.md` (RU):** MacBook Pro M5 32 ГБ: Homebrew, `git`, `uv`, SSH key (`ssh-keygen -t ed25519`), clone repo, `.env`, `uv sync`, `uv run cm --help`; Draw Things for quick tests (and later loading the LoRA trained on RunPod); Pixelmator Pro/Photoshop for retouch; CapCut/DaVinci Resolve for Reels; what not to run on the Mac (batches, video, LoRA training — use RunPod).
- [ ] **Step 5: Write `docs/guide/07-warmup.md` (RU):** months 1–3 plan per platform (Instagram витрина: 4–5 Reels/нед + сторис; X: ежедневно, sensitive media; Reddit: только сабреддиты, где ИИ разрешён, проверка правил каждого; бесплатный Telegram с первого дня), Instagram risk (link to paid channel + sexual hint = «скрытое предложение секс-услуг» → без откровенного рядом со ссылкой), weekly metrics table (подписчики по площадкам, Telegram, переходы), month-4 launch checklist (Fanvue: публичная часть строго SFW, пометка ИИ; платный Telegram: встроенная подписка за Stars, вывод через Fragment в TON не раньше 21 дня, на iPhone 18+ каналы скрыты), targets from spec §2.
- [ ] **Step 6: Update guides 02–06** for Roxana: trigger names, scene file roles (`instagram` → Instagram + бесплатный Telegram; `social` → X, Reddit, платный Telegram; `fanvue` → Fanvue), and remove Greta/IT content.
- [ ] **Step 7: Run** `uv run pytest -q` → all pass. **Commit** `docs: Roxana guides, Mac setup, warm-up plan; remove Greta`.

---

## Out of scope (later phases, per spec §11)

Phase 2 feet scenes + feet detailer; phase 3 SDXL model + second LoRA + topless-with-pasties tier; phase 4 local reply-draft tool.
