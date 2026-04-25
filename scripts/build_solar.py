#!/usr/bin/env python3.11
"""
astro-natal-merkaba: build_solar.py
Соляр (Solar Return) — карта на точный момент возврата Солнца к натальной
позиции в указанном году. Используется как прогноз на год от ДР до ДР.

Особенности:
- Точный момент находится бинарным поиском (точность ~1 минуты)
- Город пребывания в день ДР этого года влияет на дома соляра
- Ключевые элементы: ASC соляра, MC соляра, дом куда падает Солнце,
  угловые планеты (в 1/4/7/10 домах) — главная тема года

Использование:
  python3.11 build_solar.py \\
    --natal ~/.astro-natal-merkaba/cache/dmitriy_1993-08-13_moskva_western.json \\
    --year 2026 \\
    --city "Москва" \\
    --outdir /tmp/astro-solar-dima
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

try:
    from geopy.geocoders import Nominatim
    from timezonefinder import TimezoneFinder
    GEOCODING_AVAILABLE = True
except ImportError:
    GEOCODING_AVAILABLE = False

from build_transits import (
    PLANET_RU, PLANET_SYMBOLS, SIGN_RU, SIGN_EN_TO_IDX,
    ASPECTS, ASPECT_RU, ASPECT_NATURE,
    angular_distance, normalize_angle, find_aspect,
)


def geocode_city(city):
    if not GEOCODING_AVAILABLE:
        raise RuntimeError("geopy/timezonefinder не установлены")
    geolocator = Nominatim(user_agent="astro-natal-merkaba")
    loc = geolocator.geocode(city, language='en', timeout=10)
    if not loc:
        raise ValueError(f"Город не найден: {city}")
    tf = TimezoneFinder()
    tz_str = tf.timezone_at(lat=loc.latitude, lng=loc.longitude)
    return loc.latitude, loc.longitude, tz_str


def sun_pos_at(dt, lat, lon, tz_str):
    """Долгота транзитного Солнца в момент dt."""
    subj = AstrologicalSubject(
        'SR_search', dt.year, dt.month, dt.day, dt.hour, dt.minute,
        lng=lon, lat=lat, tz_str=tz_str,
        zodiac_type='Tropical', online=False
    )
    return subj.sun.abs_pos


def find_solar_return_moment(natal_sun_abs, year, birth_month, birth_day, lat, lon, tz_str):
    """
    Бинарный поиск точного момента когда транзитное Солнце = натальному Солнцу.
    Возвращает datetime с точностью до минуты.
    """
    target = datetime(year, birth_month, birth_day, 12, 0)
    low = target - timedelta(days=3)
    high = target + timedelta(days=3)

    # Проверка направления: за день до — Солнце "позади" натала, за день после — "впереди"
    # Нормализуем разницу в [-180, 180]
    def signed_diff(pos):
        d = (pos - natal_sun_abs + 180) % 360 - 180
        return d

    for _ in range(40):  # ~40 итераций даёт точность << 1 секунда
        mid = low + (high - low) / 2
        pos = sun_pos_at(mid, lat, lon, tz_str)
        diff = signed_diff(pos)
        if abs(diff) < 0.0001:  # ~0.36 arcsec
            break
        if diff < 0:
            low = mid
        else:
            high = mid
        # Останавливаемся если окно меньше минуты
        if (high - low).total_seconds() < 60:
            break
    return mid


def extract_planets(subject):
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
        house = None
        for h_attr in ['house', 'house_pos']:
            if hasattr(obj, h_attr):
                house = getattr(obj, h_attr)
                if house and isinstance(house, str) and 'House' in house:
                    try:
                        house = int(house.replace('First', '1').replace('Second', '2')
                                    .replace('Third', '3').replace('Fourth', '4')
                                    .replace('Fifth', '5').replace('Sixth', '6')
                                    .replace('Seventh', '7').replace('Eighth', '8')
                                    .replace('Ninth', '9').replace('Tenth', '10')
                                    .replace('Eleventh', '11').replace('Twelfth', '12')
                                    .replace('_House', '').replace('House', '').strip())
                    except ValueError:
                        house = None
                break
        planets[key] = {
            'absolute': round(obj.abs_pos, 4),
            'sign_idx': sign_idx,
            'sign_ru': SIGN_RU[sign_idx],
            'degrees': round(obj.position, 2),
            'house': house,
            'retrograde': bool(getattr(obj, 'retrograde', False)),
            'symbol': PLANET_SYMBOLS.get(key, ''),
            'name_ru': PLANET_RU.get(key, key),
        }
    return planets


def extract_houses(subject):
    """Куспиды 12 домов соляра."""
    houses = {}
    house_attrs = [
        ('1', 'first_house'), ('2', 'second_house'), ('3', 'third_house'),
        ('4', 'fourth_house'), ('5', 'fifth_house'), ('6', 'sixth_house'),
        ('7', 'seventh_house'), ('8', 'eighth_house'), ('9', 'ninth_house'),
        ('10', 'tenth_house'), ('11', 'eleventh_house'), ('12', 'twelfth_house'),
    ]
    for num, attr in house_attrs:
        h = getattr(subject, attr, None)
        if h is None:
            continue
        sign_idx = SIGN_EN_TO_IDX.get(h.sign, 0)
        houses[num] = {
            'absolute': round(h.abs_pos, 4),
            'sign_ru': SIGN_RU[sign_idx],
            'degrees': round(h.position, 2),
        }
    return houses


def find_house_for_position(position, houses):
    """Какой дом содержит указанную долготу."""
    if not houses:
        return None
    pos = normalize_angle(position)
    cusps = []
    for i in range(1, 13):
        h = houses.get(str(i))
        if h:
            cusps.append((i, h['absolute']))
    if len(cusps) < 12:
        return None
    cusps.sort(key=lambda x: x[1])
    for i, (h_num, cusp) in enumerate(cusps):
        next_cusp = cusps[(i + 1) % 12][1]
        if next_cusp < cusp:  # wrap-around
            if pos >= cusp or pos < next_cusp:
                return h_num
        else:
            if cusp <= pos < next_cusp:
                return h_num
    return None


def angular_planets(planets):
    """Планеты в угловых домах (1/4/7/10) — самые сильные в соляре."""
    result = []
    for k, p in planets.items():
        if p.get('house') in (1, 4, 7, 10):
            result.append({
                'planet': k,
                'name_ru': p['name_ru'],
                'symbol': p['symbol'],
                'sign_ru': p['sign_ru'],
                'degrees': p['degrees'],
                'house': p['house'],
                'retrograde': p['retrograde'],
            })
    return result


def compute_solar_aspects(planets):
    """Аспекты внутри соляра между планетами."""
    aspects = []
    keys = list(planets.keys())
    for i, k1 in enumerate(keys):
        for k2 in keys[i+1:]:
            p1 = planets[k1]
            p2 = planets[k2]
            arc = angular_distance(p1['absolute'], p2['absolute'])
            for name, exact, symbol in ASPECTS:
                diff = abs(arc - exact)
                if diff <= 5.0:  # стандартный соляр-орб
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
    p = argparse.ArgumentParser(description='Соляр (Solar Return)')
    p.add_argument('--natal', required=True)
    p.add_argument('--year', type=int, help='Год соляра (default: текущий)')
    p.add_argument('--city', help='Город пребывания в ДР этого года (default: натальный)')
    p.add_argument('--lat', type=float)
    p.add_argument('--lon', type=float)
    p.add_argument('--tz')
    p.add_argument('--outdir')
    args = p.parse_args()

    natal_path = Path(args.natal).expanduser()
    if not natal_path.exists():
        print(f"❌ Натал не найден: {natal_path}", file=sys.stderr)
        sys.exit(1)

    print(f"  📖 Натал: {natal_path.name}")
    with open(natal_path, 'r', encoding='utf-8') as f:
        natal = json.load(f)
    meta = natal.get('meta', {})
    name = meta.get('name', 'Unknown')

    natal_sun = natal.get('planets', {}).get('sun', {})
    natal_sun_abs = natal_sun.get('abs_pos')
    if natal_sun_abs is None:
        print(f"❌ Нет позиции натального Солнца в JSON", file=sys.stderr)
        sys.exit(1)

    natal_date = datetime.fromisoformat(meta['date'])

    # Год
    year = args.year if args.year is not None else datetime.now().year
    # Если возраст ещё не наступил в этом году — берём прошлый соляр
    today = datetime.now()
    if year == today.year:
        bday_this_year = datetime(year, natal_date.month, natal_date.day)
        if bday_this_year > today:
            year -= 1
            print(f"  ℹ️  ДР {year+1} ещё не наступил — использую соляр {year}")

    # Город
    if args.lat is not None and args.lon is not None:
        lat, lon, tz_str = args.lat, args.lon, args.tz or 'UTC'
        city_name = args.city or 'указанные координаты'
    elif args.city:
        print(f"  🌍 Геокодирую: {args.city}")
        lat, lon, tz_str = geocode_city(args.city)
        city_name = args.city
        print(f"     {lat:.4f}, {lon:.4f}, {tz_str}")
    else:
        # Натальный город по умолчанию
        lat = meta.get('lat')
        lon = meta.get('lon')
        tz_str = meta.get('tz', 'UTC')
        city_name = meta.get('city', 'натальный')
        print(f"  🌍 Город по умолчанию (натальный): {city_name}")

    if lat is None or lon is None:
        print(f"❌ Нет координат — укажи --city или --lat/--lon", file=sys.stderr)
        sys.exit(1)

    # Найти точный момент возврата
    print(f"  🔍 Ищу точный момент возврата Солнца в {year}...")
    sr_dt = find_solar_return_moment(
        natal_sun_abs, year, natal_date.month, natal_date.day, lat, lon, tz_str
    )
    print(f"  ☉ Соляр: {sr_dt.strftime('%d.%m.%Y %H:%M:%S')} в {city_name}")

    # Построить карту соляра
    sr_subject = AstrologicalSubject(
        f'{name}_solar_{year}',
        sr_dt.year, sr_dt.month, sr_dt.day, sr_dt.hour, sr_dt.minute,
        lng=lon, lat=lat, tz_str=tz_str,
        zodiac_type='Tropical', online=False
    )
    planets = extract_planets(sr_subject)
    houses = extract_houses(sr_subject)

    # Дома планет, если kerykeion не дал
    for k, p in planets.items():
        if p.get('house') is None:
            p['house'] = find_house_for_position(p['absolute'], houses)

    # Угловые планеты + аспекты соляра
    angular = angular_planets(planets)
    aspects = compute_solar_aspects(planets)

    # ASC и MC
    asc = houses.get('1', {})
    mc = houses.get('10', {})

    solar_json = {
        'meta': {
            'natal_name': name,
            'natal_date': meta.get('date'),
            'natal_sun_position': f"{natal_sun.get('sign_ru', '?')} {natal_sun.get('degrees', '?')}°",
            'solar_year': year,
            'solar_moment_iso': sr_dt.isoformat(),
            'solar_moment_human': sr_dt.strftime('%d.%m.%Y %H:%M'),
            'solar_city': city_name,
            'solar_lat': lat,
            'solar_lon': lon,
            'solar_tz': tz_str,
            'computed_at': datetime.now().isoformat(timespec='seconds'),
        },
        'solar_planets': planets,
        'solar_houses': houses,
        'solar_ascendant': {
            'sign_ru': asc.get('sign_ru', '?'),
            'degrees': asc.get('degrees', 0),
            'absolute': asc.get('absolute'),
        },
        'solar_mc': {
            'sign_ru': mc.get('sign_ru', '?'),
            'degrees': mc.get('degrees', 0),
            'absolute': mc.get('absolute'),
        },
        'sun_in_house': planets.get('sun', {}).get('house'),
        'angular_planets': angular,
        'aspects': aspects[:15],
        'totals': {
            'angular_count': len(angular),
            'aspects_total': len(aspects),
        },
    }

    name_slug = slugify(name)
    if args.outdir:
        outdir = Path(args.outdir)
    else:
        outdir = Path('./solar-reports') / f"{name_slug}_{year}"
    outdir.mkdir(parents=True, exist_ok=True)

    json_path = outdir / f"solar_{name_slug}_{year}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(solar_json, f, ensure_ascii=False, indent=2)
    print(f"  📊 JSON: {json_path}")

    print(f"\n  ┌── СОЛЯР {name} {year} ──")
    print(f"  │  Точка возврата: {sr_dt.strftime('%d.%m.%Y %H:%M')}")
    print(f"  │  Город:           {city_name}")
    print(f"  │  ASC соляра:      {asc.get('sign_ru', '?')} {asc.get('degrees', '?')}°")
    print(f"  │  MC соляра:       {mc.get('sign_ru', '?')} {mc.get('degrees', '?')}°")
    sun_h = planets.get('sun', {}).get('house')
    print(f"  │  Солнце в доме:  {sun_h} (главная тема года)")
    if angular:
        print(f"  │  Угловые планеты ({len(angular)}):")
        for a in angular:
            print(f"  │    {a['symbol']} {a['name_ru']} в доме {a['house']} ({a['sign_ru']} {a['degrees']}°)")
    print(f"  │  Аспектов: {len(aspects)}")
    print(f"  └── ✅ Готово. Следующий шаг: render_solar_docx.py")
    return str(json_path)


if __name__ == '__main__':
    main()
