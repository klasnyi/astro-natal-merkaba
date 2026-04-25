#!/usr/bin/env python3.11
"""
astro-natal-merkaba: build_synastry.py
Синастрия — сравнение двух натальных карт для оценки совместимости.

Что считает:
- Cross-аспекты: планеты person1 × планеты person2 (с орбом ≤6°)
- House overlay: где планеты person1 в домах person2 (и обратно)
- Ключевые романтические индикаторы (Sun-Moon, Venus-Mars контакты)
- Топ-15 самых сильных контактов

Использование:
  python3.11 build_synastry.py \\
    --natal1 ~/.astro-natal-merkaba/cache/dmitriy_1993-08-13_moskva_western.json \\
    --natal2 ~/.astro-natal-merkaba/cache/anna_1995-03-15_spb_western.json \\
    --outdir /tmp/astro-syn-dima-anna
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from astro_helpers import slugify

from build_transits import (
    PLANET_RU, PLANET_SYMBOLS, SIGN_RU,
    ASPECTS, ASPECT_RU, ASPECT_NATURE,
    angular_distance, normalize_angle,
)


# Синастрические орбы — немного шире транзитных, но с учётом соединений
SYNASTRY_ORBS = {
    'sun': 6.0, 'moon': 6.0,
    'mercury': 5.0, 'venus': 5.0, 'mars': 5.0,
    'jupiter': 5.0, 'saturn': 5.0,
    'uranus': 4.0, 'neptune': 4.0, 'pluto': 4.0,
    'chiron': 4.0, 'true_north_lunar_node': 4.0,
}

# Веса значимости для синастрии
PERSONAL_WEIGHT = {
    'sun': 10, 'moon': 10, 'venus': 9, 'mars': 8,
    'mercury': 7, 'ascendant': 10, 'mc': 8,
    'jupiter': 5, 'saturn': 6,
    'uranus': 4, 'neptune': 4, 'pluto': 5,
    'chiron': 5, 'true_north_lunar_node': 5,
}

# Романтические комбинации — критичные для оценки совместимости
ROMANTIC_PAIRS = {
    ('sun', 'moon'),    # инь-ян ядро
    ('moon', 'sun'),
    ('venus', 'mars'),  # любовь-страсть
    ('mars', 'venus'),
    ('sun', 'venus'),   # привлекательность
    ('venus', 'sun'),
    ('moon', 'venus'),  # эмоциональная гармония
    ('venus', 'moon'),
    ('moon', 'mars'),   # чувства-действие
    ('mars', 'moon'),
}


def find_synastry_aspect(p1_pos, p2_pos, p1_key, p2_key):
    """Аспект между двумя точками для синастрии."""
    arc = angular_distance(p1_pos, p2_pos)
    # Берём максимальный из двух орбов планет
    orb_max = max(SYNASTRY_ORBS.get(p1_key, 4.0), SYNASTRY_ORBS.get(p2_key, 4.0))
    for name, exact, symbol in ASPECTS:
        diff = abs(arc - exact)
        if diff <= orb_max:
            return {'name': name, 'exact_angle': exact,
                    'orb': round(diff, 2), 'symbol': symbol}
    return None


def get_natal_points(natal):
    """Все натальные точки (планеты + ASC/MC) с долготами."""
    points = {}
    for k, d in natal.get('planets', {}).items():
        if d.get('abs_pos') is None:
            continue
        points[k] = {
            'absolute': d['abs_pos'],
            'sign_ru': d.get('sign_ru', '?'),
            'degrees': d.get('degrees', 0),
            'house': d.get('house'),
            'name_ru': PLANET_RU.get(k, k),
            'symbol': PLANET_SYMBOLS.get(k, ''),
            'is_personal': k in ('sun', 'moon', 'mercury', 'venus', 'mars'),
        }
    houses = natal.get('houses', {})
    if '1' in houses:
        points['ascendant'] = {
            'absolute': houses['1'].get('abs_pos'),
            'sign_ru': houses['1'].get('sign_ru', '?'),
            'degrees': houses['1'].get('degrees', 0),
            'name_ru': 'Асцендент', 'symbol': '↑', 'is_personal': True,
        }
    if '10' in houses:
        points['mc'] = {
            'absolute': houses['10'].get('abs_pos'),
            'sign_ru': houses['10'].get('sign_ru', '?'),
            'degrees': houses['10'].get('degrees', 0),
            'name_ru': 'MC', 'symbol': '⊕', 'is_personal': True,
        }
    return points


def find_house_for_position(position, natal):
    """В каком доме (натала второго) находится позиция планеты первого."""
    houses = natal.get('houses', {})
    if not houses:
        return None
    pos = normalize_angle(position)
    cusps = []
    for i in range(1, 13):
        h = houses.get(str(i))
        if h and h.get('abs_pos') is not None:
            cusps.append((i, h['abs_pos']))
    if len(cusps) < 12:
        return None
    cusps.sort(key=lambda x: x[1])
    for i, (h_num, cusp) in enumerate(cusps):
        next_cusp = cusps[(i + 1) % 12][1]
        if next_cusp < cusp:  # wrap
            if pos >= cusp or pos < next_cusp:
                return h_num
        else:
            if cusp <= pos < next_cusp:
                return h_num
    return None


def compute_cross_aspects(points1, points2, name1, name2):
    """Все cross-аспекты между двумя картами."""
    aspects = []
    # Только реальные планеты для p1, исключаем ASC/MC (нет аспектов от угла к углу)
    for k1, d1 in points1.items():
        for k2, d2 in points2.items():
            if d1.get('absolute') is None or d2.get('absolute') is None:
                continue
            asp = find_synastry_aspect(d1['absolute'], d2['absolute'], k1, k2)
            if not asp:
                continue
            # Скоринг
            score = (PERSONAL_WEIGHT.get(k1, 3) + PERSONAL_WEIGHT.get(k2, 3) +
                     max(0, 5 - asp['orb']) * 2)
            if (k1, k2) in ROMANTIC_PAIRS:
                score += 5  # романтические комбинации
            if asp['name'] == 'conjunction':
                score += 2  # соединения сильнее остальных в синастрии

            aspects.append({
                'p1_owner': name1,
                'p1_key': k1,
                'p1_ru': d1['name_ru'],
                'p1_symbol': d1['symbol'],
                'p1_sign_ru': d1['sign_ru'],
                'p1_degrees': d1['degrees'],
                'p2_owner': name2,
                'p2_key': k2,
                'p2_ru': d2['name_ru'],
                'p2_symbol': d2['symbol'],
                'p2_sign_ru': d2['sign_ru'],
                'p2_degrees': d2['degrees'],
                'aspect': asp['name'],
                'aspect_ru': ASPECT_RU.get(asp['name'], asp['name']),
                'aspect_symbol': asp['symbol'],
                'aspect_nature': ASPECT_NATURE.get(asp['name'], 'neutral'),
                'orb': asp['orb'],
                'is_romantic': (k1, k2) in ROMANTIC_PAIRS,
                'intensity_score': round(score, 1),
                'key': f"{name1}_{k1}_{asp['name']}_{name2}_{k2}",
            })
    aspects.sort(key=lambda x: -x['intensity_score'])
    return aspects


def compute_house_overlays(points_from, natal_into, owner_from, owner_into):
    """Где планеты owner_from падают в домах owner_into."""
    overlays = []
    for k, d in points_from.items():
        # ASC/MC не нужны в overlay (это углы своей карты)
        if k in ('ascendant', 'mc'):
            continue
        if d.get('absolute') is None:
            continue
        house = find_house_for_position(d['absolute'], natal_into)
        if house is None:
            continue
        overlays.append({
            'planet_key': k,
            'planet_ru': d['name_ru'],
            'symbol': d['symbol'],
            'sign_ru': d['sign_ru'],
            'degrees': d['degrees'],
            'falls_in_house': house,
            'owner': owner_from,
            'in_chart_of': owner_into,
        })
    return overlays


def compute_summary(aspects, name1, name2):
    """Ключевые романтические комбинации + сводка."""
    summary = {
        'romantic_aspects': [a for a in aspects if a.get('is_romantic')],
        'sun_moon_contacts': [a for a in aspects
                              if {a['p1_key'], a['p2_key']} == {'sun', 'moon'}],
        'venus_mars_contacts': [a for a in aspects
                                 if {a['p1_key'], a['p2_key']} == {'venus', 'mars'}],
        'tense_aspects_count': sum(1 for a in aspects if a.get('aspect_nature') == 'tense'),
        'harmonious_aspects_count': sum(1 for a in aspects if a.get('aspect_nature') == 'harmonious'),
        'conjunctions_count': sum(1 for a in aspects if a['aspect'] == 'conjunction'),
    }
    return summary


def main():
    p = argparse.ArgumentParser(description='Синастрия двух натальных карт')
    p.add_argument('--natal1', required=True, help='Путь к chart.json первого человека')
    p.add_argument('--natal2', required=True, help='Путь к chart.json второго человека')
    p.add_argument('--outdir')
    args = p.parse_args()

    # Загрузка наталов
    n1_path = Path(args.natal1).expanduser()
    n2_path = Path(args.natal2).expanduser()
    if not n1_path.exists():
        print(f"❌ Натал 1 не найден: {n1_path}", file=sys.stderr); sys.exit(1)
    if not n2_path.exists():
        print(f"❌ Натал 2 не найден: {n2_path}", file=sys.stderr); sys.exit(1)

    print(f"  📖 Натал 1: {n1_path.name}")
    print(f"  📖 Натал 2: {n2_path.name}")
    with open(n1_path, 'r', encoding='utf-8') as f:
        natal1 = json.load(f)
    with open(n2_path, 'r', encoding='utf-8') as f:
        natal2 = json.load(f)

    name1 = natal1.get('meta', {}).get('name', 'Person1')
    name2 = natal2.get('meta', {}).get('name', 'Person2')

    points1 = get_natal_points(natal1)
    points2 = get_natal_points(natal2)

    # Cross-аспекты
    cross = compute_cross_aspects(points1, points2, name1, name2)
    print(f"  ⭐ Найдено {len(cross)} cross-аспектов")

    # House overlays (направление А→В и В→А)
    overlay_1_to_2 = compute_house_overlays(points1, natal2, name1, name2)
    overlay_2_to_1 = compute_house_overlays(points2, natal1, name2, name1)

    # Сводка
    summary = compute_summary(cross, name1, name2)

    syn_json = {
        'meta': {
            'person1_name': name1,
            'person1_date': natal1.get('meta', {}).get('date'),
            'person1_city': natal1.get('meta', {}).get('city'),
            'person2_name': name2,
            'person2_date': natal2.get('meta', {}).get('date'),
            'person2_city': natal2.get('meta', {}).get('city'),
            'computed_at': datetime.now().isoformat(timespec='seconds'),
        },
        'cross_aspects_top': cross[:20],
        'all_cross_aspects': cross,
        'house_overlay_1_to_2': overlay_1_to_2,
        'house_overlay_2_to_1': overlay_2_to_1,
        'summary': summary,
        'totals': {
            'cross_aspects_total': len(cross),
            'romantic_aspects_count': len(summary['romantic_aspects']),
            'tense_count': summary['tense_aspects_count'],
            'harmonious_count': summary['harmonious_aspects_count'],
            'conjunctions_count': summary['conjunctions_count'],
        },
    }

    slug = f"{slugify(name1)}_x_{slugify(name2)}"
    if args.outdir:
        outdir = Path(args.outdir)
    else:
        outdir = Path('./synastry-reports') / slug
    outdir.mkdir(parents=True, exist_ok=True)

    json_path = outdir / f"synastry_{slug}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(syn_json, f, ensure_ascii=False, indent=2)
    print(f"  📊 JSON: {json_path}")

    print(f"\n  ┌── СИНАСТРИЯ {name1} × {name2} ──")
    print(f"  │  Всего cross-аспектов: {len(cross)}")
    print(f"  │  Романтических: {len(summary['romantic_aspects'])}")
    print(f"  │  Гармоничных/напряжённых: {summary['harmonious_aspects_count']} / {summary['tense_aspects_count']}")
    print(f"  │  Соединений: {summary['conjunctions_count']}")
    if cross:
        a = cross[0]
        print(f"  │  Топ-1: {a['p1_symbol']} {a['p1_ru']} ({name1}) {a['aspect_symbol']} "
              f"{a['p2_symbol']} {a['p2_ru']} ({name2}) — орб {a['orb']}°")
    print(f"  └── ✅ Готово. Следующий шаг: render_synastry_docx.py")
    return str(json_path)


if __name__ == '__main__':
    main()
