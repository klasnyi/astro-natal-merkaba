"""
Расчёт астероидов: Ceres, Pallas, Juno, Vesta, Chiron.

Использует swisseph + ephemeris-данные kerykeion.
На вход — путь к натальному JSON-кэшу. На выход — JSON с положениями
астероидов в знаках, домах и аспектах к натальным планетам.

Phase 8 of astro-natal-merkaba expansion (v1.7.0).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Импорты helpers/констант (DRY с другими модулями)
sys.path.insert(0, os.path.dirname(__file__))
from build_transits import (  # type: ignore
    PLANET_RU,
    PLANET_SYMBOLS,
    SIGN_RU,
    SIGN_EN_TO_IDX,
    ASPECTS,
    ASPECT_RU,
    ASPECT_NATURE,
    angular_distance,
    normalize_angle,
    find_aspect,
)

# Asteroid metadata
ASTEROIDS = {
    "ceres": {
        "swe_id": 1,  # AST_OFFSET + 1
        "name_ru": "Церера",
        "symbol": "⚳",
        "archetype": "материнство, забота, питание, циклы потерь и возвращений",
    },
    "pallas": {
        "swe_id": 2,
        "name_ru": "Паллада",
        "symbol": "⚴",
        "archetype": "мудрость, стратегия, паттерны и интуитивный интеллект",
    },
    "juno": {
        "swe_id": 3,
        "name_ru": "Юнона",
        "symbol": "⚵",
        "archetype": "партнёрство, брак, верность, союзы и их теневые стороны",
    },
    "vesta": {
        "swe_id": 4,
        "name_ru": "Веста",
        "symbol": "⚶",
        "archetype": "преданность, призвание, сакральный фокус, очаг внутреннего огня",
    },
    "chiron": {
        "swe_id": "CHIRON",
        "name_ru": "Хирон",
        "symbol": "⚷",
        "archetype": "раненый целитель, дар через боль, мост между мирами",
    },
}

# Архетипы по элементам (4 элемента × 5 астероид)
ARCHETYPE_BY_ELEMENT = {
    "ceres": {
        "fire": "Любовь и забота через действие, азарт, инициативу. Учится не сжигать тех, о ком заботится.",
        "earth": "Питание через материю — еду, тело, дом. Проявляется как чуткое присутствие и сервис.",
        "air": "Забота через слова, идеи, общение. Исцеляет разговором и обменом смыслами.",
        "water": "Эмоциональное материнство, эмпатия, утроба. Чувствует чужие потребности до их озвучивания.",
    },
    "pallas": {
        "fire": "Творческая стратегия, прорывное видение, лидерство в идеях. Воин-интеллектуал.",
        "earth": "Прикладная мудрость, ремесло, мастерство в деталях, практичные паттерны.",
        "air": "Чистый стратегический ум, политика, дипломатия, паттерны связей.",
        "water": "Интуитивная мудрость, психологическая прозорливость, видение скрытых течений.",
    },
    "juno": {
        "fire": "Партнёрство как страстный союз равных, требует огня и автономии у обоих.",
        "earth": "Долговечный союз через быт, верность, надёжность, общее имущество.",
        "air": "Союз умов, интеллектуальная пара, потребность в общении и общих идеях.",
        "water": "Эмоциональное слияние, глубокая привязанность, ревность и преданность.",
    },
    "vesta": {
        "fire": "Преданность делу, страсть к призванию, священное горение.",
        "earth": "Сосредоточенный труд, методичная преданность ремеслу или земле.",
        "air": "Интеллектуальная преданность идее, философия, учительство.",
        "water": "Священное служение, целительство, эмоциональное хранение очага.",
    },
    "chiron": {
        "fire": "Рана идентичности и воли. Дар — лидерство для тех, кто проходит через огонь.",
        "earth": "Рана тела, материи, выживания. Дар — практическое целительство и воплощение.",
        "air": "Рана коммуникации, смысла, восприятия. Дар — учительство и переосмысление.",
        "water": "Рана чувств, корней, безопасности. Дар — глубокая эмпатия и психологическая работа.",
    },
}

# Архетипы по квадрантам домов (1-3 я-сфера, 4-6 близкое, 7-9 другие, 10-12 коллектив)
ARCHETYPE_BY_QUADRANT = {
    "ceres": {
        1: "Забота как способ предъявлять себя миру.",
        2: "Питание через семью, дом, корни, тело, ресурсы.",
        3: "Материнство в отношениях с другими — партнёром, клиентом, коллегой.",
        4: "Забота о коллективе, наследии, миссии в социуме.",
    },
    "pallas": {
        1: "Стратегический ум встроен в личность, видна острая интуиция.",
        2: "Мудрость прикладная — в семье, ресурсах, творчестве.",
        3: "Стратегия в партнёрстве, переговорах, юриспруденции.",
        4: "Интеллектуальное лидерство в коллективе и социальных миссиях.",
    },
    "juno": {
        1: "Идентичность сильно завязана на роль партнёра.",
        2: "Партнёрство через дом, семью, общие ресурсы и быт.",
        3: "Брак и контракты — центральная сфера через 7 дом.",
        4: "Союзы профессиональные, коллективные, идеологические.",
    },
    "vesta": {
        1: "Преданность себе, своему пути, самопостижение как алтарь.",
        2: "Священное служение через семью, дом, ремесло, тело.",
        3: "Преданность партнёрству, общему делу, психологии, целительству.",
        4: "Призвание коллективное — миссия, учительство, духовное лидерство.",
    },
    "chiron": {
        1: "Рана идентичности, чувство «я не такой, как все». Путь — принять уникальность.",
        2: "Рана близости, корней, ресурсов. Путь — научиться принимать и давать опору.",
        3: "Рана партнёрства или коммуникации. Путь — целительство через диалог.",
        4: "Рана коллективной принадлежности. Путь — стать целителем для других.",
    },
}


def parse_natal_to_jd(natal: dict) -> float:
    """Из натальных meta вычисляем Julian Day UT."""
    import swisseph as swe

    meta = natal["meta"]
    date_str = meta["date"]  # YYYY-MM-DD
    time_str = meta.get("time", "12:00")  # HH:MM
    tz_str = meta["tz"]

    yr, mo, day = map(int, date_str.split("-"))
    hh, mm = map(int, time_str.split(":"))

    # Локальное время → UT через ZoneInfo
    local_dt = datetime(yr, mo, day, hh, mm, tzinfo=ZoneInfo(tz_str))
    ut_dt = local_dt.astimezone(ZoneInfo("UTC"))

    jd = swe.julday(
        ut_dt.year,
        ut_dt.month,
        ut_dt.day,
        ut_dt.hour + ut_dt.minute / 60.0 + ut_dt.second / 3600.0,
    )
    return jd


def setup_swisseph():
    """Указываем kerykeion ephemeris path для swisseph."""
    import swisseph as swe
    import kerykeion

    sweph_dir = os.path.join(os.path.dirname(kerykeion.__file__), "sweph")
    swe.set_ephe_path(sweph_dir)


def compute_asteroid_positions(jd: float) -> dict:
    """Вычислить положения 5 астероидов на Julian Day UT."""
    import swisseph as swe

    flag = swe.FLG_SWIEPH | swe.FLG_SPEED
    result = {}

    for key, info in ASTEROIDS.items():
        if info["swe_id"] == "CHIRON":
            body = swe.CHIRON
        else:
            body = swe.AST_OFFSET + info["swe_id"]

        try:
            res, _ = swe.calc_ut(jd, body, flag)
            lon, lat, dist, lon_speed = res[0], res[1], res[2], res[3]
        except Exception as e:
            print(f"⚠️  Ошибка расчёта {info['name_ru']}: {e}", file=sys.stderr)
            continue

        sign_idx = int(lon // 30) % 12
        sign_keys = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]
        sign_en = sign_keys[sign_idx]

        result[key] = {
            "key": key,
            "name_ru": info["name_ru"],
            "symbol": info["symbol"],
            "abs_pos": round(lon, 4),
            "degrees": round(lon % 30, 2),
            "sign_en": sign_en,
            "sign_ru": SIGN_RU[sign_idx],
            "speed": round(lon_speed, 4),
            "retrograde": lon_speed < 0,
            "archetype": ASTEROIDS[key]["archetype"],
        }

    return result


def find_house_for_position(abs_pos: float, houses: dict) -> int:
    """Найти дом для абсолютной долготы по cusps Placidus."""
    cusps = []
    for i in range(1, 13):
        cusps.append(houses[str(i)]["abs_pos"])

    for i in range(12):
        start = cusps[i]
        end = cusps[(i + 1) % 12]

        if start <= end:
            if start <= abs_pos < end:
                return i + 1
        else:  # wrap через 0°
            if abs_pos >= start or abs_pos < end:
                return i + 1
    return 1  # fallback


def get_quadrant(house: int) -> int:
    """Квадрант дома: 1 (1-3), 2 (4-6), 3 (7-9), 4 (10-12)."""
    return ((house - 1) // 3) + 1


def determine_element(sign_en: str) -> str:
    fire = {"Ari", "Leo", "Sag"}
    earth = {"Tau", "Vir", "Cap"}
    air = {"Gem", "Lib", "Aqu"}
    water = {"Can", "Sco", "Pis"}
    if sign_en in fire:
        return "fire"
    if sign_en in earth:
        return "earth"
    if sign_en in air:
        return "air"
    return "water"


def attach_houses_and_archetypes(asteroids: dict, natal: dict) -> dict:
    """Добавить дом, архетип по элементу и квадранту."""
    houses = natal["houses"]
    for key, ast in asteroids.items():
        house = find_house_for_position(ast["abs_pos"], houses)
        quadrant = get_quadrant(house)
        element = determine_element(ast["sign_en"])

        ast["house"] = house
        ast["quadrant"] = quadrant
        ast["element"] = element
        ast["archetype_in_element"] = ARCHETYPE_BY_ELEMENT.get(key, {}).get(element, "")
        ast["archetype_in_quadrant"] = ARCHETYPE_BY_QUADRANT.get(key, {}).get(quadrant, "")

    return asteroids


# Орбы для астероид-аспектов: тесные (астероиды слабее планет)
ASTEROID_ORBS = {
    "luminary": 2.0,  # Sun, Moon
    "personal": 1.5,  # Mercury, Venus, Mars
    "social": 1.5,   # Jupiter, Saturn
    "outer": 1.0,    # Uranus, Neptune, Pluto
    "angle": 2.0,    # ASC, MC
    "node": 1.0,
}


def get_orb_for_natal(natal_key: str) -> float:
    if natal_key in ("sun", "moon"):
        return ASTEROID_ORBS["luminary"]
    if natal_key in ("mercury", "venus", "mars"):
        return ASTEROID_ORBS["personal"]
    if natal_key in ("jupiter", "saturn"):
        return ASTEROID_ORBS["social"]
    if natal_key in ("uranus", "neptune", "pluto"):
        return ASTEROID_ORBS["outer"]
    if natal_key in ("ascendant", "mc"):
        return ASTEROID_ORBS["angle"]
    return ASTEROID_ORBS["node"]


def find_asteroid_aspect(pos1: float, pos2: float, orb_max: float):
    """Найти аспект между двумя долготами с заданным макс. орбом.
    Возвращает dict с key/name_ru/symbol/nature/orb/exact_angle или None.
    """
    arc = angular_distance(pos1, pos2)
    for name, exact, symbol in ASPECTS:
        diff = abs(arc - exact)
        if diff <= orb_max:
            return {
                "key": name,
                "name_ru": ASPECT_RU[name],
                "symbol": symbol,
                "nature": ASPECT_NATURE[name],
                "orb": round(diff, 2),
                "exact_angle": exact,
            }
    return None


def compute_asteroid_aspects(asteroids: dict, natal: dict) -> list:
    """Аспекты астероид → натальные планеты/углы."""
    natal_points = {}

    # Планеты
    for key, p in natal["planets"].items():
        natal_points[key] = {
            "key": key,
            "name_ru": p["name_ru"],
            "abs_pos": p["abs_pos"],
            "type": "planet",
        }
    # ASC, MC
    asc = natal.get("ascendant", {})
    mc = natal.get("mc", {})
    if asc:
        natal_points["ascendant"] = {"key": "ascendant", "name_ru": "Асцендент", "abs_pos": asc["abs_pos"], "type": "angle"}
    if mc:
        natal_points["mc"] = {"key": "mc", "name_ru": "MC", "abs_pos": mc["abs_pos"], "type": "angle"}

    aspects = []
    for ast_key, ast in asteroids.items():
        for n_key, n in natal_points.items():
            # Пропускаем тавтологию — астероид с самим собой
            # (например, Chiron у нас и в натале как kerykeion-объект, и через swisseph)
            if ast_key == n_key:
                continue
            orb_max = get_orb_for_natal(n_key)
            asp = find_asteroid_aspect(ast["abs_pos"], n["abs_pos"], orb_max)
            if asp is None:
                continue
            aspects.append({
                "asteroid_key": ast_key,
                "asteroid_name": ast["name_ru"],
                "natal_key": n_key,
                "natal_name": n["name_ru"],
                "natal_type": n["type"],
                "aspect_key": asp["key"],
                "aspect_name": asp["name_ru"],
                "aspect_symbol": asp["symbol"],
                "nature": asp["nature"],
                "orb": asp["orb"],
                "exact_angle": asp["exact_angle"],
            })

    aspects.sort(key=lambda a: a["orb"])
    return aspects


def main():
    parser = argparse.ArgumentParser(description="Расчёт астероидов (Ceres, Pallas, Juno, Vesta, Chiron) для натальной карты")
    parser.add_argument("--natal", required=True, help="Путь к натальному JSON (из кэша или из build_chart.py)")
    parser.add_argument("--outdir", default="/tmp/astro-asteroids", help="Куда складывать результаты")
    parser.add_argument("--no-docx", action="store_true", help="Не генерировать DOCX (только JSON)")
    args = parser.parse_args()

    natal_path = Path(args.natal).expanduser()
    if not natal_path.exists():
        print(f"❌ Натальный файл не найден: {natal_path}", file=sys.stderr)
        sys.exit(1)

    with open(natal_path, encoding="utf-8") as f:
        natal = json.load(f)

    setup_swisseph()
    jd = parse_natal_to_jd(natal)

    print(f"📍 Натал: {natal['meta']['name']} ({natal['meta']['date']} {natal['meta']['time']} {natal['meta']['city']})")
    print(f"   JD UT = {jd:.4f}")
    print()

    asteroids = compute_asteroid_positions(jd)
    asteroids = attach_houses_and_archetypes(asteroids, natal)
    aspects = compute_asteroid_aspects(asteroids, natal)

    # Печать сводки
    print("✨ Астероиды:")
    for key, a in asteroids.items():
        retro = " R" if a["retrograde"] else ""
        print(f"  {a['symbol']} {a['name_ru']:8} {a['sign_ru']:11} {a['degrees']:5.2f}°  дом {a['house']}{retro}")
    print()
    print(f"🔗 Аспекты к наталу: {len(aspects)}")
    for asp in aspects[:10]:
        print(f"  {asp['asteroid_name']:8} {asp['aspect_symbol']} {asp['natal_name']:14} орб {asp['orb']:.2f}°  ({asp['nature']})")

    # Сохранение JSON
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    name_slug = natal["meta"]["name"].lower().replace(" ", "_")
    json_out = outdir / f"asteroids_{name_slug}.json"
    result = {
        "meta": {
            "natal_meta": natal["meta"],
            "jd_ut": jd,
            "module": "asteroids",
            "module_version": "1.0",
            "computed_at": datetime.now().isoformat(),
        },
        "asteroids": asteroids,
        "aspects": aspects,
    }
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n💾 JSON: {json_out}")

    # DOCX
    if not args.no_docx:
        try:
            from render_asteroids_docx import render_asteroids_docx
            docx_out = outdir / f"asteroids_{name_slug}.docx"
            render_asteroids_docx(result, str(docx_out))
            print(f"📄 DOCX: {docx_out}")
        except Exception as e:
            print(f"⚠️  DOCX рендер не удался: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
