#!/usr/bin/env python3.11
"""
astro-natal-merkaba: build_transits.py
Считает транзиты планет к натальной карте на заданную дату.

Вход: натальная карта (chart.json от build_chart.py или из кэша).
Выход: transits.json со всеми активными аспектами + ближайшие точности
       + текущие позиции транзитных планет + признаки ретрограда.

Использование:
  python3.11 build_transits.py \\
    --natal ~/.astro-natal-merkaba/cache/dmitriy_1993-08-13_moskva_western.json \\
    --date 25.04.2026 \\
    --time 12:00 \\
    --outdir /tmp/astro-transits-dima
"""
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Local helpers
sys.path.insert(0, str(Path(__file__).parent))
from astro_helpers import parse_date, parse_time, slugify

try:
    from kerykeion import AstrologicalSubject
except ImportError:
    print("❌ kerykeion не установлен: pip install kerykeion", file=sys.stderr)
    sys.exit(1)


# ─── КОНСТАНТЫ ────────────────────────────────────────────────────────────

TRANSIT_PLANETS = [
    'sun', 'moon', 'mercury', 'venus', 'mars',
    'jupiter', 'saturn', 'uranus', 'neptune', 'pluto',
    'true_north_lunar_node', 'chiron'
]

PLANET_RU = {
    'sun': 'Солнце', 'moon': 'Луна', 'mercury': 'Меркурий',
    'venus': 'Венера', 'mars': 'Марс', 'jupiter': 'Юпитер',
    'saturn': 'Сатурн', 'uranus': 'Уран', 'neptune': 'Нептун',
    'pluto': 'Плутон', 'true_north_lunar_node': 'С.Узел',
    'chiron': 'Хирон', 'mean_lilith': 'Лилит',
}

PLANET_SYMBOLS = {
    'sun': '☉', 'moon': '☽', 'mercury': '☿', 'venus': '♀',
    'mars': '♂', 'jupiter': '♃', 'saturn': '♄', 'uranus': '♅',
    'neptune': '♆', 'pluto': '♇', 'true_north_lunar_node': '☊',
    'chiron': '⚷', 'mean_lilith': '⚸',
}

SIGN_RU = ['Овен', 'Телец', 'Близнецы', 'Рак', 'Лев', 'Дева',
           'Весы', 'Скорпион', 'Стрелец', 'Козерог', 'Водолей', 'Рыбы']

SIGN_EN_TO_IDX = {
    'Ari': 0, 'Aries': 0, 'Tau': 1, 'Taurus': 1, 'Gem': 2, 'Gemini': 2,
    'Can': 3, 'Cancer': 3, 'Leo': 4, 'Vir': 5, 'Virgo': 5,
    'Lib': 6, 'Libra': 6, 'Sco': 7, 'Scorpio': 7,
    'Sag': 8, 'Sagittarius': 8, 'Cap': 9, 'Capricorn': 9,
    'Aqu': 10, 'Aquarius': 10, 'Pis': 11, 'Pisces': 11,
}

# Главные аспекты с их точными углами
ASPECTS = [
    ('conjunction', 0,   '☌'),
    ('sextile',     60,  '⚹'),
    ('square',      90,  '□'),
    ('trine',       120, '△'),
    ('opposition',  180, '☍'),
]

ASPECT_RU = {
    'conjunction': 'соединение', 'sextile': 'секстиль',
    'square': 'квадрат', 'trine': 'трин', 'opposition': 'оппозиция',
}

ASPECT_NATURE = {
    'conjunction': 'neutral', 'sextile': 'harmonious',
    'square': 'tense', 'trine': 'harmonious', 'opposition': 'tense',
}

# Транзитные орбы (уже натальных)
TRANSIT_ORBS = {
    'sun': 1.5, 'moon': 1.5, 'mercury': 2.0, 'venus': 2.0, 'mars': 2.0,
    'jupiter': 3.0, 'saturn': 3.0,
    'uranus': 3.0, 'neptune': 3.0, 'pluto': 3.0, 'chiron': 3.0,
    'true_north_lunar_node': 2.0,
}

