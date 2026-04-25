# Changelog

История релизов astro-natal-merkaba. Семантическое версионирование.

## v2.0.0 — Финальный релиз (2026-04-25)

**Полная астрологическая платформа: 10 модулей, единая палитра МерКаБа.**

Все запланированные техники теперь работают. Это итоговый milestone-релиз серии v1.0–v1.10. Дальнейшие изменения пойдут как minor/patch внутри v2.x.

### Что в v2.0
- 10 рабочих модулей: натал, транзиты, прогрессии, соляр, синастрия, композит, астероиды, релокация, ведические даши, ректификация
- Единая DRY-архитектура: константы и helpers — из `build_transits.py`, палитра и стили DOCX — из `render_docx.py`
- Кэш натальных карт в `~/.astro-natal-merkaba/cache/`
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

По запросу: «Дмитрий Симоненко» → **«Дмитрий <dimkaklasnyi@gmail.com>»** во всех публичных файлах. Применено к astro repo (LICENSE, README, SKILL.md frontmatter, render_docx colophon) и к karmic-numerology-merkaba v1.3.1 (LICENSE).

---

## v1.1.0 — Phase 1: Foundation (2026-04-25)

- `astro_helpers.py`: кэш наталов в `~/.astro-natal-merkaba/cache/`, slug-генерация (с транслитом кириллицы), парсеры даты/времени/системы
- `build_chart.py` — auto-save в кэш после расчёта
- SKILL.md +135 строк: «Кэш натальных карт», «Расчёт для другого человека (client-mode)», «Расширенные техники (бэклог)»

---

## v1.0.0 — GitHub baseline (2026-04-25)

Натальная карта без расширений. Готов к Cowork.

- Base scripts: `build_chart.py`, `render_docx.py`
- 5 reference JSON архетипов (planets, signs, houses, aspects, nakshatras)
- README, LICENSE (MIT + Swiss Ephemeris notice + дисклеймер), .gitignore
- Topics: claude-skill, anthropic, cowork, astrology, natal-chart, swiss-ephemeris, kerykeion, merkaba, python, docx, russian, vedic, western-astrology
