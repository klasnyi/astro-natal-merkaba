"""
Vimshottari Dasha — ведическая система предсказательной астрологии.

Каждый человек проживает 120-летний цикл из 9 планетных «владык»
(mahadasha), каждый — со своим фиксированным периодом. Внутри каждой
mahadasha идут 9 antardasha, длительности которых пропорциональны.

Старт = накшатра натальной Луны → её владыка → дробь, которая уже прошла.

Phase 7 of astro-natal-simond expansion (v1.9.0).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))
from astro_helpers import slugify  # type: ignore

warnings.filterwarnings("ignore")

# Vimshottari mahadasha periods (years), lord cycle starting from Ketu
DASHA_LORDS = ["ketu", "venus", "sun", "moon", "mars", "rahu", "jupiter", "saturn", "mercury"]
DASHA_YEARS = {
    "ketu": 7, "venus": 20, "sun": 6, "moon": 10, "mars": 7,
    "rahu": 18, "jupiter": 16, "saturn": 19, "mercury": 17,
}
TOTAL_CYCLE = sum(DASHA_YEARS.values())  # 120

LORD_RU = {
    "ketu": "Кету", "venus": "Венера", "sun": "Солнце", "moon": "Луна",
    "mars": "Марс", "rahu": "Раху", "jupiter": "Юпитер",
    "saturn": "Сатурн", "mercury": "Меркурий",
}
LORD_SYMBOL = {
    "ketu": "☋", "venus": "♀", "sun": "☉", "moon": "☽",
    "mars": "♂", "rahu": "☊", "jupiter": "♃", "saturn": "♄", "mercury": "☿",
}

# Архетипы владык — что они означают как период жизни
LORD_THEMES = {
    "ketu": "Кету — отделение от иллюзий, духовный поиск, отшельничество, отпускание прошлого. Часто кажется, что почва уходит из-под ног — на самом деле освобождается ниша для нового. Темы: интуиция, мистика, одиночество, переосмысление.",
    "venus": "Венера — комфорт, отношения, эстетика, материальный достаток. Период роскоши, искусства, любви и наслаждений. Темы: красота, партнёрство, удовольствие, чувственность, ценности.",
    "sun": "Солнце — лидерство, статус, признание. Период видимости и автономии. Темы: эго, карьера, отец, авторитет, самореализация.",
    "moon": "Луна — эмоциональная глубина, дом, семья, забота. Период внутренней работы, материнских тем, питания себя и других. Темы: чувства, дом, мать, женское, интуиция.",
    "mars": "Марс — действие, борьба, прорыв через сопротивление. Период активной воли, технических навыков, спорта, военной/инженерной/медицинской работы. Темы: энергия, конфликт, защита, страсть.",
    "rahu": "Раху — амбиции, экспансия, нестандартные пути, внезапные удачи и ловушки. Период «голода» — хочется больше, выше, быстрее. Темы: иностранное, технологии, нарушение норм, харизма, наваждение.",
    "jupiter": "Юпитер — мудрость, рост, учительство, духовность, благополучие. Самый «удачный» период — расширение возможностей. Темы: знания, философия, дети, наставники, путешествия, изобилие.",
    "saturn": "Сатурн — дисциплина, долг, медленный труд, мастерство через ограничение. Период серьёзной работы, ответственности, кармических уроков. Темы: время, структура, отказ, выдержка, авторитет.",
    "mercury": "Меркурий — интеллект, коммуникация, бизнес, обучение. Период активного ума, переговоров, торговли, текстов. Темы: речь, аналитика, нетворкинг, гибкость, торговля.",
}

# Накшатры (1-27) → имя + владыка
NAKSHATRAS = [
    ("Ashwini", "Ашвини", "ketu"),
    ("Bharani", "Бхарани", "venus"),
    ("Krittika", "Криттика", "sun"),
    ("Rohini", "Рохини", "moon"),
    ("Mrigashira", "Мригашира", "mars"),
    ("Ardra", "Ардра", "rahu"),
    ("Punarvasu", "Пунарвасу", "jupiter"),
    ("Pushya", "Пушья", "saturn"),
    ("Ashlesha", "Ашлеша", "mercury"),
    ("Magha", "Магха", "ketu"),
    ("Purva Phalguni", "Пурва Пхалгуни", "venus"),
    ("Uttara Phalguni", "Уттара Пхалгуни", "sun"),
    ("Hasta", "Хаста", "moon"),
    ("Chitra", "Читра", "mars"),
    ("Swati", "Свати", "rahu"),
    ("Vishakha", "Вишакха", "jupiter"),
    ("Anuradha", "Ануратха", "saturn"),
    ("Jyeshtha", "Джйештха", "mercury"),
    ("Mula", "Мула", "ketu"),
    ("Purva Ashadha", "Пурва Ашадха", "venus"),
    ("Uttara Ashadha", "Уттара Ашадха", "sun"),
    ("Shravana", "Шравана", "moon"),
    ("Dhanishta", "Дханишта", "mars"),
    ("Shatabhisha", "Шатабхиша", "rahu"),
    ("Purva Bhadrapada", "Пурва Бхадрапада", "jupiter"),
    ("Uttara Bhadrapada", "Уттара Бхадрапада", "saturn"),
    ("Revati", "Ревати", "mercury"),
]

NAKSHATRA_SIZE = 360.0 / 27  # 13.333...°


def parse_birth_to_jd(meta: dict) -> tuple[float, datetime]:
    """Натал meta → (Julian Day UT, datetime UT)."""
    import swisseph as swe

    yr, mo, day = map(int, meta["date"].split("-"))
    time_str = meta.get("time", "12:00")
    hh, mm = map(int, time_str.split(":"))
    local_dt = datetime(yr, mo, day, hh, mm, tzinfo=ZoneInfo(meta["tz"]))
    ut_dt = local_dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    jd = swe.julday(
        ut_dt.year, ut_dt.month, ut_dt.day,
        ut_dt.hour + ut_dt.minute / 60.0 + ut_dt.second / 3600.0,
    )
    return jd, ut_dt


def setup_swisseph_with_ayanamsha():
    import swisseph as swe
    import kerykeion

    swe.set_ephe_path(os.path.join(os.path.dirname(kerykeion.__file__), "sweph"))
    swe.set_sid_mode(swe.SIDM_LAHIRI)


def compute_sidereal_moon(jd: float) -> tuple[float, float]:
    """Возвращает (sidereal_lon_moon, ayanamsha)."""
    import swisseph as swe

    ayan = swe.get_ayanamsa_ut(jd)
    moon_trop, _ = swe.calc_ut(jd, swe.MOON, swe.FLG_SWIEPH)
    moon_sid = (moon_trop[0] - ayan) % 360
    return moon_sid, ayan


def find_nakshatra(moon_sidereal_lon: float) -> dict:
    nak_idx = int(moon_sidereal_lon // NAKSHATRA_SIZE)  # 0-based, 0..26
    nak_idx = min(nak_idx, 26)
    fraction_through = (moon_sidereal_lon % NAKSHATRA_SIZE) / NAKSHATRA_SIZE

    name_en, name_ru, lord = NAKSHATRAS[nak_idx]
    return {
        "index": nak_idx + 1,  # 1-based
        "name_en": name_en,
        "name_ru": name_ru,
        "lord": lord,
        "lord_ru": LORD_RU[lord],
        "fraction_through": round(fraction_through, 4),
        "moon_sidereal_lon": round(moon_sidereal_lon, 4),
    }


def add_years_to_date(start: datetime, years: float) -> datetime:
    """Прибавить дробное количество лет (1 год = 365.25 дней)."""
    days = years * 365.25
    return start + timedelta(days=days)


def build_mahadashas(birth_dt_ut: datetime, nakshatra: dict) -> list[dict]:
    """Постройка последовательности 9 mahadasha от рождения вперёд на 120 лет."""
    first_lord = nakshatra["lord"]
    fraction_used = nakshatra["fraction_through"]

    first_lord_idx = DASHA_LORDS.index(first_lord)
    first_lord_full_years = DASHA_YEARS[first_lord]
    first_lord_remaining_years = first_lord_full_years * (1 - fraction_used)
    first_lord_used_years = first_lord_full_years * fraction_used

    # Дата начала первого dasha (когда родился, эта махадаша уже шла)
    first_lord_start_dt = add_years_to_date(birth_dt_ut, -first_lord_used_years)

    sequence = []
    current_start = first_lord_start_dt
    for i in range(9):  # 9 mahadasha = 120 лет
        lord = DASHA_LORDS[(first_lord_idx + i) % 9]
        years = DASHA_YEARS[lord]
        end = add_years_to_date(current_start, years)
        sequence.append({
            "lord": lord,
            "lord_ru": LORD_RU[lord],
            "symbol": LORD_SYMBOL[lord],
            "years": years,
            "start": current_start.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
            "theme": LORD_THEMES[lord],
        })
        current_start = end

    return sequence


def build_antardashas(mahadasha: dict) -> list[dict]:
    """Внутри одной mahadasha — 9 antardasha. Длительность каждой = (M_lord_years × A_lord_years) / 120."""
    M_lord = mahadasha["lord"]
    M_lord_years = DASHA_YEARS[M_lord]
    M_start = datetime.strptime(mahadasha["start"], "%Y-%m-%d")

    M_lord_idx = DASHA_LORDS.index(M_lord)
    sub = []
    current = M_start
    for i in range(9):
        A_lord = DASHA_LORDS[(M_lord_idx + i) % 9]
        A_lord_years = DASHA_YEARS[A_lord]
        sub_years = (M_lord_years * A_lord_years) / TOTAL_CYCLE
        end = add_years_to_date(current, sub_years)
        sub.append({
            "lord": A_lord,
            "lord_ru": LORD_RU[A_lord],
            "symbol": LORD_SYMBOL[A_lord],
            "years": round(sub_years, 3),
            "months": round(sub_years * 12, 1),
            "start": current.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
        })
        current = end
    return sub


def find_current_period(mahadashas: list[dict], today: datetime) -> tuple[dict, dict]:
    """Найти текущую mahadasha и antardasha."""
    today_str = today.strftime("%Y-%m-%d")
    current_mahadasha = None
    for m in mahadashas:
        if m["start"] <= today_str <= m["end"]:
            current_mahadasha = m
            break

    if current_mahadasha is None:
        return None, None

    antardashas = build_antardashas(current_mahadasha)
    current_antardasha = None
    for a in antardashas:
        if a["start"] <= today_str <= a["end"]:
            current_antardasha = a
            break

    return current_mahadasha, current_antardasha


def main():
    parser = argparse.ArgumentParser(description="Vimshottari Dasha — ведический предсказательный цикл")
    parser.add_argument("--natal", required=True, help="Путь к натальному JSON")
    parser.add_argument("--outdir", default="/tmp/astro-dashas", help="Куда складывать результаты")
    parser.add_argument("--no-docx", action="store_true", help="Не генерировать DOCX")
    parser.add_argument("--with-pratyantar", action="store_true",
                        help="Также вычислить Pratyantardasha (3-й уровень) для текущей antardasha")
    args = parser.parse_args()

    natal_path = Path(args.natal).expanduser()
    if not natal_path.exists():
        print(f"❌ Натальный файл не найден: {natal_path}", file=sys.stderr)
        sys.exit(1)

    with open(natal_path, encoding="utf-8") as f:
        natal = json.load(f)

    print(f"📍 Натал: {natal['meta']['name']} ({natal['meta']['date']} {natal['meta']['time']} {natal['meta']['city']})")

    setup_swisseph_with_ayanamsha()
    jd, birth_ut = parse_birth_to_jd(natal["meta"])

    moon_sid, ayan = compute_sidereal_moon(jd)
    nakshatra = find_nakshatra(moon_sid)

    print(f"   Lahiri ayanamsha: {ayan:.4f}°")
    print(f"   Moon sidereal: {moon_sid:.4f}°")
    print(f"   Накшатра {nakshatra['index']}: {nakshatra['name_ru']} ({nakshatra['name_en']})")
    print(f"   Владыка: {nakshatra['lord_ru']}")
    print(f"   Доля пройдена: {nakshatra['fraction_through']*100:.2f}%")
    print()

    mahadashas = build_mahadashas(birth_ut, nakshatra)
    today = datetime.now()
    current_mahadasha, current_antardasha = find_current_period(mahadashas, today)

    print("📊 Mahadasha (главные периоды жизни):")
    for m in mahadashas:
        marker = " ◀ ТЕКУЩАЯ" if m is current_mahadasha else ""
        print(f"   {m['symbol']} {m['lord_ru']:8} {m['start']} → {m['end']} ({m['years']} лет){marker}")

    if current_mahadasha:
        print()
        print(f"🎯 Сейчас: Махадаша {current_mahadasha['lord_ru']} ({current_mahadasha['start']} → {current_mahadasha['end']})")
        if current_antardasha:
            print(f"   Антардаша {current_antardasha['lord_ru']} ({current_antardasha['start']} → {current_antardasha['end']}, {current_antardasha['months']} мес)")

    # Pratyantardasha — третий уровень — если запросили
    pratyantardashas = None
    if args.with_pratyantar and current_antardasha:
        # внутри antardasha — 9 pratyantardasha по той же формуле
        A_lord = current_antardasha["lord"]
        A_years_total = current_antardasha["years"]
        A_start = datetime.strptime(current_antardasha["start"], "%Y-%m-%d")
        A_lord_idx = DASHA_LORDS.index(A_lord)
        pratyantardashas = []
        current = A_start
        for i in range(9):
            P_lord = DASHA_LORDS[(A_lord_idx + i) % 9]
            P_years = (A_years_total * DASHA_YEARS[P_lord]) / TOTAL_CYCLE
            end = add_years_to_date(current, P_years)
            pratyantardashas.append({
                "lord": P_lord,
                "lord_ru": LORD_RU[P_lord],
                "symbol": LORD_SYMBOL[P_lord],
                "years": round(P_years, 4),
                "days": round(P_years * 365.25, 1),
                "start": current.strftime("%Y-%m-%d"),
                "end": end.strftime("%Y-%m-%d"),
            })
            current = end

    # Save
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    name_slug = slugify(natal["meta"]["name"])
    json_out = outdir / f"dashas_{name_slug}.json"

    result = {
        "meta": {
            "natal_meta": natal["meta"],
            "module": "dashas_vimshottari",
            "module_version": "1.0",
            "computed_at": datetime.now().isoformat(),
            "today": today.strftime("%Y-%m-%d"),
            "ayanamsha_lahiri": round(ayan, 4),
        },
        "moon_sidereal": {
            "abs_pos": round(moon_sid, 4),
        },
        "nakshatra": nakshatra,
        "mahadashas": mahadashas,
        "current_mahadasha": current_mahadasha,
        "current_antardasha": current_antardasha,
        "pratyantardashas": pratyantardashas,
    }
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n💾 JSON: {json_out}")

    # DOCX
    if not args.no_docx:
        try:
            from render_dashas_docx import render_dashas_docx
            docx_out = outdir / f"dashas_{name_slug}.docx"
            render_dashas_docx(result, str(docx_out))
            print(f"📄 DOCX: {docx_out}")
        except Exception as e:
            print(f"⚠️  DOCX рендер не удался: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
