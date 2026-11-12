# 10. Контент-план: первые 50 постов

Решения от 14 ноября 2026, обновлены 16 ноября под новый образ (йога и пилатес,
[bible](../../character/bible.md), стратегия — [13](13-promo-strategy.md)):

| Что | Решение |
|---|---|
| Площадки | Instagram (лента + сторис) — 40 постов, бесплатный Telegram — 10; Threads — те же фото с короткой подписью |
| Темп | 1 пост в день, 50 дней (около 7 недель) |
| Старт | сначала 1–2 недели прогрева аккаунта ([07](07-warmup.md)), потом план |
| Темы ленты | Дом и утро (14), Йога и пилатес (13), Жизнь в Дубае (13) |
| Формат | 24 одиночных фото и 16 каруселей по 3–5 кадров |
| Ниша в Instagram | чистая йога и жизнь, без наготы, блюра, «прикрыто руками» и ссылки на Fanvue |
| Голос | тёплый, спокойный, с иронией; «40 is not the end. It's the good part.» |
| Язык | английский, лёгкий русский акцент (иногда без артикля), без «!», максимум одно 🤍, 🌅 или 🧘‍♀️ |
| Образ | «phone»: бальзам вместо помады, живая кожа (`character/profile_phone.yaml`), LoRA v4 |
| Её квартира | спальня 1, ванная 2, гостиная 9 (`rooms/`) |

Платные наборы для Fanvue в этот план не входят — они в [13](13-promo-strategy.md).

**Параллельный запуск на 30 дней** (Instagram + Telegram + X) — в [15](15-parallel-plan.md).
Он заменяет колонку Telegram этого календаря; для Instagram берёт отсюда первые 30 постов
(сцены и подписи), без дней-пропусков.

## Фото

| Файл сцен | Сцен | Кадров | Для чего |
|---|---|---|---|
| `scenes/plan50_instagram.yaml` | 40 | 144 | одиночный пост: 2 варианта на выбор; карусель: 6, из них берём 3–5 |
| `scenes/plan50_telegram.yaml` | 8 | 16 | фото-посты Telegram (уровень `social`: халат, полотенце, бельё, стопы) |

Рендер на Маке в быстром режиме, около 11 минут на кадр: 160 кадров — примерно 29 часов,
3–4 ночи. Команды — в шапке каждого файла. Потом `scripts/phone_finish.py --hdr 0.5`.
Лишние кадры из каруселей и одиночных постов идут в сторис и Threads.

Если домашние кадры «уплывают» от её комнат, их фон фиксируется заменой на плашку из
`rooms/` (это облако, RunPod; около $1 за 30–40 кадров).

## Перед каждым постом

- Подпись «AI-generated» в bio и метка ИИ в Instagram при публикации.
- В Instagram никаких слов: nude, naked, feet, barefoot, lingerie, «link for more»,
  «exclusive», «spicy». Ссылка в bio ведёт в бесплатный Telegram, не на Fanvue.
- Проверить кадр на 100%: руки, пальцы, телефон в обычном селфи, лицо совпадает,
  oxblood-ногти на месте.
- Публикует только оператор, вручную или через планировщик с его подтверждением.

## Сторис (каждый день, 2–3 штуки)

Из запасных кадров дня + текст на фоне: «утро» («6 am. Mat. Coffee. In that order.»),
опрос («Beach or studio tomorrow?»), вопрос-стикер («Ask me anything about 40.»).
По пятницам — репост поста Telegram с «link in bio».

## Серии

- **Sunrise Monday** — пляж или студия на рассвете.
- **40 and…** — мысль о возрасте и теле.
- **Siberia vs Dubai** — шутки про контраст.
- **Little Dubai** — места и мелочи города (абра, рынок, пустыня).
- В Telegram: **Poll Sunday** — подписчики выбирают тему следующего сета.

## Календарь

Д — день от начала плана (после прогрева). И — Instagram, Т — Telegram.
Тема: Д — дом, Й — йога и пилатес, Г — город (Дубай). Формат: О — одиночное, К — карусель.

