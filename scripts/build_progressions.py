#!/usr/bin/env python3.11
"""
astro-natal-merkaba: build_progressions.py
Считает секундарные прогрессии (1 день после рождения = 1 год жизни).

Прогрессированная карта — это не "что снаружи", а символическое внутреннее
развитие личности. Ключевые элементы: прогрессированное Солнце (1° = 1 год
смещения фокуса), прогрессированная Луна (полный цикл за ~28 лет —
эмоциональная погода 2-3-летних периодов), аспекты прогрессий к наталу.

Использование:
  python3.11 build_progressions.py \\
    --natal ~/.astro-natal-merkaba/cache/dmitriy_1993-08-13_moskva_western.json \\
    --age 32.7 \\
    --outdir /tmp/astro-progressions-dima

  # Или возраст автоматически (на сегодня):
  python3.11 build_progressions.py \\
    --natal ~/.astro-natal-merkaba/cache/dmitriy_1993-08-13_moskva_western.json
"""
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from astro_helpers import slugify

try:
    from kerykeion import AstrologicalSubject
except ImportError:
    print("❌ kerykeion не установлен", file=sys.stderr)
    sys.exit(1)

# Используем те же константы что и для транзитов
from build_transits import (
    PLANET_RU, PLANET_SYMBOLS, SIGN_RU, SIGN_EN_TO_IDX,
    ASPECTS, ASPECT_RU, ASPECT_NATURE,
    angular_distance, normalize_angle, find_aspect,
    NATAL_POINT_WEIGHT,
)


# ─── ПРОГРЕССИОННЫЕ КОНСТАНТЫ ─────────────────────────────────────────────

# Прогрессированные орбы — ОЧЕНЬ узкие (планеты движутся медленно символически)
PROGRESSED_ORBS = {
    'sun': 1.0, 'moon': 1.0, 'mercury': 0.8, 'venus': 0.8, 'mars': 0.6,
    'jupiter': 0.5, 'saturn': 0.5,
    'uranus': 0.3, 'neptune': 0.3, 'pluto': 0.3, 'chiron': 0.5,
    'true_north_lunar_node': 0.6,
}

# Веса значимости для прогрессий (Луна и Солнце доминируют)
PROGRESSED_WEIGHT = {
    'sun': 10, 'moon': 10,
    'mercury': 7, 'venus': 7, 'mars': 7,
    'jupiter': 5, 'saturn': 5,
    'uranus': 3, 'neptune': 3, 'pluto': 3, 'chiron': 5,
    'true_north_lunar_node': 4,
}

# Фазы лунного цикла прогрессированной Луны (от прогрессированного Солнца)
MOON_PHASES = [
    (0,    45,   'New Moon → Crescent', 'Начало нового цикла, посев'),
    (45,   90,   'Crescent → First Quarter', 'Прорастание, преодоление'),
    (90,   135,  'First Quarter → Gibbous', 'Действие, кризис, выбор'),
    (135,  180,  'Gibbous → Full Moon', 'Кристаллизация, подготовка к пику'),
    (180,  225,  'Full Moon → Disseminating', 'Пик, осознание, обнародование'),
    (225,  270,  'Disseminating → Last Quarter', 'Раздача, передача знаний'),
    (270,  315,  'Last Quarter → Balsamic', 'Кризис веры, очищение'),
    (315,  360,  'Balsamic → New Moon', 'Растворение, отпускание, вход в новое'),
]


def moon_phase(sun_pos, moon_pos):
    """Возвращает (degree_separation, phase_name, phase_meaning)."""
    sep = (normalize_angle(moon_pos) - normalize_angle(sun_pos)) % 360
    for low, high, name, meaning in MOON_PHASES:
        if low <= sep < high:
            return round(sep, 1), name, meaning
    return round(sep, 1), '?', '?'


