# Changelog

История релизов astro-natal-simond. Семантическое версионирование.

## v2.4.2 — Универсальный --interp во всех 11 рендерах (2026-04-25 day, Lite закрыт)

**Lite версия скила полностью закрыта** — все рендеры единообразно принимают LLM-интерпретации.

- **`render_docx.py`** — добавлена универсальная функция `add_extended_interp_section(doc, interp)` (~73 строки, +6 секций):
  - intro_how_to_read / summary / items / key_aspects / deep_themes / practical_advice
  - Используется как общий хелпер всеми рендерами, у которых не было нативного --interp
- **`render_asteroids_docx.py`** — добавлен опциональный флаг `--interp INTERP`, параметр `interp` в функцию `render_asteroids_docx()`
- **`render_dashas_docx.py`** — аналогично + импорт add_extended_interp_section
- **`render_relocation_docx.py`** — аналогично

**До v2.4.2:** только 7 из 11 рендеров принимали `--interp` (натал, транзиты, прогрессии, соляр, синастрия, композит, ректификация). Астероиды/даши/релокация работали только без LLM-интерпретаций.

**После v2.4.2:** **все 11 рендеров** единообразно поддерживают LLM-фазу. В Cowork-флоу пользователь получает полный отчёт со всеми углублёнными интерпретациями для любого модуля.

Smoke test (Краснодар 13.08.1993 5:30) на 7 модулей прошёл — все DOCX генерируются корректно.

## v2.4.1 — Расширенное меню после натала (2026-04-25 day)

UX-улучшение по фидбэку Димы из живого использования в Cowork.

- **`SKILL.md` секция «Шаг 6 — Презентация результата»** теперь содержит явный блок «📋 Что ещё можно построить по этому наталу» с **11 пунктами**: транзиты+bi-wheel, прогрессии, соляр, синастрия, композит, астероиды, релокация, даши, ректификация, Лилит, расширенные интерпретации
- Каждый пункт — с **эмодзи** и **триггерами активации**, чтобы пользователь понимал что и как запросить
- В конце Claude обязан спросить: **«Какую технику запустить следующей?»** — НЕ предлагать только 2-3 пункта
- Раньше после натала Claude писал лишь «можно запросить транзиты или другие техники» — слишком вяло, пользователь не видел всего функционала

Никаких изменений в Python-коде. Только SKILL.md +39/-2 строки.

## v2.4.0 — Расширенные интерпретации (2026-04-25)

Каркас расширенной архетипической библиотеки + автоматический fallback в DOCX-рендере, когда interp.json от LLM не задан.

- **`references/planets_in_signs.json`** (новый, 24 комбинации заполнены): Солнце × 12 знаков и Луна × 12 знаков с keyword/archetype/gift/shadow по 50–80 слов на каждую. Бэклог: остальные 8 планет (Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto) × 12 знаков = 96 комбинаций — заполняются по запросу
- **`references/planets_in_houses.json`** (новый, 24 комбинации заполнены): Солнце и Луна × 12 домов с keyword/archetype/focus/shadow. Бэклог: 96 комбинаций для остальных планет
- **`references/elements_modalities_hemispheres.json`** (новый, заполнен полностью): 4 стихии (огонь/земля/воздух/вода) × 4 режима (archetype/dominant/lacking/balanced) + 3 креста (cardinal/fixed/mutable) × 4 режима + 4 полусферы (north/south/east/west)
- **`render_docx.py`** — добавлена секция «Расширенные интерпретации»:
  * `_load_extended_refs()` lazy-load трёх JSON через модульный кэш
  * `get_planet_in_sign_text(planet_key, sign_ru)` / `get_planet_in_house_text(...)` / `get_element_text(...)` / `get_modality_text(...)` — helpers для извлечения текстов
  * `_format_ext_entry()` — формирует параграф из {keyword, archetype, gift/focus, shadow}
  * `add_planets_section()` теперь использует расширенный текст как fallback если в interp.json нет описания планеты
  * `add_distributions_section()` подгружает расширенный текст для доминирующей стихии и креста как fallback
- Smoke на Диме (без interp.json): Sun Лев → подтягивается «Творец-сияющий» (~300 слов), Луна Близнецы → «Чувство через слово», доминанта Воздух → расширенный текст про воздушный архетип. DOCX 297 КБ, 59 параграфов
- Backward-compat: при наличии interp.json от LLM ext-refs игнорируются (приоритет user-defined)

---

## v2.3.0 — Лилит (натал + транзиты + синастрия) (2026-04-25)

