# 00. Установка на Mac (MacBook Pro M5, 32 ГБ)

Mac — пульт управления. Генерация пачек, видео и обучение LoRA идут на арендованной
RTX 4090 (RunPod), а Mac запускает `cm`, хранит результаты, ретушь и монтаж.

## 1. Инструменты командной строки

```bash
# Homebrew (если ещё нет): https://brew.sh
brew install git rsync ffmpeg
curl -LsSf https://astral.sh/uv/install.sh | sh     # uv: Python и зависимости проекта
ssh-keygen -t ed25519 -C "cm"                       # SSH-ключ для пода (Enter на всё)
```

`ffmpeg` нужен `cm export` для видео (убирает метаданные промпта), `rsync` — для
загрузки файлов на под.

## 2. Проект

```bash
git clone <адрес вашего репозитория> Comfy_Model
cd Comfy_Model
uv sync
cp .env.example .env      # впишите ключи, см. 01-setup.md
uv run cm --help
```

Дальше — [01. Установка и первый запуск пода](01-setup.md).

## 3. Приложения

| Задача | Приложение | Цена |
|---|---|---|
| Быстрые тесты промптов и сцен прямо на Mac | Draw Things (App Store) | бесплатно |
| Ретушь (пальцы рук и ног, мелкие артефакты) | Pixelmator Pro или Photoshop | разово ~$50 / подписка |
| Монтаж Reels | CapCut или DaVinci Resolve | бесплатно |

После обучения LoRA (`ohwxroxana_v1.safetensors`, см. [03](03-train-lora.md)) её можно
скачать с пода (`uv run cm pod ssh`, затем `scp`) и подключить в Draw Things для
тестов на Mac.

## 4. Что не делать на Mac

- Пачки по 20+ фото, видео (Wan) и обучение LoRA — только на поде: на Mac это часы,
  на 4090 — минуты.
- Не закрывайте ноутбук посреди `cm pod up`: если связь оборвётся, `cm` попробует
  сам выключить под, но проверьте `uv run cm pod status`.
