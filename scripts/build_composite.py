#!/usr/bin/env python3.11
"""
astro-natal-simond: build_composite.py
Композитная карта (midpoint composite) — карта отношений как «третья сущность».

Каждая позиция композита = середина дуги между соответствующими планетами
двух людей. Это не транзит и не синастрия — это «характер отношений сам по себе».

Использование:
  python3.11 build_composite.py \\
    --natal1 ~/.astro-natal-simond/cache/dmitriy_1993-08-13_moskva_western.json \\
    --natal2 ~/.astro-natal-simond/cache/anna_1995-03-15_sankt-peterburg_western.json \\
    --outdir /tmp/astro-comp-dima-anna
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


def midpoint(a, b):
    """Кратчайший midpoint между двумя долготами на круге.
    Если разница > 180°, midpoint берётся через 'короткую сторону' круга."""
    a = normalize_angle(a)
    b = normalize_angle(b)
    diff = (b - a) % 360
    if diff > 180:
        diff -= 360
    return normalize_angle(a + diff / 2)


def position_to_dict(absolute_pos, key):
    abs_pos = normalize_angle(absolute_pos)
    sign_idx = int(abs_pos // 30)
    return {
        'absolute': round(abs_pos, 4),
        'sign_idx': sign_idx,
        'sign_ru': SIGN_RU[sign_idx],
        'degrees': round(abs_pos % 30, 2),
        'symbol': PLANET_SYMBOLS.get(key, ''),
        'name_ru': PLANET_RU.get(key, key),
    }


def compute_composite_planets(natal1, natal2):
    """Composite = midpoint каждой пары планет."""
    p1 = natal1.get('planets', {})
    p2 = natal2.get('planets', {})
    result = {}
    for k in p1:
        if k not in p2:
            continue
        a1 = p1[k].get('abs_pos')
        a2 = p2[k].get('abs_pos')
        if a1 is None or a2 is None:
            continue
        mid = midpoint(a1, a2)
        result[k] = position_to_dict(mid, k)
    return result


def compute_composite_angles(natal1, natal2):
    """Composite ASC и MC = midpoint двух соответствующих углов."""
    h1 = natal1.get('houses', {})
    h2 = natal2.get('houses', {})
    angles = {}
    for num, attr in [('1', 'ascendant'), ('10', 'mc')]:
        c1 = h1.get(num, {}).get('abs_pos')
        c2 = h2.get(num, {}).get('abs_pos')
        if c1 is None or c2 is None:
            continue
        mid = midpoint(c1, c2)
        sign_idx = int(normalize_angle(mid) // 30)
        angles[attr] = {
            'absolute': round(mid, 4),
            'sign_idx': sign_idx,
            'sign_ru': SIGN_RU[sign_idx],
            'degrees': round(normalize_angle(mid) % 30, 2),
        }
    return angles


def compute_composite_houses_whole_sign(asc_data):
    """Дома композита по системе Whole Sign от composite ASC.
    Это упрощение — точные Плацидус-дома требуют пересчёта от полночной локации,
    что не имеет смысла для midpoint composite.
    Whole Sign даёт чистый и осмысленный результат."""
    if not asc_data:
        return {}
    asc_sign = asc_data['sign_idx']
    houses = {}
    for i in range(12):
        sign_idx = (asc_sign + i) % 12
        houses[str(i + 1)] = {
            'sign_ru': SIGN_RU[sign_idx],
            'sign_idx': sign_idx,
            'absolute': round(sign_idx * 30, 2),
            'degrees': 0,
        }
    return houses


def find_house_for_position(position, houses):
    pos = normalize_angle(position)
    for i in range(1, 13):
        h = houses.get(str(i))
        if not h:
            continue
        cusp = h['absolute']
        next_cusp = (cusp + 30) % 360
        if next_cusp < cusp:
            if pos >= cusp or pos < next_cusp:
                return i
        else:
            if cusp <= pos < next_cusp:
                return i
    return None


def compute_composite_aspects(planets, angles):
    """Аспекты внутри композита (между планетами + к ASC/MC)."""
    points = dict(planets)
    if angles.get('ascendant'):
        a = angles['ascendant']
        points['ascendant'] = {**a, 'name_ru': 'Асцендент', 'symbol': '↑'}
    if angles.get('mc'):
        m = angles['mc']
        points['mc'] = {**m, 'name_ru': 'MC', 'symbol': '⊕'}

    aspects = []
    keys = list(points.keys())
    for i, k1 in enumerate(keys):
        for k2 in keys[i+1:]:
            p1 = points[k1]
            p2 = points[k2]
            arc = angular_distance(p1['absolute'], p2['absolute'])
            for name, exact, symbol in ASPECTS:
                diff = abs(arc - exact)
                if diff <= 5.0:
                    aspects.append({
                        'planet1': k1,
                        'planet1_ru': p1['name_ru'],
                        'planet1_symbol': p1['symbol'],
                        'planet2': k2,
                        'planet2_ru': p2['name_ru'],
                        'planet2_symbol': p2['symbol'],
                        'aspect': name,
                        'aspect_ru': ASPECT_RU.get(name, name),
                        'aspect_symbol': symbol,
                        'aspect_nature': ASPECT_NATURE.get(name, 'neutral'),
                        'orb': round(diff, 2),
                    })
                    break
    aspects.sort(key=lambda x: x['orb'])
    return aspects


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--natal1', required=True)
    p.add_argument('--natal2', required=True)
    p.add_argument('--outdir')
    args = p.parse_args()

    n1_path = Path(args.natal1).expanduser()
    n2_path = Path(args.natal2).expanduser()
    if not n1_path.exists() or not n2_path.exists():
        print(f"❌ Один из наталов не найден", file=sys.stderr)
        sys.exit(1)

    print(f"  📖 Натал 1: {n1_path.name}")
    print(f"  📖 Натал 2: {n2_path.name}")
    with open(n1_path, 'r', encoding='utf-8') as f:
        natal1 = json.load(f)
    with open(n2_path, 'r', encoding='utf-8') as f:
        natal2 = json.load(f)

    name1 = natal1.get('meta', {}).get('name', 'Person1')
    name2 = natal2.get('meta', {}).get('name', 'Person2')

    planets = compute_composite_planets(natal1, natal2)
    angles = compute_composite_angles(natal1, natal2)
    houses = compute_composite_houses_whole_sign(angles.get('ascendant'))

    # Дома планет композита (Whole Sign)
    for k, p_data in planets.items():
        p_data['house'] = find_house_for_position(p_data['absolute'], houses)

    aspects = compute_composite_aspects(planets, angles)

    comp_json = {
        'meta': {
            'person1_name': name1,
            'person1_date': natal1.get('meta', {}).get('date'),
            'person2_name': name2,
            'person2_date': natal2.get('meta', {}).get('date'),
            'method': 'midpoint',
            'house_system': 'Whole Sign (от composite ASC)',
            'computed_at': datetime.now().isoformat(timespec='seconds'),
        },
        'composite_planets': planets,
        'composite_angles': angles,
        'composite_houses': houses,
        'aspects': aspects,
        'totals': {
            'aspects_total': len(aspects),
            'tense': sum(1 for a in aspects if a.get('aspect_nature') == 'tense'),
            'harmonious': sum(1 for a in aspects if a.get('aspect_nature') == 'harmonious'),
        },
    }

    slug = f"{slugify(name1)}_x_{slugify(name2)}"
    if args.outdir:
        outdir = Path(args.outdir)
    else:
        outdir = Path('./composite-reports') / slug
    outdir.mkdir(parents=True, exist_ok=True)

    json_path = outdir / f"composite_{slug}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(comp_json, f, ensure_ascii=False, indent=2)
    print(f"  📊 JSON: {json_path}")

    print(f"\n  ┌── КОМПОЗИТ {name1} × {name2} ──")
    asc = angles.get('ascendant', {})
    sun = planets.get('sun', {})
    moon = planets.get('moon', {})
    print(f"  │  Composite ASC: {asc.get('sign_ru', '?')} {asc.get('degrees', '?')}°")
    print(f"  │  Composite Sun: {sun.get('sign_ru', '?')} {sun.get('degrees', '?')}° (дом {sun.get('house')})")
    print(f"  │  Composite Moon: {moon.get('sign_ru', '?')} {moon.get('degrees', '?')}° (дом {moon.get('house')})")
    print(f"  │  Аспектов: {len(aspects)} ({comp_json['totals']['harmonious']} гарм. / {comp_json['totals']['tense']} напр.)")
    print(f"  └── ✅ Готово. Следующий шаг: render_composite_docx.py")


if __name__ == '__main__':
    main()