Чёрная Луна (Black Moon Lilith, Mean Apogee) — теневая женственность, подавленное, инстинкты, темы изгнания/отвержения. Mean Lilith через swisseph (`swe.MEAN_APOG`) — стабильнее чем True/Osculating вариант.

- **Натал** — уже работала: `mean_lilith` в `PLANET_KEYS` (`build_chart.py`), отображается в секции «Кармические точки» DOCX-отчёта
- **Транзиты** (`build_transits.py`) — добавлено:
  * `mean_lilith` в `TRANSIT_PLANETS` list
  * `obj_map` в `extract_transit_planets()` через `getattr(subject, 'mean_lilith', None)` с fallback на None
  * Орб 1.5° в `TRANSIT_ORBS` (узкий, лилитные транзиты значимы только когда тесные)
  * Скорость 0.111°/день в `PLANET_DAILY_MOTION` (~40°/год, цикл ≈ 8.85 года)
  * Вес 5 в `PLANET_WEIGHT` — наравне с Юпитером и Хироном
- **Синастрия** (`build_synastry.py`) — автоматом через `for k, d in natal['planets']`, никаких изменений не нужно
- Smoke на Диме (натал + транзиты на 25.04.2026): транзитная Лилит Стрелец 14.07°, **топ-1 транзит — Лилит △ ASC орб 0.61°** (мощный индикатор активации тени через идентичность). Найдено 3 Лилит-аспекта (Нептун ☌ Лилит 0.52°, Плутон ⚹ Лилит 1.88°, Лилит △ ASC 0.61°)
- Smoke на синастрии Дима × Анна: **4 Лилит-аспекта** (Узел Димы ☍ Лилит Анны 1.58°, Меркурий Димы ⚹ Лилит Анны 3.46°, Лилит Димы △ Плутон Анны 3.03°)

---

## v2.2.0 — Расширенная ректификация (+6 типов событий) (2026-04-25)

EVENT_THEMES расширен с 9 до 15 типов жизненных событий для Phase-11 ректификации.

- 6 новых event types в `build_rectification.py`:
  * `death_of_close` — смерть близкого человека (Pluto/Saturn/Mars/Moon → Moon/IC/4-8-12 cusps)
  * `legal_event` — суд/иск/контракт (Saturn/Pluto/Mars/Jupiter → MC/Mercury/9-10-7 cusps)
  * `financial_windfall` — крупный денежный приход (Jupiter/Venus/Uranus → Sun/Venus/2-8 cusps)
  * `surgery_accident` — операция/авария (Mars/Pluto/Saturn/Uranus/Chiron → ASC/Mars/6-8-1 cusps)
  * `public_recognition` — публичное признание/медиа (Jupiter/Sun/Uranus → MC/Sun/10-11 cusps)
  * `education_milestone` — диплом/экзамен (Mercury/Jupiter/Saturn → Mercury/MC/3-9 cusps)
- Все типы используют ту же scoring-логику: `t_weight × tightness × multiplier(×2 for angular)`
- Smoke на Диме (4 события: surgery_accident + financial_windfall + public_recognition + relocation, окно 04:00–07:00 шаг 12 мин): топ-3 кандидат **05:36 рядом с реальным 5:30** ✅ алгоритм по-прежнему валиден после расширения
- SKILL.md обновлён с полным списком 15 типов и тематическими планетами

---

## v2.1.0 — Bi-wheel PNG (2026-04-25)

Двойной круг: натал внутри + транзиты снаружи + цветные линии активных аспектов между ними. Палитра МерКаБа на тёмном фоне.

- `render_biwheel.py` (новый, ~370 строк): зодиакальное кольцо со стихиями, ASC/DSC/MC/IC лейблы, натальные дома (угловые золотым), натальные планеты во внутреннем кольце с авто-разнесением близких символов по радиусу, транзитные планеты во внешнем кольце, линии аспектов натал↔натал внутри + транзит↔натал между кольцами с прозрачностью по орбу
- Опциональный флаг `--biwheel` в `build_transits.py` — после расчёта транзитов автоматически рисует bi-wheel PNG, путь записывается в transits.json как `biwheel_png`
- `--biwheel-orb FLOAT` (default 3.0°) — настраиваемый максимальный орб для отображаемых аспектов
- `render_transits_docx.py` — новая функция `add_biwheel_image()` встраивает bi-wheel PNG в DOCX-отчёт после блока «Текущий период» (если поле `biwheel_png` есть в JSON)
- Импорт констант (PLANET_SYMBOLS/COLORS, SIGN_SYMBOLS, ELEMENT_COLORS, ASPECT_COLORS, MAJOR_ASPECTS) из `build_chart.py` — DRY сохранён
- Smoke на Диме: bi-wheel PNG 476 КБ, DOCX 509 КБ (с встроенной картинкой), 19 аспектов отображены, цвета по типу (красный квадрат / оранжевый оппозиция / зелёный трин / синий секстиль / белый соединение)

