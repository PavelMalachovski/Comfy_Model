# 09. Датасет и LoRA на Qwen-Image 2512

Цель: из выбранного лица `out/qwen-faces-2/phone-2.png` получить LoRA с триггером
`ohwxroxana`. Перед началом сделайте обратный поиск по этому лицу: на нём не должен находиться
реальный человек. Лицензия Qwen-Image и Qwen-Image-Edit: Apache 2.0. Кадры FLUX и Kontext сюда
не добавляйте.

Ожидаемая цена, это оценка: **$5–7** (RTX 5090, $1.19/ч) плюс том. Держите на RunPod запас
около $10.

## 1. Увеличить том

Для обучения нужна полная версия Qwen, ещё примерно 58 ГБ. RunPod → Storage → `bakeoff-no` →
**200 GB**. Это около $14 в месяц, пока том существует.

## 2. Датасет

```bash
.venv/bin/cm pod up --models pod/qwen_models.yaml
.venv/bin/cm batch dataset scenes/dataset_qwen.yaml --ref out/qwen-faces-2/phone-2.png --workflows workflows/qwen --out out/qwen-dataset
.venv/bin/cm pod down
```

## 3. Отбор

В `out/qwen-dataset/` оставьте 15–30 кадров, где лицо совпадает с `phone-2`. Удалите кадры, где
лицо уплыло или поза копирует референс. Затем:

На следующем поде верните текстуру кожи отобранным кадрам (сила 0.25, примерно по минуте на кадр):

```bash
.venv/bin/cm pod up --models pod/qwen_models.yaml
.venv/bin/cm lora refine out/qwen-dataset --out out/qwen-dataset-refined
.venv/bin/cm lora prepare out/qwen-dataset-refined
```

## 4. Обучение

`cm lora train` не запускается на поде старше 1 часа. Если проход занял больше, поднимите новый под:

```bash
.venv/bin/cm lora train --base qwen
.venv/bin/cm lora status
```

`HF_TOKEN` для Qwen не нужен. Первый запуск дополнительно скачивает полную модель.

Если датасет меняли и надо обучить заново, укажите новую версию: `.venv/bin/cm lora train --base qwen --version 2`.
Без этого ai-toolkit увидит готовую первую версию и ничего не обучит.

## 5. Проверка

```bash
.venv/bin/cm batch photo scenes/lora_check.yaml --lora ohwxroxana_v1.safetensors --workflows workflows/qwen --out out/qwen-lora-check
.venv/bin/cm pod down
.venv/bin/cm pod status
```

Хорошо, если на шести кадрах одно и то же лицо в разных ракурсах, кожа живая и кадры не копируют
датасет. Кадры предназначены для проверки: публикуйте их только после перевода пайплайна.
