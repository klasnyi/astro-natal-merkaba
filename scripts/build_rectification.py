"""
Ректификация времени рождения по жизненным событиям.

Идея: ASC и MC меняются на ~1° каждые 4 минуты. Транзитные аспекты к
ангулярным точкам в момент важных событий (свадьба, переезд, смерть близкого,
рождение ребёнка) — самые точные индикаторы. Перебираем кандидаты времени
в заданном окне, считаем суммарный «резонанс» транзитов с событиями,
выдаём топ-3.

Phase 11 of astro-natal-simond expansion (v1.10.0).
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
from build_transits import (  # type: ignore
    PLANET_RU,
    PLANET_SYMBOLS,
    SIGN_RU,
    ASPECTS,
    ASPECT_RU,
    ASPECT_NATURE,
    angular_distance,
    normalize_angle,
)

warnings.filterwarnings("ignore")


# Тематические планеты для каждого типа события + вес
EVENT_THEMES = {
    "marriage": {
        "name": "Свадьба / союз",
        "transit_planets": {"venus": 5, "mars": 4, "jupiter": 4, "sun": 3, "moon": 3},
        "natal_targets": ["sun", "moon", "venus", "mars", "ascendant", "descendant", "mc", "ic", "house_7_cusp"],
    },
    "divorce": {
        "name": "Развод / разрыв",
        "transit_planets": {"saturn": 5, "uranus": 5, "pluto": 4, "mars": 3},
        "natal_targets": ["venus", "mars", "moon", "ascendant", "descendant", "house_7_cusp"],
    },
    "child_birth": {
        "name": "Рождение ребёнка",
        "transit_planets": {"jupiter": 5, "moon": 5, "venus": 4, "sun": 3},
        "natal_targets": ["sun", "moon", "venus", "ascendant", "ic", "mc", "house_5_cusp"],
    },
    "relocation": {
        "name": "Переезд",
        "transit_planets": {"uranus": 5, "jupiter": 4, "mars": 3, "mercury": 3, "moon": 3},
        "natal_targets": ["moon", "mercury", "ic", "ascendant", "house_4_cusp"],
    },
    "career_change": {
        "name": "Смена карьеры / повышение",
        "transit_planets": {"sun": 4, "saturn": 5, "jupiter": 5, "uranus": 4},
        "natal_targets": ["sun", "saturn", "mc", "house_10_cusp"],
    },
    "loss_grief": {
        "name": "Тяжёлая потеря",
        "transit_planets": {"saturn": 5, "pluto": 5, "moon": 4, "uranus": 3},
        "natal_targets": ["sun", "moon", "saturn", "ascendant", "ic"],
    },
    "illness": {
        "name": "Серьёзная болезнь",
        "transit_planets": {"saturn": 4, "pluto": 4, "mars": 4, "neptune": 3, "chiron": 5},
        "natal_targets": ["sun", "moon", "ascendant", "house_6_cusp", "house_8_cusp"],
    },
    "awakening": {
        "name": "Духовное пробуждение / трансформация",
        "transit_planets": {"neptune": 5, "pluto": 5, "uranus": 4, "jupiter": 3},
        "natal_targets": ["sun", "moon", "neptune", "pluto", "mc"],
    },
    "death_of_close": {
        "name": "Смерть близкого человека",
        "transit_planets": {"pluto": 5, "saturn": 5, "mars": 3, "moon": 4, "neptune": 3},
        "natal_targets": ["moon", "ic", "saturn", "house_4_cusp", "house_8_cusp", "house_12_cusp"],
    },
    "legal_event": {
        "name": "Юридическое событие (суд / иск / контракт)",
        "transit_planets": {"saturn": 5, "pluto": 4, "mars": 4, "jupiter": 4, "mercury": 3},
        "natal_targets": ["mercury", "mc", "saturn", "house_9_cusp", "house_10_cusp", "house_7_cusp"],
    },
    "financial_windfall": {
        "name": "Крупный денежный приход / финансовый скачок",
        "transit_planets": {"jupiter": 5, "venus": 4, "uranus": 4, "sun": 3, "pluto": 3},
        "natal_targets": ["sun", "venus", "jupiter", "house_2_cusp", "house_8_cusp", "mc"],
    },
    "surgery_accident": {
        "name": "Операция / авария / физическая травма",
        "transit_planets": {"mars": 5, "pluto": 5, "saturn": 4, "uranus": 4, "chiron": 4},
        "natal_targets": ["ascendant", "mars", "house_6_cusp", "house_8_cusp", "house_1_cusp", "sun"],
    },
    "public_recognition": {
        "name": "Публичное признание / награда / медиа",
        "transit_planets": {"jupiter": 5, "sun": 4, "uranus": 4, "venus": 3},
        "natal_targets": ["sun", "mc", "jupiter", "house_10_cusp", "house_11_cusp"],
    },
    "education_milestone": {
        "name": "Завершение учёбы / диплом / экзамен",
        "transit_planets": {"mercury": 4, "jupiter": 5, "saturn": 4, "sun": 3},
        "natal_targets": ["mercury", "jupiter", "mc", "house_3_cusp", "house_9_cusp"],
    },
    "default": {
        "name": "Значимое событие (общее)",
        "transit_planets": {"sun": 3, "moon": 3, "saturn": 4, "jupiter": 4, "uranus": 4, "pluto": 4},
        "natal_targets": ["sun", "moon", "ascendant", "mc"],
    },
}

# Орбы для ректификации — узкие, только тесные аспекты считаем значимыми
RECT_ORB_TIGHT = 1.5  # для ангулярных точек
RECT_ORB_NORMAL = 2.5  # для планет


SIGN_KEYS = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]


def parse_meta_to_jd(yr, mo, day, hh, mm, tz_str: str) -> float:
    """Локальные дата/время в JD UT."""
    import swisseph as swe
    local_dt = datetime(yr, mo, day, hh, mm, tzinfo=ZoneInfo(tz_str))
    ut_dt = local_dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    return swe.julday(
        ut_dt.year, ut_dt.month, ut_dt.day,
        ut_dt.hour + ut_dt.minute / 60.0 + ut_dt.second / 3600.0,
    )


def setup_swisseph():
    import swisseph as swe
    import kerykeion
    swe.set_ephe_path(os.path.join(os.path.dirname(kerykeion.__file__), "sweph"))


def build_chart_for_candidate(natal_meta: dict, candidate_time_str: str):
    """Создаёт kerykeion subject для одного кандидата времени."""
    import kerykeion as kr

    yr, mo, day = map(int, natal_meta["date"].split("-"))
    hh, mm = map(int, candidate_time_str.split(":"))

    sub = kr.AstrologicalSubject(
        natal_meta["name"],
        yr, mo, day, hh, mm,
        lng=natal_meta["lon"],
        lat=natal_meta["lat"],
        tz_str=natal_meta["tz"],
        zodiac_type="Tropical" if natal_meta["system"] == "western" else "Sidereal",
    )
    return sub


def extract_natal_targets(sub) -> dict:
    """Натальные точки с долготой, индексированные по ключам."""
    targets = {}
    # Планеты
    for key in ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn",
                "uranus", "neptune", "pluto"):
        p = getattr(sub, key, None)
        if p is None:
            continue
        targets[key] = p.abs_pos

    # Углы и cusps
    targets["ascendant"] = sub.first_house.abs_pos
    targets["mc"] = sub.tenth_house.abs_pos
    targets["descendant"] = (sub.first_house.abs_pos + 180) % 360
    targets["ic"] = (sub.tenth_house.abs_pos + 180) % 360

    house_attr = ["first_house", "second_house", "third_house", "fourth_house",
                  "fifth_house", "sixth_house", "seventh_house", "eighth_house",
                  "ninth_house", "tenth_house", "eleventh_house", "twelfth_house"]
    for i, attr in enumerate(house_attr, start=1):
        h = getattr(sub, attr, None)
        if h is not None:
            targets[f"house_{i}_cusp"] = h.abs_pos

    return targets


def compute_transit_positions(event_date: datetime, transit_keys: list[str]) -> dict:
    """Транзитные позиции на дату события (для нужных планет)."""
    import swisseph as swe

    jd = swe.julday(
        event_date.year, event_date.month, event_date.day,
        event_date.hour + event_date.minute / 60.0,
    )

    SWE_BODY = {
        "sun": swe.SUN, "moon": swe.MOON, "mercury": swe.MERCURY,
        "venus": swe.VENUS, "mars": swe.MARS, "jupiter": swe.JUPITER,
        "saturn": swe.SATURN, "uranus": swe.URANUS, "neptune": swe.NEPTUNE,
        "pluto": swe.PLUTO, "chiron": swe.CHIRON,
    }
    out = {}
    for key in transit_keys:
        body = SWE_BODY.get(key)
        if body is None:
            continue
        res, _ = swe.calc_ut(jd, body, swe.FLG_SWIEPH)
        out[key] = res[0]
    return out


def find_aspect_orb(pos1: float, pos2: float, orb_max: float):
    arc = angular_distance(pos1, pos2)
    best = None
    for name, exact, symbol in ASPECTS:
        diff = abs(arc - exact)
        if diff <= orb_max:
            if best is None or diff < best:
                best = diff
    return best  # tightest orb if any, else None


def score_candidate(natal_targets: dict, events: list[dict]) -> tuple[float, list]:
    """Скоринг кандидата времени = сумма по событиям резонанса транзитов с натальными точками."""
    total_score = 0.0
    breakdowns = []

    for event in events:
        theme = EVENT_THEMES.get(event["type"], EVENT_THEMES["default"])
        transit_keys = list(theme["transit_planets"].keys())
        natal_target_keys = theme["natal_targets"]

        # Транзитные позиции на дату события
        ev_dt = datetime.fromisoformat(event["date"])
        transit_pos = compute_transit_positions(ev_dt, transit_keys)

        event_score = 0.0
        event_aspects = []

        for tkey, tpos in transit_pos.items():
            t_weight = theme["transit_planets"][tkey]
            for n_key in natal_target_keys:
                n_pos = natal_targets.get(n_key)
                if n_pos is None:
                    continue
                # Узкие орбы для ангулярных + cusps, шире для планет
                is_angular = n_key in ("ascendant", "mc", "descendant", "ic") or n_key.startswith("house_")
                orb_max = RECT_ORB_TIGHT if is_angular else RECT_ORB_NORMAL
                orb = find_aspect_orb(tpos, n_pos, orb_max)
                if orb is None:
                    continue
                # Чем точнее орб, тем выше score (от 0 до 1)
                tightness = (orb_max - orb) / orb_max
                # Ангулярные точки получают bonus (×2) — они time-sensitive
                multiplier = 2.0 if is_angular else 1.0
                aspect_score = t_weight * tightness * multiplier
                event_score += aspect_score
                event_aspects.append({
                    "transit_planet": tkey,
                    "natal_target": n_key,
                    "orb": round(orb, 3),
                    "score": round(aspect_score, 2),
                })

        breakdowns.append({
            "event": event,
            "score": round(event_score, 2),
            "top_aspects": sorted(event_aspects, key=lambda a: -a["score"])[:3],
        })
        total_score += event_score

    return round(total_score, 2), breakdowns


def main():
    parser = argparse.ArgumentParser(description="Ректификация времени рождения по жизненным событиям")
    parser.add_argument("--natal", required=True, help="Путь к натальному JSON (должен содержать lat/lon/tz/date в meta)")
    parser.add_argument("--events", required=True,
                        help="Путь к JSON со списком событий: [{\"date\":\"YYYY-MM-DD HH:MM\",\"type\":\"marriage\"}, ...]")
    parser.add_argument("--start-time", default="00:00", help="Начало окна (HH:MM)")
    parser.add_argument("--end-time", default="23:59", help="Конец окна (HH:MM)")
    parser.add_argument("--step-minutes", type=int, default=8, help="Шаг перебора в минутах (мин 4)")
    parser.add_argument("--top", type=int, default=5, help="Сколько лучших кандидатов показать")
    parser.add_argument("--outdir", default="/tmp/astro-rectification")
    parser.add_argument("--no-docx", action="store_true")
    args = parser.parse_args()

    natal_path = Path(args.natal).expanduser()
    events_path = Path(args.events).expanduser()
    if not natal_path.exists():
        print(f"❌ Натал не найден: {natal_path}", file=sys.stderr)
        sys.exit(1)
    if not events_path.exists():
        print(f"❌ Файл событий не найден: {events_path}", file=sys.stderr)
        sys.exit(1)

    with open(natal_path, encoding="utf-8") as f:
        natal = json.load(f)
    with open(events_path, encoding="utf-8") as f:
        events = json.load(f)

    if not isinstance(events, list) or not events:
        print("❌ Список событий пуст или некорректен", file=sys.stderr)
        sys.exit(2)

    setup_swisseph()

    print(f"📍 Натал: {natal['meta']['name']} ({natal['meta']['date']} {natal['meta']['city']})")
    print(f"   Окно: {args.start_time} → {args.end_time}, шаг {args.step_minutes} мин")
    print(f"   События: {len(events)}")
    for e in events:
        theme = EVENT_THEMES.get(e["type"], EVENT_THEMES["default"])
        print(f"     · {e['date']} — {theme['name']} ({e['type']})")

    # Генерация кандидатов времени
    s_h, s_m = map(int, args.start_time.split(":"))
    e_h, e_m = map(int, args.end_time.split(":"))
    start_total_min = s_h * 60 + s_m
    end_total_min = e_h * 60 + e_m
    step = max(args.step_minutes, 4)

    candidates = []
    cur = start_total_min
    while cur <= end_total_min:
        h = cur // 60
        m = cur % 60
        if h < 24:
            candidates.append(f"{h:02d}:{m:02d}")
        cur += step

    print(f"\n🔍 Кандидатов: {len(candidates)}")
    print(f"   Total chart-builds: {len(candidates) * (1 + len(events))}")
    print()

    results = []
    for i, ctime in enumerate(candidates):
        if i % 10 == 0:
            print(f"   [{i}/{len(candidates)}] {ctime}...", flush=True)
        try:
            sub = build_chart_for_candidate({**natal["meta"], "candidate_time": ctime}, ctime)
            natal_targets = extract_natal_targets(sub)
            score, breakdowns = score_candidate(natal_targets, events)
            asc_data = {
                "sign_ru": SIGN_RU[SIGN_KEYS.index(sub.first_house.sign)],
                "degrees": round(sub.first_house.position, 2),
            }
            mc_data = {
                "sign_ru": SIGN_RU[SIGN_KEYS.index(sub.tenth_house.sign)],
                "degrees": round(sub.tenth_house.position, 2),
            }
            results.append({
                "time": ctime,
                "score": score,
                "asc": asc_data,
                "mc": mc_data,
                "breakdowns": breakdowns,
            })
        except Exception as e:
            print(f"   ⚠️  Ошибка для {ctime}: {e}", file=sys.stderr)

    results.sort(key=lambda r: -r["score"])
    top = results[: args.top]

    print("\n🏆 Топ кандидатов времени:")
    for rank, r in enumerate(top, start=1):
        print(f"  {rank}. {r['time']}  score={r['score']}  ASC {r['asc']['sign_ru']} {r['asc']['degrees']}° / MC {r['mc']['sign_ru']} {r['mc']['degrees']}°")

    # Save
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    name_slug = slugify(natal["meta"]["name"])
    json_out = outdir / f"rectification_{name_slug}.json"
    out = {
        "meta": {
            "natal_meta": natal["meta"],
            "module": "rectification",
            "module_version": "1.0",
            "computed_at": datetime.now().isoformat(),
            "window": {"start": args.start_time, "end": args.end_time, "step_minutes": step},
            "candidates_total": len(candidates),
        },
        "events": events,
        "top_candidates": top,
        "all_results": results,  # полный список для анализа
    }
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n💾 JSON: {json_out}")

    if not args.no_docx:
        try:
            from render_rectification_docx import render_rectification_docx
            docx_out = outdir / f"rectification_{name_slug}.docx"
            render_rectification_docx(out, str(docx_out))
            print(f"📄 DOCX: {docx_out}")
        except Exception as e:
            print(f"⚠️  DOCX рендер не удался: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