# Скорости планет (град/сутки, среднее) — для оценки exact_date
PLANET_DAILY_MOTION = {
    'sun': 1.0, 'moon': 13.2, 'mercury': 1.4, 'venus': 1.2, 'mars': 0.524,
    'jupiter': 0.083, 'saturn': 0.034, 'uranus': 0.012, 'neptune': 0.006,
    'pluto': 0.004, 'chiron': 0.05, 'true_north_lunar_node': 0.053,
}

# Веса значимости планет — для топ-сортировки активных транзитов
PLANET_WEIGHT = {
    # Чем медленнее планета, тем дольше длится транзит → значимее
    'pluto': 10, 'neptune': 9, 'uranus': 8, 'saturn': 7, 'chiron': 6,
    'jupiter': 5, 'true_north_lunar_node': 5,
    'mars': 4, 'sun': 4,
    'venus': 3, 'mercury': 3, 'moon': 1,
}

# Веса натальных точек
NATAL_POINT_WEIGHT = {
    'sun': 10, 'moon': 10, 'ascendant': 10, 'mc': 9,
    'mercury': 6, 'venus': 6, 'mars': 6,
    'jupiter': 5, 'saturn': 5,
    'uranus': 4, 'neptune': 4, 'pluto': 4, 'chiron': 5,
    'true_north_lunar_node': 5, 'mean_lilith': 4,
}


# ─── УТИЛИТЫ ──────────────────────────────────────────────────────────────

def normalize_angle(a):
    return a % 360


def angular_distance(a, b):
    d = abs(normalize_angle(a) - normalize_angle(b))
    return 360 - d if d > 180 else d


def find_aspect(transit_pos, natal_pos, transit_planet):
    """Находит аспект между двумя долготами или None."""
    arc = angular_distance(transit_pos, natal_pos)
    orb_max = TRANSIT_ORBS.get(transit_planet, 2.0)
    for name, exact, symbol in ASPECTS:
        diff = abs(arc - exact)
        if diff <= orb_max:
            return {'name': name, 'exact_angle': exact,
                    'orb': round(diff, 2), 'symbol': symbol}
    return None


def determine_movement(transit_pos_now, transit_pos_tomorrow, natal_pos, exact_angle):
    """Applying (точность близится) или separating (расходится)."""
    arc_now = angular_distance(transit_pos_now, natal_pos)
    arc_tomorrow = angular_distance(transit_pos_tomorrow, natal_pos)
    err_now = abs(arc_now - exact_angle)
    err_tomorrow = abs(arc_tomorrow - exact_angle)
    return 'applying' if err_tomorrow < err_now else 'separating'


def estimate_exact_date(transit_planet, current_orb, movement, current_date):
    """Линейная экстраполяция даты точности (приблизительно)."""
    if movement != 'applying':
        return None
    daily = PLANET_DAILY_MOTION.get(transit_planet, 0.5)
    if daily <= 0:
        return None
    days = current_orb / daily
    if days > 365:
        return None
    exact = current_date + timedelta(days=int(round(days)))
    return exact.strftime('%Y-%m-%d')


def intensity_score(aspect_record):
    """Скоринг для сортировки топ-транзитов."""
    tp = aspect_record['transit_planet']
    np = aspect_record['natal_point']
    orb = aspect_record['orb']
    movement = aspect_record.get('movement', 'unknown')

    score = (PLANET_WEIGHT.get(tp, 3) * 2 +
             NATAL_POINT_WEIGHT.get(np, 5) * 2)
    # Чем точнее орб — тем выше score
    score += max(0, 5 - orb) * 2
    # Applying транзит весит больше
    if movement == 'applying':
        score += 3
    return score