| Д | Где | Тема | Формат | Сцена | Подпись |
|---|---|---|---|---|---|
| 1 | И | Д | О | p01-h-morning-coffee-window | Morning. Coffee first, then everything else. |
| 2 | И | Й | К | p02-f-beach-class-sunrise | 6 am, mats are out, beach is still mine. Ten minutes before everyone comes. |
| 3 | И | Й | О | p03-f-studio-mirror | Monday. Studio smells like coffee and good intentions. |
| 4 | И | Д | К | p04-h-bedroom-mirror-outfit | Forty, and I finally dress for myself. |
| 5 | Т | — | фото | p05-tg-welcome-bed | Hi, I'm Roxy. Pilates teacher, Dubai, 40. Here I show the mornings Instagram doesn't see. 🤍 |
| 6 | И | Г | О | p06-d-matcha-cafe | Iced matcha, 9 am, already 30 degrees. In Siberia we would call it a miracle. |
| 7 | И | Й | К | p07-f-pilates-reformer | Plank on the reformer. Shaking is just the body learning. |
| 8 | И | Д | О | p08-h-bathroom-robe | Not every morning is a good morning. This one needed two coffees. |
| 9 | И | Г | К | p09-d-beach-club-friends | Girls' day. Nobody talked about work. Almost. |
| 10 | Т | — | текст | — | Little story: at 32 my back said stop. Pilates was supposed to be rehab. Eight years later I teach it in Dubai. Funny how life works. |
| 11 | И | Й | О | p11-f-running-promenade | Six kilometres before the sun gets serious. |
| 12 | И | Д | К | p12-h-living-room-evening | Evenings are slow now. I like slow. |
| 13 | И | Г | О | p13-d-old-dubai-abra | One dirham across the creek. Best view in the city. |
| 14 | И | Й | О | p14-f-side-plank-studio | Side plank, 45 seconds. Breathe. Don't look at the clock. |
| 15 | Т | — | фото | p15-tg-towel-mirror | After class, before coffee. You're the only ones who see me like this. |
| 16 | И | Д | О | p16-h-kitchen-breakfast | Breakfast for someone who teaches at 7 am. |
| 17 | И | Г | К | p17-d-desert-picnic | Tea, dates, and nobody for 20 kilometres. |
| 18 | И | Й | О | p18-f-tree-pose-palms | Tree pose. Balance is mostly about where you look. |
| 19 | И | Д | К | p19-h-bed-reading | Sunday. Book, silence, no messages before noon. |
| 20 | Т | — | фото | p20-tg-feet-mat | You asked what my mat sees every morning. Here. |
| 21 | И | Г | О | p21-d-souk-spices | Old Dubai smells like rose and saffron. New Dubai smells like iced coffee. |
| 22 | И | Й | К | p22-f-beach-yoga | Stretch. Breathe. Stop apologizing. |
| 23 | И | Д | О | p23-h-bathroom-skincare | Skincare at 40: water, sleep, sunscreen. And not caring so much. |
| 24 | И | Г | К | p24-d-marina-walk-sunset | Three years here and sunsets still stop me. |
| 25 | Т | — | фото | p25-tg-lingerie-teaser | Something more private is coming. Only for those who are here early. 🤍 |
| 26 | И | Й | О | p26-f-after-class-selfie | Taught three classes. Took one. Earned this water. |
| 27 | И | Д | К | p27-h-balcony-morning | My view. My coffee. My quiet hour. |
| 28 | И | Г | О | p28-d-farmers-market | Figs, mint, and too much bread. Weekend rules. |
| 29 | И | Й | О | p29-f-pool-laps | Forty laps. Then lunch. In that order. |
| 30 | Т | — | текст | — | People ask if I miss Moscow. I miss snow sometimes. I don't miss who I was there. |
| 31 | И | Д | О | p31-h-hallway-ready | Mat bag on, phone on silent. Class in 20. |
| 32 | И | Г | К | p32-d-dinner-friends | Divorce taught me one thing: choose your Friday table carefully. |
| 33 | И | Й | О | p33-f-wall-pilates | Legs up the wall. The laziest exercise I teach. Also the best. |
| 34 | И | Д | К | p34-h-bedroom-evening | Lights low. Phone down soon. |
| 35 | Т | — | фото | p35-tg-swimsuit-rear | Sunrise swim. I didn't look back long. Long enough for you. |
| 36 | И | Г | О | p36-d-sea-swim | Water is 27 degrees. I'm not complaining. Siberian girl, remember. |
| 37 | И | Й | К | p37-f-desert-yoga | Warrior two on a dune at sunrise. Sand everywhere. Worth it. |
| 38 | И | Д | О | p38-h-car-coffee-selfie | Five minutes in the car before the day starts. Nobody gets those five minutes. |
| 39 | И | Г | О | p39-d-airport-travel | Yoga retreat this weekend. Mat comes with me everywhere. |
| 40 | Т | — | фото | p40-tg-robe-stretch | Closed channel opens soon. I will remember who was here first. |
| 41 | И | Й | О | p41-f-living-room-stretch | Forward fold. Some days the floor is closer than others. |
| 42 | И | Д | К | p42-h-weekend-brunch | Weekend. Phone face down. You should try it, after you like this. |
| 43 | И | Г | О | p43-d-sunset-dhow | Sunset on the water. No wine, just juice and good company. |
| 44 | И | Й | К | p44-f-pilates-ring | Pilates ring. Small thing, big burn. |
| 45 | Т | — | фото | p45-tg-bed-legs | A month together. Lazy evening, just for you. |
| 46 | И | Д | О | p46-h-bathroom-ready | Ready in ten. Dinner with friends, not with a date. Yet. |
| 47 | И | Г | О | p47-d-yacht-day | A friend's yacht, a whole day of nothing. I'm learning to do nothing. |
| 48 | И | Й | О | p48-f-beach-walk | Sea, wind, salt. And my mat, just in case. |
| 49 | И | Д | К | p49-h-living-room-sunset | Fifty days. Thank you for being here. 40 really is the good part. |
| 50 | Т | — | фото | p50-tg-closing-balcony | You stayed. The private channel is open now. Details only here. 🤍 |

## Метрики

Раз в неделю — таблица из [07](07-warmup.md): подписчики, охват, сохранения, переходы
в Telegram. Через 3 недели: темы с худшим охватом заменить, лучшую серию удвоить.
