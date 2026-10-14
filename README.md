# cm: ИИ-персона Greta Vaitkutė

CLI для генерации контента вымышленной ИИ-персоны (28 лет, Вильнюс, DevOps/SRE)
в ComfyUI на арендованной RunPod RTX 4090. Площадки: Instagram, Reddit, X, Telegram
(бесплатный тизер), Fanvue (единственная монетизация). Бюджет $50–70 в месяц,
2–3 часа в день. Персонаж вымышленный, взрослый, ни на кого не похож; пометка ИИ везде.

```bash
# нужны uv, git, ssh, rsync и ffmpeg (для экспорта видео)
uv sync
cp .env.example .env     # RUNPOD_API_KEY, RUNPOD_VOLUME_ID, HF_TOKEN
uv run cm --help
```

## Руководство оператора

1. [Установка и первый запуск пода](docs/guide/01-setup.md)
2. [Лицо персонажа и датасет](docs/guide/02-create-face.md)
3. [Обучение LoRA](docs/guide/03-train-lora.md)
4. [Ежедневная работа](docs/guide/04-daily.md)
5. [Короткие видео](docs/guide/05-video.md)
6. [Чек-лист запуска площадок](docs/guide/06-launch.md)

Библия персонажа: [character/bible.md](character/bible.md). Спецификация:
[docs/superpowers/specs/2026-10-14-ai-model-it-girl-design.md](docs/superpowers/specs/2026-10-14-ai-model-it-girl-design.md).

## Команды

| Команда | Что делает |
|---|---|
| `cm pod up` / `cm pod status` / `cm pod ssh` / `cm pod down` | поднять, проверить, зайти по SSH, выключить под |
| `cm batch face\|dataset\|photo\|video <сцены.yaml>` | пакетная генерация по файлу сцен |
| `cm lora prepare` / `cm lora train` / `cm lora status` | датасет и обучение LoRA |
| `cm export <файлы>` | подготовка к публикации: фото → JPEG с меткой ИИ в EXIF, без метаданных промпта; видео (.mp4) → ремукс через `ffmpeg` без метаданных и с тегом `comment=AI-generated` (без `ffmpeg` видео копируется как есть, с предупреждением) |

Результаты: `out/<дата>-<вид>/<сцена>_<NN>.png|mp4` + `manifest.jsonl`.

## Для разработчика

```bash
uv run pytest -q
uv run python scripts/validate_workflows.py   # необязательно: проверка графов на CPU, ~4 GB при первом запуске
```