def intensity_label(score):
    if score >= 35:
        return 'high'
    elif score >= 25:
        return 'medium'
    return 'low'


def position_to_dict(absolute_pos):
    """Из абсолютной долготы → знак + градус."""
    abs_pos = normalize_angle(absolute_pos)
    sign_idx = int(abs_pos // 30)
    deg_in_sign = abs_pos % 30
    return {
        'absolute': round(abs_pos, 4),
        'sign_idx': sign_idx,
        'sign_ru': SIGN_RU[sign_idx],
        'degrees': round(deg_in_sign, 2),
    }


# ─── РАСЧЁТ ──────────────────────────────────────────────────────────────

def load_natal(natal_path):
    with open(natal_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_transit_subject(year, month, day, hour, minute, lat, lon, tz_str):
    return AstrologicalSubject(
        'Transit', year, month, day, hour, minute,
        lng=lon, lat=lat, tz_str=tz_str,
        zodiac_type='Tropical', online=False
    )


def extract_transit_planets(subject):
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


def get_natal_points(natal_chart):
    """Извлекает все натальные точки (планеты + ASC/MC) с долготами.
    Натальный JSON использует поле 'abs_pos' (kerykeion convention)."""
    points = {}
    for key, data in natal_chart.get('planets', {}).items():
        abs_pos = data.get('abs_pos')
        if abs_pos is None:
            continue
        points[key] = {
            'absolute': abs_pos,
            'sign_ru': data.get('sign_ru', '?'),
            'degrees': data.get('degrees', 0),
            'house': data.get('house'),
            'name_ru': PLANET_RU.get(key, key),
            'symbol': PLANET_SYMBOLS.get(key, ''),
        }
    houses = natal_chart.get('houses', {})
    if houses:
        if '1' in houses:
            points['ascendant'] = {
                'absolute': houses['1'].get('abs_pos'),
                'sign_ru': houses['1'].get('sign_ru', '?'),
                'degrees': houses['1'].get('degrees', 0),
                'name_ru': 'Асцендент',
                'symbol': '↑',
            }
        if '10' in houses:
            points['mc'] = {
                'absolute': houses['10'].get('abs_pos'),
                'sign_ru': houses['10'].get('sign_ru', '?'),
                'degrees': houses['10'].get('degrees', 0),
                'name_ru': 'MC',
                'symbol': '⊕',
            }
    return points


def compute_transit_aspects(transit_planets, natal_points, tomorrow_planets, current_date):
    """Считает все аспекты транзит → натал, с движением и оценкой exact."""
    aspects = []
    for tp_key, tp_data in transit_planets.items():
        tp_pos = tp_data['absolute']
        for np_key, np_data in natal_points.items():
            np_pos = np_data.get('absolute')
            if np_pos is None:
                continue
            aspect = find_aspect(tp_pos, np_pos, tp_key)
            if aspect is None:
                continue

            # Движение
            tomorrow_pos = tomorrow_planets.get(tp_key, {}).get('absolute')
            if tomorrow_pos is not None:
                movement = determine_movement(tp_pos, tomorrow_pos, np_pos,
                                              aspect['exact_angle'])
            else:
                movement = 'unknown'

            exact_date = estimate_exact_date(
                tp_key, aspect['orb'], movement, current_date
            ) if movement == 'applying' else None

            record = {
                'transit_planet': tp_key,
                'transit_planet_ru': tp_data['name_ru'],
                'transit_symbol': tp_data['symbol'],
                'transit_sign_ru': tp_data['sign_ru'],
                'transit_degrees': tp_data['degrees'],
                'transit_retrograde': tp_data['retrograde'],
                'natal_point': np_key,
                'natal_point_ru': np_data['name_ru'],
                'natal_symbol': np_data['symbol'],
                'natal_sign_ru': np_data['sign_ru'],
                'natal_degrees': np_data['degrees'],
                'natal_house': np_data.get('house'),
                'aspect': aspect['name'],
                'aspect_ru': ASPECT_RU.get(aspect['name'], aspect['name']),
                'aspect_symbol': aspect['symbol'],
                'aspect_nature': ASPECT_NATURE.get(aspect['name'], 'neutral'),
                'orb': aspect['orb'],
                'movement': movement,
                'estimated_exact_date': exact_date,
            }
            record['intensity_score'] = intensity_score(record)
            record['intensity'] = intensity_label(record['intensity_score'])
            record['key'] = f"{tp_key}_{aspect['name']}_{np_key}"
            aspects.append(record)
    return aspects


# ─── ОСНОВНОЙ ФЛОУ ────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description='Транзиты к натальной карте')
    p.add_argument('--natal', required=True, help='Путь к chart.json')
    p.add_argument('--date', help='Дата транзита ДД.ММ.ГГГГ (default: today)')
    p.add_argument('--time', default='12:00', help='Время транзита ЧЧ:ММ (default: 12:00)')
    p.add_argument('--lat', type=float, help='Широта (default: из натала)')
    p.add_argument('--lon', type=float, help='Долгота (default: из натала)')
    p.add_argument('--tz', help='Таймзона (default: из натала)')
    p.add_argument('--outdir', help='Папка вывода (default: ./transits-reports)')
    p.add_argument('--biwheel', action='store_true',
                   help='Дополнительно сгенерировать bi-wheel PNG (натал внутри + транзиты снаружи)')
    p.add_argument('--biwheel-orb', type=float, default=3.0,
                   help='Макс. орб для линий аспектов в bi-wheel (def 3.0°)')
    args = p.parse_args()

    # Натальная карта
    natal_path = Path(args.natal).expanduser()
    if not natal_path.exists():
        print(f"❌ Натальная карта не найдена: {natal_path}", file=sys.stderr)
        sys.exit(1)

    print(f"  📖 Загружаю натал: {natal_path.name}")
    natal = load_natal(natal_path)
    natal_meta = natal.get('meta', {})
    natal_name = natal_meta.get('name', 'Unknown')

    # Дата транзита
    if args.date:
        try:
            year, month, day = parse_date(args.date)
        except ValueError as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)
    else:
        today = datetime.now()
        year, month, day = today.year, today.month, today.day

    # Время транзита
    try:
        time_parsed = parse_time(args.time)
        if time_parsed is None:
            time_parsed = (12, 0)
        hour, minute = time_parsed
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)

    # Координаты — берём из натала по умолчанию
    lat = args.lat if args.lat is not None else natal_meta.get('lat')
    lon = args.lon if args.lon is not None else natal_meta.get('lon')
    tz_str = args.tz or natal_meta.get('tz', 'UTC')
    if lat is None or lon is None:
        print(f"❌ В натале нет координат, укажи --lat и --lon", file=sys.stderr)
        sys.exit(1)

    print(f"  🌍 {lat:.4f}, {lon:.4f} · {tz_str}")
    print(f"  📅 Транзит на {day:02d}.{month:02d}.{year} {hour:02d}:{minute:02d}")

    # Транзитные позиции на момент
    subject = build_transit_subject(year, month, day, hour, minute, lat, lon, tz_str)
    transit_planets = extract_transit_planets(subject)

    # Транзит +1 сутки — для определения applying/separating
    tomorrow_dt = datetime(year, month, day) + timedelta(days=1)
    tomorrow_subject = build_transit_subject(
        tomorrow_dt.year, tomorrow_dt.month, tomorrow_dt.day,
        hour, minute, lat, lon, tz_str
    )
    tomorrow_planets = extract_transit_planets(tomorrow_subject)

    # Натальные точки
    natal_points = get_natal_points(natal)

    # Аспекты
    current_date = datetime(year, month, day)
    all_aspects = compute_transit_aspects(
        transit_planets, natal_points, tomorrow_planets, current_date
    )

    # Топ — по intensity_score
    sorted_aspects = sorted(all_aspects, key=lambda x: -x['intensity_score'])
    active_top = sorted_aspects[:10]

    # Ближайшие точности (отсортированы по дате)
    upcoming = sorted(
        [a for a in all_aspects
         if a.get('estimated_exact_date') and a['movement'] == 'applying'],
        key=lambda x: x['estimated_exact_date']
    )[:15]

    # Ретроградные сейчас
    retrograde_now = [
        {'planet': k, 'name_ru': v['name_ru'], 'symbol': v['symbol'],
         'sign_ru': v['sign_ru'], 'degrees': v['degrees']}
        for k, v in transit_planets.items() if v['retrograde']
    ]

    # Финальный JSON
    transit_json = {
        'meta': {
            'natal_name': natal_name,
            'natal_date': natal_meta.get('date'),
            'natal_city': natal_meta.get('city'),
            'natal_system': natal_meta.get('system', 'western'),
            'transit_date': f"{year:04d}-{month:02d}-{day:02d}",
            'transit_time': f"{hour:02d}:{minute:02d}",
            'transit_lat': lat,
            'transit_lon': lon,
            'transit_tz': tz_str,
            'computed_at': datetime.now().isoformat(timespec='seconds'),
        },
        'transit_planets': transit_planets,
        'all_aspects': all_aspects,
        'active_transits_top': active_top,
        'upcoming_exactness': upcoming,
        'retrograde_now': retrograde_now,
        'totals': {
            'total_aspects': len(all_aspects),
            'high_intensity': sum(1 for a in all_aspects if a['intensity'] == 'high'),
            'medium_intensity': sum(1 for a in all_aspects if a['intensity'] == 'medium'),
            'low_intensity': sum(1 for a in all_aspects if a['intensity'] == 'low'),
        },
    }

    # Папка вывода
    name_slug = slugify(natal_name)
    date_iso = f"{year:04d}-{month:02d}-{day:02d}"
    if args.outdir:
        outdir = Path(args.outdir)
    else:
        outdir = Path('./transits-reports') / f"{name_slug}_{date_iso}"
    outdir.mkdir(parents=True, exist_ok=True)

    json_path = outdir / f"transits_{name_slug}_{date_iso}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(transit_json, f, ensure_ascii=False, indent=2)

    print(f"  📊 JSON: {json_path}")

    # ── Bi-wheel PNG (опционально) ────────────────────────────────────────
    biwheel_path = None
    if args.biwheel:
        try:
            from render_biwheel import render_biwheel
            biwheel_path = outdir / f"biwheel_{name_slug}_{date_iso}.png"
            print(f"  🎨 Рисую bi-wheel...")
            render_biwheel(natal, transit_json, str(biwheel_path),
                           max_aspect_orb=args.biwheel_orb)
            print(f"  🖼  Bi-wheel: {biwheel_path}")
            transit_json['biwheel_png'] = str(biwheel_path)
            # перезаписываем JSON с обновлённым полем biwheel_png
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(transit_json, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ⚠️  Bi-wheel не создан: {e}")

    print(f"\n  ┌── ТРАНЗИТЫ {natal_name} на {date_iso} ──")
    print(f"  │  Всего аспектов: {transit_json['totals']['total_aspects']}")
    print(f"  │  Высокая интенсивность: {transit_json['totals']['high_intensity']}")
    print(f"  │  Ретроград: {', '.join(r['name_ru'] for r in retrograde_now) or 'нет'}")
    if active_top:
        a = active_top[0]
        print(f"  │  Топ-1: {a['transit_symbol']} {a['transit_planet_ru']} "
              f"{a['aspect_symbol']} {a['natal_point_ru']} "
              f"(орб {a['orb']}°, {a['movement']})")
    print(f"  └── ✅ Данные готовы. Следующий шаг: render_transits_docx.py")
    return str(json_path)


if __name__ == '__main__':
    main()