def detect_ingress(natal_planet_pos, progressed_planet_pos, planet_key):
    """
    Возвращает ingress info если прогрессированная планета сменила знак
    относительно натальной (или близка к смене).
    """
    natal_sign = int(normalize_angle(natal_planet_pos) // 30)
    prog_sign = int(normalize_angle(progressed_planet_pos) // 30)

    if natal_sign != prog_sign:
        return {
            'planet': planet_key,
            'planet_ru': PLANET_RU.get(planet_key, planet_key),
            'symbol': PLANET_SYMBOLS.get(planet_key, ''),
            'natal_sign': SIGN_RU[natal_sign],
            'progressed_sign': SIGN_RU[prog_sign],
            'note': f'Прогрессия сменила знак с {SIGN_RU[natal_sign]} на {SIGN_RU[prog_sign]}',
        }
    # Близко к смене знака?
    deg_in_sign = normalize_angle(progressed_planet_pos) % 30
    if deg_in_sign > 28.5:
        next_sign_idx = (prog_sign + 1) % 12
        return {
            'planet': planet_key,
            'planet_ru': PLANET_RU.get(planet_key, planet_key),
            'symbol': PLANET_SYMBOLS.get(planet_key, ''),
            'natal_sign': SIGN_RU[natal_sign],
            'progressed_sign': SIGN_RU[prog_sign],
            'note': f'Прогрессия в {deg_in_sign:.1f}° {SIGN_RU[prog_sign]} — близко к переходу в {SIGN_RU[next_sign_idx]} (≈{30 - deg_in_sign:.1f}° = ~{30 - deg_in_sign:.1f} лет)',
        }
    return None


# ─── РАСЧЁТ ───────────────────────────────────────────────────────────────

def load_natal(natal_path):
    with open(natal_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def compute_age_years(natal_meta):
    """Возраст в годах с десятичной точностью на сегодня."""
    natal_date = datetime.fromisoformat(natal_meta['date'])
    if natal_meta.get('time'):
        h, m = map(int, natal_meta['time'].split(':'))
        natal_dt = datetime(natal_date.year, natal_date.month, natal_date.day, h, m)
    else:
        natal_dt = datetime(natal_date.year, natal_date.month, natal_date.day, 12, 0)
    now = datetime.now()
    delta = now - natal_dt
    return delta.total_seconds() / (365.25 * 24 * 3600)


def progressed_date(natal_meta, age_years):
    """natal_date + age_years дней = прогрессированная дата."""
    natal_date = datetime.fromisoformat(natal_meta['date'])
    if natal_meta.get('time'):
        h, m = map(int, natal_meta['time'].split(':'))
        base = datetime(natal_date.year, natal_date.month, natal_date.day, h, m)
    else:
        base = datetime(natal_date.year, natal_date.month, natal_date.day, 12, 0)
    return base + timedelta(days=age_years)


def build_progressed_subject(prog_dt, lat, lon, tz_str, name):
    return AstrologicalSubject(
        f'{name}_progressed',
        prog_dt.year, prog_dt.month, prog_dt.day,
        prog_dt.hour, prog_dt.minute,
        lng=lon, lat=lat, tz_str=tz_str,
        zodiac_type='Tropical', online=False
    )


def extract_progressed_planets(subject):
    planets = {}
    obj_map = {
        'sun': subject.sun, 'moon': subject.moon,
        'mercury': subject.mercury, 'venus': subject.venus, 'mars': subject.mars,
        'jupiter': subject.jupiter, 'saturn': subject.saturn,
        'uranus': subject.uranus, 'neptune': subject.neptune, 'pluto': subject.pluto,
        'true_north_lunar_node': getattr(subject, 'mean_north_lunar_node',
                                          getattr(subject, 'mean_node', None)),
        'chiron': getattr(subject, 'chiron', None),
    }
    for key, obj in obj_map.items():
        if obj is None:
            continue
        sign_idx = SIGN_EN_TO_IDX.get(obj.sign, 0)
        planets[key] = {
            'absolute': round(obj.abs_pos, 4),
            'sign_idx': sign_idx,
            'sign_ru': SIGN_RU[sign_idx],
            'degrees': round(obj.position, 2),
            'retrograde': bool(getattr(obj, 'retrograde', False)),
            'symbol': PLANET_SYMBOLS.get(key, ''),
            'name_ru': PLANET_RU.get(key, key),
        }
    return planets


def compute_progressed_aspects(progressed_planets, natal_chart):
    """Аспекты от прогрессий к натальным точкам."""
    aspects = []
    natal_planets = natal_chart.get('planets', {})
    natal_houses = natal_chart.get('houses', {})

    natal_points = {}
    for k, d in natal_planets.items():
        if d.get('abs_pos') is None:
            continue
        natal_points[k] = {
            'absolute': d['abs_pos'],
            'sign_ru': d.get('sign_ru', '?'),
            'degrees': d.get('degrees', 0),
            'house': d.get('house'),
            'name_ru': PLANET_RU.get(k, k),
            'symbol': PLANET_SYMBOLS.get(k, ''),
        }
    if natal_houses:
        if '1' in natal_houses:
            natal_points['ascendant'] = {
                'absolute': natal_houses['1'].get('abs_pos'),
                'sign_ru': natal_houses['1'].get('sign_ru', '?'),
                'degrees': natal_houses['1'].get('degrees', 0),
                'name_ru': 'Асцендент', 'symbol': '↑',
            }
        if '10' in natal_houses:
            natal_points['mc'] = {
                'absolute': natal_houses['10'].get('abs_pos'),
                'sign_ru': natal_houses['10'].get('sign_ru', '?'),
                'degrees': natal_houses['10'].get('degrees', 0),
                'name_ru': 'MC', 'symbol': '⊕',
            }

    for pk, pdata in progressed_planets.items():
        pp = pdata['absolute']
        for nk, ndata in natal_points.items():
            np_pos = ndata.get('absolute')
            if np_pos is None:
                continue
            # Используем прогрессионные орбы вместо транзитных
            arc = angular_distance(pp, np_pos)
            orb_max = PROGRESSED_ORBS.get(pk, 0.5)
            best = None
            for name, exact, symbol in ASPECTS:
                diff = abs(arc - exact)
                if diff <= orb_max:
                    best = {'name': name, 'exact_angle': exact,
                            'orb': round(diff, 2), 'symbol': symbol}
                    break
            if not best:
                continue

            score = (PROGRESSED_WEIGHT.get(pk, 5) * 2 +
                     NATAL_POINT_WEIGHT.get(nk, 5) * 2 +
                     max(0, 2 - best['orb']) * 3)

            aspects.append({
                'progressed_planet': pk,
                'progressed_planet_ru': pdata['name_ru'],
                'progressed_symbol': pdata['symbol'],
                'progressed_sign_ru': pdata['sign_ru'],
                'progressed_degrees': pdata['degrees'],
                'progressed_retrograde': pdata['retrograde'],
                'natal_point': nk,
                'natal_point_ru': ndata['name_ru'],
                'natal_symbol': ndata['symbol'],
                'natal_sign_ru': ndata['sign_ru'],
                'natal_degrees': ndata['degrees'],
                'natal_house': ndata.get('house'),
                'aspect': best['name'],
                'aspect_ru': ASPECT_RU.get(best['name'], best['name']),
                'aspect_symbol': best['symbol'],
                'aspect_nature': ASPECT_NATURE.get(best['name'], 'neutral'),
                'orb': best['orb'],
                'intensity_score': round(score, 1),
                'key': f"prog_{pk}_{best['name']}_{nk}",
            })
    aspects.sort(key=lambda x: -x['intensity_score'])
    return aspects


def main():
    p = argparse.ArgumentParser(description='Секундарные прогрессии')
    p.add_argument('--natal', required=True)
    p.add_argument('--age', type=float, help='Возраст лет (default: на сегодня)')
    p.add_argument('--outdir')
    args = p.parse_args()

    natal_path = Path(args.natal).expanduser()
    if not natal_path.exists():
        print(f"❌ Натал не найден: {natal_path}", file=sys.stderr)
        sys.exit(1)

    print(f"  📖 Натал: {natal_path.name}")
    natal = load_natal(natal_path)
    meta = natal.get('meta', {})
    name = meta.get('name', 'Unknown')

    age = args.age if args.age is not None else compute_age_years(meta)
    prog_dt = progressed_date(meta, age)
    print(f"  ⏳ Возраст: {age:.2f} лет")
    print(f"  📅 Прогрессированная дата: {prog_dt.strftime('%d.%m.%Y %H:%M')}")

    lat = meta.get('lat')
    lon = meta.get('lon')
    tz_str = meta.get('tz', 'UTC')
    if lat is None or lon is None:
        print(f"❌ Нет координат в натале", file=sys.stderr)
        sys.exit(1)

    subject = build_progressed_subject(prog_dt, lat, lon, tz_str, name)
    prog_planets = extract_progressed_planets(subject)

    # Лунная фаза
    sun_pos = prog_planets['sun']['absolute']
    moon_pos = prog_planets['moon']['absolute']
    moon_sep, phase_name, phase_meaning = moon_phase(sun_pos, moon_pos)

    # Аспекты
    aspects = compute_progressed_aspects(prog_planets, natal)

    # Ingresses (смена знака прогрессией относительно натала)
    ingresses = []
    natal_planets = natal.get('planets', {})
    for pk, pdata in prog_planets.items():
        natal_pos = natal_planets.get(pk, {}).get('abs_pos')
        if natal_pos is None:
            continue
        ing = detect_ingress(natal_pos, pdata['absolute'], pk)
        if ing:
            ingresses.append(ing)

    # JSON
    prog_json = {
        'meta': {
            'natal_name': name,
            'natal_date': meta.get('date'),
            'natal_city': meta.get('city'),
            'age_years': round(age, 3),
            'progressed_date': prog_dt.strftime('%Y-%m-%d'),
            'progressed_time': prog_dt.strftime('%H:%M'),
            'computed_at': datetime.now().isoformat(timespec='seconds'),
        },
        'progressed_planets': prog_planets,
        'progressed_moon_phase': {
            'separation_degrees': moon_sep,
            'phase_name': phase_name,
            'phase_meaning': phase_meaning,
            'sun_sign': prog_planets['sun']['sign_ru'],
            'sun_degrees': prog_planets['sun']['degrees'],
            'moon_sign': prog_planets['moon']['sign_ru'],
            'moon_degrees': prog_planets['moon']['degrees'],
        },
        'aspects_to_natal': aspects[:15],
        'all_aspects_count': len(aspects),
        'ingresses': ingresses,
        'totals': {
            'aspects_total': len(aspects),
            'aspects_to_luminaries_or_angles': sum(
                1 for a in aspects
                if a['natal_point'] in ('sun', 'moon', 'ascendant', 'mc')
            ),
        },
    }

    name_slug = slugify(name)
    if args.outdir:
        outdir = Path(args.outdir)
    else:
        outdir = Path('./progressions-reports') / f"{name_slug}_{int(age)}"
    outdir.mkdir(parents=True, exist_ok=True)

    json_path = outdir / f"progressions_{name_slug}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(prog_json, f, ensure_ascii=False, indent=2)
    print(f"  📊 JSON: {json_path}")

    print(f"\n  ┌── ПРОГРЕССИИ {name} (возраст {age:.1f}) ──")
    print(f"  │  Прогр. Солнце: {prog_planets['sun']['sign_ru']} {prog_planets['sun']['degrees']}°")
    print(f"  │  Прогр. Луна:   {prog_planets['moon']['sign_ru']} {prog_planets['moon']['degrees']}°")
    print(f"  │  Лунная фаза:   {phase_name} (разделение {moon_sep}°)")
    if ingresses:
        for ing in ingresses[:3]:
            print(f"  │  Ingress: {ing['symbol']} {ing['planet_ru']} → {ing['progressed_sign']}")
    print(f"  │  Аспектов к наталу: {len(aspects)}")
    if aspects:
        a = aspects[0]
        print(f"  │  Топ-1: прогр. {a['progressed_planet_ru']} {a['aspect_symbol']} натал. {a['natal_point_ru']} (орб {a['orb']}°)")
    print(f"  └── ✅ Готово. Следующий шаг: render_progressions_docx.py")
    return str(json_path)


if __name__ == '__main__':
    main()