---

## v2.0.0 — Финальный релиз (2026-04-25)

**Полная астрологическая платформа: 10 модулей, единая палитра МерКаБа.**

Все запланированные техники теперь работают. Это итоговый milestone-релиз серии v1.0–v1.10. Дальнейшие изменения пойдут как minor/patch внутри v2.x.

### Что в v2.0
- 10 рабочих модулей: натал, транзиты, прогрессии, соляр, синастрия, композит, астероиды, релокация, ведические даши, ректификация
- Единая DRY-архитектура: константы и helpers — из `build_transits.py`, палитра и стили DOCX — из `render_docx.py`
- Кэш натальных карт в `~/.astro-natal-simond/cache/`
- Полностью обновлённый README с таблицей всех модулей
- SKILL.md ~65 KB, охватывает все 10 техник + бэклог
- Около 15 000+ строк Python-кода

### Не в v2.0 (бэклог для v2.x)
- Bi-wheel PNG (натал внутри + транзиты снаружи)
- Лилит в транзитах (kerykeion API менее стабилен для этого)
- PDF-экспорт через soffice (сейчас только DOCX)

---

## v1.10.0 — Phase 11: Ректификация (2026-04-25)

Восстановление неизвестного времени рождения через transit-резонанс к натальным точкам в дни значимых событий жизни.

- `build_rectification.py`: перебор кандидатов времени с настраиваемым шагом (4–60 мин), для каждого — построение натала, скоринг по 9 типам событий с тематическими планетами и весами, ангулярные точки получают bonus ×2
- `render_rectification_docx.py`: топ-5 кандидатов, breakdown по событиям с топ-3 резонирующих аспектов
- 9 event types: marriage, divorce, child_birth, relocation, career_change, loss_grief, illness, awakening, default
- Smoke: Дима 13.08.1993 + 4 события → 04:00 (top-1) и 05:36 (top-2 рядом с реальным 05:30)

---

## v1.9.0 — Phase 7: Ведические даши (2026-04-25)

Vimshottari Dasha — главная предсказательная система ведической астрологии. 120-летний цикл от натальной Луны.

- `build_dashas.py`: Lahiri ayanamsha через swisseph, sidereal Moon → 27 накшатр → lord → mahadasha sequence с уже-прошедшей долей. Antardashas пропорционально. Опционально pratyantardasha (3-й уровень).
- `render_dashas_docx.py`: блок накшатры, таблица 120-летнего цикла с подсветкой текущей mahadasha, фокус на текущий период с антардашей, полный breakdown antardasha
- 9 архетипов планетных владык + 27 накшатр с русскими транскрипциями
- Smoke: Дима — Sidereal Moon 54.57° → Mrigashira (Mars), 9.3% elapsed at birth, текущая Юпитер mahadasha 2017–2033 / Венера antardasha 2025-10-30 → 2028-06-30

---

## v1.8.0 — Phase 9: Релокация (2026-04-25)

Пересчёт ASC/MC/домов для другого города при сохранении натального UT-момента.

- `build_relocation.py`: геокодинг через Nominatim + timezonefinder, kerykeion subject с оригинальной tz_str + целевыми lat/lon, helpers для сравнения домов и поиска угловых планет
- `render_relocation_docx.py`: сравнение углов натал vs релокация, таблица планет, сменивших дом, угловые планеты, распределение по домам, advice
- Smoke: Дима → Берлин: ASC Лев 14.68° → Рак 25.53°, MC Овен 23.35° → Рыбы 27.17°, 7 планет сменили дом, 3 угловые (Меркурий 1, Марс+Юпитер стеллиум 4)

---

## v1.7.0 — Phase 8: Астероиды (2026-04-25)

Церера, Паллада, Юнона, Веста + Хирон через swisseph (kerykeion sweph data, файл `seas_18.se1`).

- `build_asteroids.py`: положения 5 астероид (знак, дом, ретроградность), архетип по элементу + квадранту дома, узкие аспекты к натальным планетам/углам (1–2°)
- `render_asteroids_docx.py`: МерКаБа палитра, summary table + per-asteroid blocks + aspects table + practical advice
- Tautology filter (Хирон swisseph vs натальный Хирон не показываем)
- Smoke: Дима — Ceres Tau 5.39° dom 10, Pallas Pis 4.94° R, Juno Vir 5.77°, Vesta Pis 8.52° R, Chiron Leo 27.10°. 2 тесных аспекта.

---

