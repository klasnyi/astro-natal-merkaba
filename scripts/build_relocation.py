"""
Релокация (relocation chart): пересчёт углов и домов для другого города
при сохранении даты, времени и UT-момента рождения.

Натальные планеты по эклиптике не меняются — меняются ASC/MC/cusps,
потому что они зависят от LST (local sidereal time), а LST — от долготы.

Phase 9 of astro-natal-merkaba expansion (v1.8.0).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from datetime import datetime
from pathlib import Path

# Импорты helpers (DRY)
sys.path.insert(0, os.path.dirname(__file__))
from astro_helpers import slugify  # type: ignore
from build_transits import (  # type: ignore
    PLANET_RU,
    PLANET_SYMBOLS,
    SIGN_RU,
)

warnings.filterwarnings("ignore", category=DeprecationWarning)


SIGN_KEYS = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]

# kerykeion имена для планет (kebab/snake разные API версии)
PLANET_KEY_MAP = {
    "sun": "sun",
    "moon": "moon",
    "mercury": "mercury",
    "venus": "venus",
    "mars": "mars",
    "jupiter": "jupiter",
    "saturn": "saturn",
    "uranus": "uranus",
    "neptune": "neptune",
    "pluto": "pluto",
}

HOUSE_NAME_TO_NUM = {
    "First_House": 1, "Second_House": 2, "Third_House": 3, "Fourth_House": 4,
    "Fifth_House": 5, "Sixth_House": 6, "Seventh_House": 7, "Eighth_House": 8,
    "Ninth_House": 9, "Tenth_House": 10, "Eleventh_House": 11, "Twelfth_House": 12,
}


def geocode_city(city: str) -> tuple[float, float, str]:
    """Город → (lat, lon, tz_str). Через geopy + timezonefinder."""
    from geopy.geocoders import Nominatim
    from timezonefinder import TimezoneFinder

    geolocator = Nominatim(user_agent="astro-natal-merkaba-relocation/1.0")
    location = geolocator.geocode(city, timeout=10)
    if location is None:
        raise RuntimeError(f"Город не найден: {city}")

    tf = TimezoneFinder()
    tz_str = tf.timezone_at(lng=location.longitude, lat=location.latitude)
    if tz_str is None:
        raise RuntimeError(f"Не удалось определить таймзону для {city}")

    return location.latitude, location.longitude, tz_str


def build_relocation_subject(natal_meta: dict, target_lat: float, target_lon: float, target_tz: str):
    """Создать kerykeion subject с оригинальной датой/временем (тем же UT-моментом)
    но координатами целевого города.

    ВАЖНО: чтобы UT-момент совпадал с натальным, передаём оригинальный tz_str и время.
    Тогда kerykeion вычислит тот же UT, и для новых координат рассчитает новые дома.
    """
    import kerykeion as kr

    yr, mo, day = map(int, natal_meta["date"].split("-"))
    time_str = natal_meta.get("time", "12:00")
    hh, mm = map(int, time_str.split(":"))

    # Используем оригинальный tz_str натала, чтобы UT-момент остался прежним.
    # target_tz нужен только для отображения "в каком местном времени родился бы человек,
    # если бы был в этом городе" — в текущей логике мы его не используем для расчёта,
    # потому что важен UT-момент.
    sub = kr.AstrologicalSubject(
        natal_meta["name"],
        yr, mo, day, hh, mm,
        lng=target_lon,
        lat=target_lat,
        tz_str=natal_meta["tz"],  # важно — оригинальная таймзона рождения
        zodiac_type="Tropical" if natal_meta["system"] == "western" else "Sidereal",
    )
    return sub


def extract_planet(planet_obj, key: str) -> dict:
    sign_en = planet_obj.sign  # 'Leo', 'Vir', etc
    sign_idx = SIGN_KEYS.index(sign_en) if sign_en in SIGN_KEYS else 0
    house_name = getattr(planet_obj, "house", None)
    house_num = HOUSE_NAME_TO_NUM.get(house_name, None)

    return {
        "key": key,
        "name_ru": PLANET_RU.get(key, key.title()),
        "symbol": PLANET_SYMBOLS.get(key, ""),
        "abs_pos": round(planet_obj.abs_pos, 4),
        "degrees": round(planet_obj.position, 2),
        "sign_en": sign_en,
        "sign_ru": SIGN_RU[sign_idx],
        "house": house_num,
        "retrograde": getattr(planet_obj, "retrograde", False),
    }


def extract_relocation_data(sub) -> dict:
    """Извлечь планеты, ASC/MC/cusps из релоцированного subject."""
    planets = {}
    for natal_key, kerykeion_key in PLANET_KEY_MAP.items():
        p_obj = getattr(sub, kerykeion_key, None)
        if p_obj is None:
            continue
        planets[natal_key] = extract_planet(p_obj, natal_key)

    # ASC и MC
    asc = sub.first_house
    mc = sub.tenth_house
    asc_data = {
        "abs_pos": round(asc.abs_pos, 4),
        "degrees": round(asc.position, 2),
        "sign_en": asc.sign,
        "sign_ru": SIGN_RU[SIGN_KEYS.index(asc.sign)],
    }
    mc_data = {
        "abs_pos": round(mc.abs_pos, 4),
        "degrees": round(mc.position, 2),
        "sign_en": mc.sign,
        "sign_ru": SIGN_RU[SIGN_KEYS.index(mc.sign)],
    }

    # Все 12 cusps
    houses = {}
    for i, attr in enumerate([
        "first_house", "second_house", "third_house", "fourth_house",
        "fifth_house", "sixth_house", "seventh_house", "eighth_house",
        "ninth_house", "tenth_house", "eleventh_house", "twelfth_house",
    ], start=1):
        h = getattr(sub, attr, None)
        if h is None:
            continue
        houses[str(i)] = {
            "sign_en": h.sign,
            "sign_ru": SIGN_RU[SIGN_KEYS.index(h.sign)],
            "degrees": round(h.position, 2),
            "abs_pos": round(h.abs_pos, 4),
        }

    return {
        "planets": planets,
        "ascendant": asc_data,
        "mc": mc_data,
        "houses": houses,
    }


def compare_house_changes(natal_planets: dict, reloc_planets: dict) -> list:
    """Найти планеты, сменившие дом при релокации."""
    changes = []
    for key, n_planet in natal_planets.items():
        r_planet = reloc_planets.get(key)
        if r_planet is None or r_planet.get("house") is None:
            continue
        if n_planet.get("house") != r_planet["house"]:
            changes.append({
                "key": key,
                "name_ru": n_planet["name_ru"],
                "symbol": n_planet["symbol"],
                "natal_house": n_planet.get("house"),
                "reloc_house": r_planet["house"],
                "sign_ru": n_planet["sign_ru"],
                "degrees": n_planet["degrees"],
            })
    return changes


def find_angular_planets(reloc_planets: dict) -> list:
    """Угловые планеты (в 1/4/7/10) — самые активные в релокации."""
    angular = []
    for key, p in reloc_planets.items():
        if p.get("house") in (1, 4, 7, 10):
            angular.append(p)
    return angular


def main():
    parser = argparse.ArgumentParser(description="Релокация: пересчёт углов и домов для другого города")
    parser.add_argument("--natal", required=True, help="Путь к натальному JSON-кэшу")
    parser.add_argument("--city", required=True, help="Целевой город релокации (например, 'Берлин' или 'New York')")
    parser.add_argument("--outdir", default="/tmp/astro-relocation", help="Куда складывать результаты")
    parser.add_argument("--no-docx", action="store_true", help="Не генерировать DOCX")
    args = parser.parse_args()

    natal_path = Path(args.natal).expanduser()
    if not natal_path.exists():
        print(f"❌ Натальный файл не найден: {natal_path}", file=sys.stderr)
        sys.exit(1)

    with open(natal_path, encoding="utf-8") as f:
        natal = json.load(f)

    print(f"📍 Натал: {natal['meta']['name']} ({natal['meta']['date']} {natal['meta']['time']} {natal['meta']['city']})")
    print(f"🌍 Релокация → {args.city}")

    # Геокодинг
    try:
        target_lat, target_lon, target_tz = geocode_city(args.city)
    except Exception as e:
        print(f"❌ Геокодинг не удался: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"   Координаты: lat={target_lat:.4f}, lon={target_lon:.4f}, tz={target_tz}")

    # Сборка релоцированного subject
    sub = build_relocation_subject(natal["meta"], target_lat, target_lon, target_tz)
    reloc = extract_relocation_data(sub)

    # Сравнение
    changes = compare_house_changes(natal["planets"], reloc["planets"])
    angular = find_angular_planets(reloc["planets"])

    print()
    print("📊 Сравнение углов:")
    print(f"   ASC: натал {natal['ascendant']['sign_ru']} {natal['ascendant']['degrees']}° "
          f"→ релок {reloc['ascendant']['sign_ru']} {reloc['ascendant']['degrees']}°")
    print(f"   MC:  натал {natal['mc']['sign_ru']} {natal['mc']['degrees']}° "
          f"→ релок {reloc['mc']['sign_ru']} {reloc['mc']['degrees']}°")
    print()
    print(f"🔄 Планеты сменили дом: {len(changes)}")
    for c in changes:
        print(f"   {c['symbol']} {c['name_ru']:8} дом {c['natal_house']} → {c['reloc_house']}")
    print()
    print(f"⭐ Угловые планеты в релокации: {len(angular)}")
    for a in angular:
        print(f"   {a['symbol']} {a['name_ru']:8} дом {a['house']} ({a['sign_ru']} {a['degrees']}°)")

    # Сохранение
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    name_slug = slugify(natal["meta"]["name"])
    city_slug = slugify(args.city)
    json_out = outdir / f"relocation_{name_slug}_to_{city_slug}.json"

    result = {
        "meta": {
            "natal_meta": natal["meta"],
            "target_city": args.city,
            "target_lat": target_lat,
            "target_lon": target_lon,
            "target_tz": target_tz,
            "module": "relocation",
            "module_version": "1.0",
            "computed_at": datetime.now().isoformat(),
        },
        "natal": {
            "ascendant": natal["ascendant"],
            "mc": natal["mc"],
            "planets": natal["planets"],
            "houses": natal["houses"],
        },
        "relocation": reloc,
        "house_changes": changes,
        "angular_planets": angular,
    }
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n💾 JSON: {json_out}")

    # DOCX
    if not args.no_docx:
        try:
            from render_relocation_docx import render_relocation_docx
            docx_out = outdir / f"relocation_{name_slug}_to_{city_slug}.docx"
            render_relocation_docx(result, str(docx_out))
            print(f"📄 DOCX: {docx_out}")
        except Exception as e:
            print(f"⚠️  DOCX рендер не удался: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