## v1.6.0 — Phase 6: Композит (2026-04-25)

Карта отношений как «третьей сущности» (midpoint method).

- `build_composite.py`: midpoint каждой пары планет через короткую сторону круга, composite ASC/MC = midpoint двух углов, дома Whole Sign от composite ASC, аспекты внутри композита
- `render_composite_docx.py`: ядро (Sun/Moon/ASC/MC), планеты по домам, аспекты, advice
- Smoke: Дима × Анна — composite Sun Близнецы 7.37° dom 11, Moon Рак 26.3° dom 12, ASC Лев 14.31°, 28 аспектов

---

## v1.5.0 — Phase 5: Синастрия (2026-04-25)

Совместимость двух натальных карт: cross-аспекты + house overlays.

- `build_synastry.py`: cross-аспекты person1 × person2 (орбы 4–6° по типу планеты), house overlay в обе стороны, романтические комбинации (Sun-Moon, Venus-Mars, Sun-Venus, Moon-Venus, Moon-Mars) с bonus +5
- `render_synastry_docx.py`: сводная таблица, топ-12 cross-аспектов с цветом по природе, два раздела house overlays
- Smoke: Дима × Анна — 46 cross-аспектов (27 гарм / 16 напр / 3 соединения / 3 романтических). Топ: ASC ☌ ASC орб 0.75°

---

## v1.4.0 — Phase 4: Соляр (2026-04-25)

Solar Return — карта на год от ДР до ДР.

- `build_solar.py`: бинарный поиск точки возврата Солнца (0.0001° точность, окно ±3 дня от ДР, ~40 итераций), геокодинг для города пребывания, угловые планеты, аспекты соляра
- `render_solar_docx.py`: сводка года (ASC + Sun house + угловые), темы домов, распределение планет
- Smoke: Дима соляр 2025 — 12.08.2025 22:02:34 в Москве, ASC Телец 9.42°, Sun дом 5

---

## v1.3.0 — Phase 3: Прогрессии (2026-04-25)

Secondary progressions: 1 день после рождения = 1 год жизни.

- `build_progressions.py`: прогрессированные позиции, 8-фазный лунный цикл, ingresses (смены знаков), узкие орбы (≤1° для inner, ≤0.5° для outer)
- `render_progressions_docx.py`: главные секции прогр. Sun + прогр. Moon + лунная фаза + ingresses + аспекты к наталу
- DRY: импорт констант из `build_transits`
- Smoke: Дима возраст 32.7 — Прогр. Sun Дева 21.94°, Moon Дева 2.45°, фаза Balsamic→New Moon, 3 ingresses

---

## v1.2.0 — Phase 2: Транзиты (2026-04-25)

Transit-to-natal аспекты с движением (applying/separating) и оценкой даты точности.

- `build_transits.py`: транзитные позиции, аспекты с орбами 1.5–3° по типу планеты, оценка даты точности линейной экстраполяцией, скоринг intensity. **Источник DRY-констант для всех модулей.**
- `render_transits_docx.py`: цветовое кодирование (red/orange/grey по интенсивности), таблицы, palette helpers
- Bug fix: `abs_pos` (не `absolute`) — поле в kerykeion натальном JSON
- Smoke: Дима + 25.04.2026 — 19 аспектов, top: Нептун △ Меркурий 1.42° applying

---

## v1.1.1 — Authorship cleanup (2026-04-25)

По запросу: «Дмитрий Симоненко» → **«Дмитрий <dimkaklasnyi@gmail.com>»** во всех публичных файлах. Применено к astro repo (LICENSE, README, SKILL.md frontmatter, render_docx colophon) и к karmic-numerology-simond v1.3.1 (LICENSE).

---

## v1.1.0 — Phase 1: Foundation (2026-04-25)

- `astro_helpers.py`: кэш наталов в `~/.astro-natal-simond/cache/`, slug-генерация (с транслитом кириллицы), парсеры даты/времени/системы
- `build_chart.py` — auto-save в кэш после расчёта
- SKILL.md +135 строк: «Кэш натальных карт», «Расчёт для другого человека (client-mode)», «Расширенные техники (бэклог)»

---

## v1.0.0 — GitHub baseline (2026-04-25)

Натальная карта без расширений. Готов к Cowork.

- Base scripts: `build_chart.py`, `render_docx.py`
- 5 reference JSON архетипов (planets, signs, houses, aspects, nakshatras)
- README, LICENSE (MIT + Swiss Ephemeris notice + дисклеймер), .gitignore
- Topics: claude-skill, anthropic, cowork, astrology, natal-chart, swiss-ephemeris, kerykeion, merkaba, python, docx, russian, vedic, western-astrology
