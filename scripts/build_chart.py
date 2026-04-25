#!/usr/bin/env python3.11
"""
astro-natal-merkaba: build_chart.py
Рассчитывает натальную астрологическую карту (западная + ведическая).
Выход: JSON с данными карты + PNG колесо.

Использование:
  python3.11 build_chart.py --date 8.11.1994 --time 14:30 --city "Харьков" --name Дарья --system western
  python3.11 build_chart.py --date 8.11.1994 --city "Москва" --name Иван --system vedic
  python3.11 build_chart.py --date 8.11.1994 --lat 55.75 --lon 37.62 --tz Europe/Moscow --name Анна
"""
import argparse
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from itertools import combinations

# Local helpers (slug, cache, parsers) — добавляем cwd в sys.path
sys.path.insert(0, str(Path(__file__).parent))
from astro_helpers import cache_save

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

try:
    from geopy.geocoders import Nominatim
    from timezonefinder import TimezoneFinder
    GEOCODING_AVAILABLE = True
except ImportError:
    GEOCODING_AVAILABLE = False

try:
    from kerykeion import AstrologicalSubject, NatalAspects
    KERYKEION_AVAILABLE = True
except ImportError:
    KERYKEION_AVAILABLE = False

# ─── КОНСТАНТЫ ───────────────────────────────────────────────────────────────

PLANET_KEYS = [
    'sun', 'moon', 'mercury', 'venus', 'mars',
    'jupiter', 'saturn', 'uranus', 'neptune', 'pluto',
    'true_north_lunar_node', 'chiron', 'mean_lilith',
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

PLANET_COLORS = {
    'sun': '#FFD700', 'moon': '#E8E8E8', 'mercury': '#90EE90',
    'venus': '#FFB6C1', 'mars': '#FF4500', 'jupiter': '#FFA500',
    'saturn': '#A0937D', 'uranus': '#40E0D0', 'neptune': '#6495ED',
    'pluto': '#9370DB', 'true_north_lunar_node': '#FFFFFF',
    'chiron': '#FF69B4', 'mean_lilith': '#CC88FF',
}

SIGN_EN = ['Ari','Tau','Gem','Can','Leo','Vir','Lib','Sco','Sag','Cap','Aqu','Pis']
SIGN_RU = ['Овен','Телец','Близнецы','Рак','Лев','Дева',
           'Весы','Скорпион','Стрелец','Козерог','Водолей','Рыбы']
SIGN_SYMBOLS = ['♈','♉','♊','♋','♌','♍','♎','♏','♐','♑','♒','♓']

SIGN_FULL_EN = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
                'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']

EN_TO_IDX = {s: i for i, s in enumerate(SIGN_FULL_EN)}
# kerykeion возвращает короткие коды ('Ari', 'Sco', ...) в obj.sign — мапим их тоже
EN_TO_IDX.update({s: i for i, s in enumerate(SIGN_EN)})

ELEMENT_SIGNS = {
    'fire':  [0, 4, 8],
    'earth': [1, 5, 9],
    'air':   [2, 6, 10],
    'water': [3, 7, 11],
}
SIGN_ELEMENT = ['fire','earth','air','water','fire','earth',
                'air','water','fire','earth','air','water']
SIGN_MODALITY = ['cardinal','fixed','mutable','cardinal','fixed','mutable',
                 'cardinal','fixed','mutable','cardinal','fixed','mutable']

ELEMENT_COLORS = {
    'fire': '#C0392B', 'earth': '#27AE60',
    'air': '#F39C12', 'water': '#2980B9',
}
ELEMENT_RU = {'fire':'Огонь','earth':'Земля','air':'Воздух','water':'Вода'}
MODALITY_RU = {'cardinal':'Кардинальные','fixed':'Фиксированные','mutable':'Мутабельные'}

ASPECT_RU = {
    'conjunction':  'Конъюнкция',  'opposition': 'Оппозиция',
    'trine':        'Трин',         'square':     'Квадратура',
    'sextile':      'Секстиль',     'quincunx':   'Квинкункс',
    'semisextile':  'Полусекстиль', 'semisquare': 'Полуквадрат',
    'sesquisquare': 'Сескиквадрат', 'quintile':   'Квинтиль',
    'biquintile':   'Биквинтиль',
}
ASPECT_COLORS = {
    'conjunction': '#FFFFFF', 'opposition': '#E67E22',
    'trine': '#27AE60', 'square': '#E74C3C',
    'sextile': '#3498DB', 'quincunx': '#9B59B6',
}
MAJOR_ASPECTS = {'conjunction', 'opposition', 'trine', 'square', 'sextile', 'quincunx'}

HOUSE_KEYS = ['first','second','third','fourth','fifth','sixth',
              'seventh','eighth','ninth','tenth','eleventh','twelfth']

# 27 Накшатр (для ведической астрологии)
NAKSHATRAS = [
    {'name_en':'Ashwini','name_ru':'Ашвини','start':0,'end':13.333,'ruler':'Кету','quality':'теджас (огонь)'},
    {'name_en':'Bharani','name_ru':'Бхарани','start':13.333,'end':26.666,'ruler':'Венера','quality':'тамас'},
    {'name_en':'Krittika','name_ru':'Криттика','start':26.666,'end':40,'ruler':'Солнце','quality':'раджас'},
    {'name_en':'Rohini','name_ru':'Рохини','start':40,'end':53.333,'ruler':'Луна','quality':'тамас'},
    {'name_en':'Mrigashira','name_ru':'Мригашира','start':53.333,'end':66.666,'ruler':'Марс','quality':'тамас'},
    {'name_en':'Ardra','name_ru':'Ардра','start':66.666,'end':80,'ruler':'Раху','quality':'тамас'},
    {'name_en':'Punarvasu','name_ru':'Пунарвасу','start':80,'end':93.333,'ruler':'Юпитер','quality':'саттва'},
    {'name_en':'Pushya','name_ru':'Пушья','start':93.333,'end':106.666,'ruler':'Сатурн','quality':'тамас'},
    {'name_en':'Ashlesha','name_ru':'Ашлеша','start':106.666,'end':120,'ruler':'Меркурий','quality':'саттва'},
    {'name_en':'Magha','name_ru':'Магха','start':120,'end':133.333,'ruler':'Кету','quality':'тамас'},
    {'name_en':'Purva Phalguni','name_ru':'Пурва Пхалгуни','start':133.333,'end':146.666,'ruler':'Венера','quality':'тамас'},
    {'name_en':'Uttara Phalguni','name_ru':'Уттара Пхалгуни','start':146.666,'end':160,'ruler':'Солнце','quality':'саттва'},
    {'name_en':'Hasta','name_ru':'Хаста','start':160,'end':173.333,'ruler':'Луна','quality':'раджас'},
    {'name_en':'Chitra','name_ru':'Читра','start':173.333,'end':186.666,'ruler':'Марс','quality':'тамас'},
    {'name_en':'Swati','name_ru':'Свати','start':186.666,'end':200,'ruler':'Раху','quality':'тамас'},
    {'name_en':'Vishakha','name_ru':'Вишакха','start':200,'end':213.333,'ruler':'Юпитер','quality':'саттва'},
    {'name_en':'Anuradha','name_ru':'Анурадха','start':213.333,'end':226.666,'ruler':'Сатурн','quality':'тамас'},
    {'name_en':'Jyeshtha','name_ru':'Джьештха','start':226.666,'end':240,'ruler':'Меркурий','quality':'саттва'},
    {'name_en':'Mula','name_ru':'Мула','start':240,'end':253.333,'ruler':'Кету','quality':'тамас'},
    {'name_en':'Purva Ashadha','name_ru':'Пурва Ашадха','start':253.333,'end':266.666,'ruler':'Венера','quality':'раджас'},
    {'name_en':'Uttara Ashadha','name_ru':'Уттара Ашадха','start':266.666,'end':280,'ruler':'Солнце','quality':'саттва'},
    {'name_en':'Shravana','name_ru':'Шравана','start':280,'end':293.333,'ruler':'Луна','quality':'раджас'},
    {'name_en':'Dhanishtha','name_ru':'Дхаништха','start':293.333,'end':306.666,'ruler':'Марс','quality':'тамас'},
    {'name_en':'Shatabhisha','name_ru':'Шатабхиша','start':306.666,'end':320,'ruler':'Раху','quality':'тамас'},
    {'name_en':'Purva Bhadrapada','name_ru':'Пурва Бхадрапада','start':320,'end':333.333,'ruler':'Юпитер','quality':'тамас'},
    {'name_en':'Uttara Bhadrapada','name_ru':'Уттара Бхадрапада','start':333.333,'end':346.666,'ruler':'Сатурн','quality':'тамас'},
    {'name_en':'Revati','name_ru':'Ревати','start':346.666,'end':360,'ruler':'Меркурий','quality':'саттва'},
]

# ─── ГЕОКОДИРОВАНИЕ ───────────────────────────────────────────────────────────

def geocode_city(city_name: str):
    """city_name → (lat, lon, tz_str) или None"""
    if not GEOCODING_AVAILABLE:
        return None
    try:
        geo = Nominatim(user_agent='astro-natal-merkaba/1.0', timeout=5)
        loc = geo.geocode(city_name, language='ru')
        if not loc:
            return None
        tf = TimezoneFinder()
        tz = tf.timezone_at(lat=loc.latitude, lng=loc.longitude)
        return loc.latitude, loc.longitude, tz or 'UTC'
    except Exception:
        return None

# ─── РАСЧЁТ КАРТЫ ─────────────────────────────────────────────────────────────

def sign_idx(sign_en_full: str) -> int:
    return EN_TO_IDX.get(sign_en_full, 0)

def house_num(house_str: str) -> int:
    """'Tenth_House' → 10"""
    mapping = {
        'First_House': 1, 'Second_House': 2, 'Third_House': 3,
        'Fourth_House': 4, 'Fifth_House': 5, 'Sixth_House': 6,
        'Seventh_House': 7, 'Eighth_House': 8, 'Ninth_House': 9,
        'Tenth_House': 10, 'Eleventh_House': 11, 'Twelfth_House': 12,
    }
    return mapping.get(house_str, 0)

def get_nakshatra(sidereal_lon: float) -> dict:
    """Возвращает накшатру для сидерической долготы"""
    lon = sidereal_lon % 360
    for n in NAKSHATRAS:
        if n['start'] <= lon < n['end']:
            return n
    return NAKSHATRAS[-1]

def build_subject(date_str, time_str, lat, lon, tz_str, name, system):
    """Строит kerykeion AstrologicalSubject"""
    parts = date_str.replace('/', '.').split('.')
    if len(parts) == 3:
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
    else:
        raise ValueError(f"Неверный формат даты: {date_str}")

    has_time = bool(time_str)
    if time_str:
        tp = time_str.replace(':', '.').split('.')
        hour, minute = int(tp[0]), int(tp[1]) if len(tp) > 1 else 0
    else:
        hour, minute = 12, 0  # солнечная карта

    zodiac_type = 'Sidereal' if system == 'vedic' else 'Tropical'
    sidereal_mode = 'LAHIRI' if system == 'vedic' else None

    kwargs = dict(
        name=name, year=year, month=month, day=day,
        hour=hour, minute=minute,
        lng=lon, lat=lat, tz_str=tz_str or 'UTC',
        zodiac_type=zodiac_type,
        online=False,
    )
    if sidereal_mode:
        kwargs['sidereal_mode'] = sidereal_mode

    return AstrologicalSubject(**kwargs), has_time, (year, month, day, hour, minute)


def extract_planets(subject):
    """Извлекает данные всех планет → dict"""
    result = {}
    for key in PLANET_KEYS:
        obj = getattr(subject, key, None)
        if obj is None:
            continue
        s_idx = sign_idx(obj.sign)
        result[key] = {
            'key': key,
            'name_ru': PLANET_RU[key],
            'symbol': PLANET_SYMBOLS[key],
            'sign_en': obj.sign,
            'sign_ru': SIGN_RU[s_idx],
            'sign_symbol': SIGN_SYMBOLS[s_idx],
            'degrees': round(obj.position, 2),
            'abs_pos': round(obj.abs_pos, 2),
            'house': house_num(getattr(obj, 'house', 'First_House')),
            'retrograde': bool(obj.retrograde),
            'element': SIGN_ELEMENT[s_idx],
            'modality': SIGN_MODALITY[s_idx],
        }
    return result


def extract_houses(subject):
    """Извлекает куспиды домов → dict {1: {...}, 2: {...}, ...}"""
    result = {}
    for i, key in enumerate(HOUSE_KEYS, 1):
        obj = getattr(subject, f'{key}_house', None)
        if obj is None:
            continue
        s_idx = sign_idx(obj.sign)
        result[str(i)] = {
            'sign_en': obj.sign,
            'sign_ru': SIGN_RU[s_idx],
            'degrees': round(obj.position, 2),
            'abs_pos': round(obj.abs_pos, 2),
        }
    return result


def extract_aspects(subject):
    """Извлекает аспекты → list"""
    aspects_engine = NatalAspects(subject)
    result = []
    for a in aspects_engine.all_aspects:
        if a.aspect not in MAJOR_ASPECTS:
            continue
        result.append({
            'p1': a.p1_name.lower().replace(' ', '_'),
            'p1_name_ru': PLANET_RU.get(a.p1_name.lower().replace(' ', '_'), a.p1_name),
            'p2': a.p2_name.lower().replace(' ', '_'),
            'p2_name_ru': PLANET_RU.get(a.p2_name.lower().replace(' ', '_'), a.p2_name),
            'aspect': a.aspect,
            'aspect_ru': ASPECT_RU.get(a.aspect, a.aspect),
            'orb': round(a.orbit, 2),
            'movement': a.aspect_movement,
            'color': ASPECT_COLORS.get(a.aspect, '#888888'),
        })
    result.sort(key=lambda x: x['orb'])
    return result


def calc_distributions(planets):
    """Считает стихии, модальности, стеллиумы"""
    elem_count = {'fire': 0, 'earth': 0, 'air': 0, 'water': 0}
    mod_count = {'cardinal': 0, 'fixed': 0, 'mutable': 0}
    sign_count = {}
    core_planets = ['sun','moon','mercury','venus','mars','jupiter','saturn',
                    'uranus','neptune','pluto','true_north_lunar_node']
    for key in core_planets:
        p = planets.get(key)
        if not p:
            continue
        elem_count[p['element']] += 1
        mod_count[p['modality']] += 1
        s = p['sign_en']
        sign_count[s] = sign_count.get(s, []) + [PLANET_RU.get(key, key)]

    dominant_elem = max(elem_count, key=elem_count.get)
    dominant_mod = max(mod_count, key=mod_count.get)

    stelliums = []
    for sign, pnames in sign_count.items():
        if len(pnames) >= 3:
            s_idx = sign_idx(sign)
            stelliums.append(f"{SIGN_RU[s_idx]} ({', '.join(pnames)})")

    return elem_count, mod_count, dominant_elem, dominant_mod, stelliums


def build_chart_json(subject, planets, houses, aspects, has_time, date_tuple,
                     city, lat, lon, tz_str, name, system, ayanamsha=None):
    year, month, day, hour, minute = date_tuple
    date_iso = f"{year:04d}-{month:02d}-{day:02d}"
    time_str = f"{hour:02d}:{minute:02d}" if has_time else None

    elem_count, mod_count, dom_elem, dom_mod, stelliums = calc_distributions(planets)

    # Асцендент
    asc = None
    mc = None
    if has_time and '1' in houses:
        asc = houses['1']
    if has_time and '10' in houses:
        mc = houses['10']

    # Ведическая: накшатры
    vedic_extra = None
    if system == 'vedic':
        moon = planets.get('moon')
        asc_data = asc
        vedic_extra = {}
        if moon:
            nak = get_nakshatra(moon['abs_pos'])
            vedic_extra['moon_nakshatra'] = {
                'name_en': nak['name_en'], 'name_ru': nak['name_ru'],
                'ruler': nak['ruler'], 'quality': nak['quality'],
            }
        if asc_data:
            nak = get_nakshatra(asc_data['abs_pos'])
            vedic_extra['ascendant_nakshatra'] = {
                'name_en': nak['name_en'], 'name_ru': nak['name_ru'],
                'ruler': nak['ruler'], 'quality': nak['quality'],
            }
        if ayanamsha is not None:
            vedic_extra['ayanamsha'] = round(ayanamsha, 2)

    chart = {
        'meta': {
            'name': name,
            'date': date_iso,
            'time': time_str,
            'has_time': has_time,
            'city': city,
            'lat': round(lat, 4) if lat else None,
            'lon': round(lon, 4) if lon else None,
            'tz': tz_str,
            'system': system,
            'system_ru': 'Западная (Тропик)' if system == 'western' else 'Ведическая (Сидерик/Лахири)',
        },
        'planets': planets,
        'houses': houses if has_time else {},
        'ascendant': asc,
        'mc': mc,
        'aspects': aspects,
        'distributions': {
            'elements': elem_count,
            'modalities': mod_count,
            'dominant_element': dom_elem,
            'dominant_element_ru': ELEMENT_RU[dom_elem],
            'dominant_modality': dom_mod,
            'dominant_modality_ru': MODALITY_RU[dom_mod],
            'stelliums': stelliums,
        },
    }
    if vedic_extra:
        chart['vedic'] = vedic_extra
    return chart


# ─── ВИЗУАЛИЗАЦИЯ (КОЛЕСО) ───────────────────────────────────────────────────

def lon_to_angle(lon: float, asc_lon: float) -> float:
    """Эклиптическая долгота → угол matplotlib (градусы, CCW от East)"""
    return (180.0 + (lon - asc_lon)) % 360.0


def render_wheel(planets: dict, houses: dict, ascendant,
                 aspects: list, output_path: str, name: str,
                 system: str, date_str: str):
    """Рисует натальное колесо в matplotlib и сохраняет PNG"""
    fig, ax = plt.subplots(figsize=(10, 10), dpi=150)
    fig.patch.set_facecolor('#12122A')
    ax.set_facecolor('#12122A')
    ax.set_xlim(-1.18, 1.18)
    ax.set_ylim(-1.18, 1.18)
    ax.set_aspect('equal')
    ax.axis('off')

    # Опорная точка: долгота асцендента (если есть)
    asc_lon = ascendant['abs_pos'] if ascendant else 0.0

    R_OUT = 1.0    # внешний радиус
    R_ZOD = 0.86   # внутренняя граница знакового кольца
    R_HSE = 0.62   # внутренняя граница кольца домов (или граница планет)
    R_INR = 0.50   # внутренний круг для аспектов

    # ── Знаковое кольцо ─────────────────────────────────────────────────────
    for i in range(12):
        lon_start = i * 30.0
        lon_end = (i + 1) * 30.0
        t1 = lon_to_angle(lon_start, asc_lon)
        t2 = t1 + 30.0  # всегда +30° (CCW)
        color = ELEMENT_COLORS[SIGN_ELEMENT[i]]
        w = mpatches.Wedge((0, 0), R_OUT, t1, t2,
                           width=R_OUT - R_ZOD,
                           facecolor=color, alpha=0.35,
                           edgecolor='#AAAAAA', linewidth=0.4)
        ax.add_patch(w)
        # Символ знака в центре сектора
        t_mid_deg = t1 + 15.0
        t_mid = math.radians(t_mid_deg)
        r_sym = (R_ZOD + R_OUT) / 2
        ax.text(r_sym * math.cos(t_mid), r_sym * math.sin(t_mid),
                SIGN_SYMBOLS[i], ha='center', va='center',
                fontsize=9, color='white', fontweight='bold')

    # Граничные окружности знакового кольца
    for r in [R_OUT, R_ZOD]:
        circle = plt.Circle((0, 0), r, fill=False, color='#AAAAAA', linewidth=0.6)
        ax.add_patch(circle)

    # ── Кольцо домов / планет ───────────────────────────────────────────────
    circle_hse = plt.Circle((0, 0), R_HSE, fill=False, color='#666688', linewidth=0.5)
    ax.add_patch(circle_hse)
    circle_inr = plt.Circle((0, 0), R_INR, fill=False, color='#444466', linewidth=0.5)
    ax.add_patch(circle_inr)

    # Линии домов
    if houses:
        for num_str, house_data in houses.items():
            t = math.radians(lon_to_angle(house_data['abs_pos'], asc_lon))
            num = int(num_str)
            # ASC (1) и DSC (7) — жирные
            lw = 1.2 if num in (1, 7, 4, 10) else 0.5
            color = '#FFFFFF' if num in (1, 4, 7, 10) else '#555577'
            ax.plot([R_INR * math.cos(t), R_ZOD * math.cos(t)],
                    [R_INR * math.sin(t), R_ZOD * math.sin(t)],
                    color=color, linewidth=lw, zorder=3)
            # Номер дома
            r_num = (R_INR + R_HSE) / 2
            # Сдвигаем номер на 15° вперёд по дому
            t_mid = houses.get(str(num % 12 + 1), house_data)
            t_label_deg = (lon_to_angle(house_data['abs_pos'], asc_lon) + 12.0) % 360
            t_label = math.radians(t_label_deg)
            ax.text(r_num * math.cos(t_label), r_num * math.sin(t_label),
                    str(num), ha='center', va='center',
                    fontsize=5.5, color='#9999BB', fontweight='normal')

    # ASC / DSC / MC / IC метки
    if ascendant:
        for lbl, lon_val, clr in [
            ('ASC', ascendant['abs_pos'], '#FFD700'),
            ('DSC', (ascendant['abs_pos'] + 180) % 360, '#FFD700'),
        ]:
            t = math.radians(lon_to_angle(lon_val, asc_lon))
            ax.text(1.10 * math.cos(t), 1.10 * math.sin(t),
                    lbl, ha='center', va='center',
                    fontsize=6.5, color=clr, fontweight='bold')

    # ── Аспекты ─────────────────────────────────────────────────────────────
    # Вычисляем углы планет для линий
    planet_angles = {}
    for key, p in planets.items():
        planet_angles[key] = math.radians(lon_to_angle(p['abs_pos'], asc_lon))

    for asp in aspects:
        if asp['aspect'] not in MAJOR_ASPECTS:
            continue
        k1 = asp['p1'].replace(' ', '_').lower()
        k2 = asp['p2'].replace(' ', '_').lower()
        if k1 not in planet_angles or k2 not in planet_angles:
            continue
        t1 = planet_angles[k1]
        t2 = planet_angles[k2]
        r_inner = R_INR * 0.97
        color = asp.get('color', '#888888')
        alpha = max(0.15, 0.5 - asp['orb'] * 0.04)
        ax.plot([r_inner * math.cos(t1), r_inner * math.cos(t2)],
                [r_inner * math.sin(t1), r_inner * math.sin(t2)],
                color=color, linewidth=0.7, alpha=alpha, zorder=2)

    # ── Планеты ─────────────────────────────────────────────────────────────
    # Раскидываем близкие планеты по радиусу, чтоб не перекрывались
    R_PLANET_MID = (R_HSE + R_ZOD) / 2  # ≈ 0.74
    planet_items = sorted(planets.items(), key=lambda x: x[1]['abs_pos'])

    used_angles = {}  # для детектирования близких планет → смещаем по радиусу
    for key, p in planet_items:
        t_deg = lon_to_angle(p['abs_pos'], asc_lon)
        t_rad = math.radians(t_deg)
        color = PLANET_COLORS[key]
        symbol = PLANET_SYMBOLS[key]

        # Проверка близости к уже нарисованным
        r = R_PLANET_MID
        for prev_deg in used_angles:
            diff = abs((t_deg - prev_deg + 180) % 360 - 180)
            if diff < 5.0:
                r = R_HSE + (R_ZOD - R_HSE) * 0.75  # поднять к внешнему
                break
        used_angles[t_deg] = key

        x, y = r * math.cos(t_rad), r * math.sin(t_rad)
        # Кружок планеты
        dot = plt.Circle((x, y), 0.025, color=color, zorder=6)
        ax.add_patch(dot)
        # Символ
        offset = 0.05
        ax.text(x + offset * math.cos(t_rad + 0.4),
                y + offset * math.sin(t_rad + 0.4),
                symbol, fontsize=7.5, color=color,
                ha='center', va='center', zorder=7,
                fontfamily='DejaVu Sans')
        # Градусы
        deg_txt = f"{p['degrees']:.0f}°{'℞' if p['retrograde'] else ''}"
        ax.text(x + (offset + 0.04) * math.cos(t_rad - 0.3),
                y + (offset + 0.04) * math.sin(t_rad - 0.3),
                deg_txt, fontsize=4.5, color='#CCCCCC',
                ha='center', va='center', zorder=7)

    # ── Центральная инфо ──────────────────────────────────────────────────
    sys_label = 'Западная' if system == 'western' else 'Ведическая'
    ax.text(0, 0.14, name, ha='center', va='center',
            fontsize=11, color='#FFD700', fontweight='bold', zorder=8)
    ax.text(0, 0.02, date_str, ha='center', va='center',
            fontsize=7.5, color='#BBBBCC', zorder=8)
    ax.text(0, -0.08, sys_label, ha='center', va='center',
            fontsize=7, color='#9999CC', zorder=8)

    # Заголовок
    title = f"Натальная карта • {name}"
    ax.set_title(title, color='white', fontsize=12, pad=8, fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return output_path


# ─── ТОЧКА ВХОДА ─────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description='Астрологическая натальная карта')
    p.add_argument('--date', required=True, help='Дата рождения: ДД.ММ.ГГГГ')
    p.add_argument('--time', default='', help='Время рождения: ЧЧ:ММ (опционально)')
    p.add_argument('--city', default='', help='Город рождения (для геокода)')
    p.add_argument('--lat', type=float, default=None, help='Широта (если без геокода)')
    p.add_argument('--lon', type=float, default=None, help='Долгота (если без геокода)')
    p.add_argument('--tz', default=None, help='Таймзона (Europe/Moscow, UTC, ...)')
    p.add_argument('--name', default='Клиент', help='Имя')
    p.add_argument('--system', default='western', choices=['western','vedic'],
                   help='Система: western (тропик) или vedic (Лахири)')
    p.add_argument('--outdir', default='', help='Папка для вывода файлов')
    p.add_argument('--no-png', action='store_true', help='Не генерировать PNG')
    return p.parse_args()


def main():
    if not KERYKEION_AVAILABLE:
        print("ERROR: kerykeion не установлен. pip3.11 install kerykeion", file=sys.stderr)
        sys.exit(1)

    args = parse_args()

    # ── Геокодирование ────────────────────────────────────────────────────
    lat, lon, tz_str = args.lat, args.lon, args.tz
    city = args.city

    if city and (lat is None or lon is None):
        result = geocode_city(city)
        if result:
            lat, lon, tz_str_geo = result
            if not tz_str:
                tz_str = tz_str_geo
            print(f"  ✅ Геокод: {city} → {lat:.4f}, {lon:.4f}, tz={tz_str}")
        else:
            print(f"  ⚠️  Не удалось геокодировать '{city}'. Используем UTC.")
            lat, lon, tz_str = 0.0, 0.0, 'UTC'
    elif lat is None:
        lat, lon, tz_str = 0.0, 0.0, 'UTC'
        city = city or 'Не указан'

    tz_str = tz_str or 'UTC'

    # ── Расчёт ────────────────────────────────────────────────────────────
    try:
        subject, has_time, date_tuple = build_subject(
            args.date, args.time, lat, lon, tz_str,
            args.name, args.system
        )
    except Exception as e:
        print(f"ERROR при расчёте карты: {e}", file=sys.stderr)
        sys.exit(1)

    planets = extract_planets(subject)
    houses = extract_houses(subject) if has_time else {}
    aspects = extract_aspects(subject)

    # Асцендент / МС
    ascendant = houses.get('1') if has_time else None
    mc = houses.get('10') if has_time else None

    # Ведическая: аяnamsha
    ayanamsha = None
    if args.system == 'vedic':
        # Разность между тропическим и сидерическим Солнцем
        subj_tropic = AstrologicalSubject(
            args.name, date_tuple[0], date_tuple[1], date_tuple[2],
            date_tuple[3], date_tuple[4],
            lng=lon, lat=lat, tz_str=tz_str,
            zodiac_type='Tropical', online=False
        )
        tropic_sun = subj_tropic.sun.abs_pos
        vedic_sun = subject.sun.abs_pos
        ayanamsha = (tropic_sun - vedic_sun) % 360

    chart_json = build_chart_json(
        subject, planets, houses, aspects, has_time, date_tuple,
        city, lat, lon, tz_str, args.name, args.system, ayanamsha
    )

    # ── Папка вывода ──────────────────────────────────────────────────────
    year, month, day = date_tuple[:3]
    date_iso = f"{year:04d}-{month:02d}-{day:02d}"
    safe_name = args.name.replace(' ', '_')

    if args.outdir:
        outdir = Path(args.outdir)
    else:
        outdir = Path('./astrology-reports')
    outdir.mkdir(parents=True, exist_ok=True)

    json_path = outdir / f"{safe_name}_{date_iso}.json"
    png_path = outdir / f"{safe_name}_{date_iso}_wheel.png"

    # ── PNG колесо ────────────────────────────────────────────────────────
    if not args.no_png:
        print(f"  🎨 Рисую колесо карты...")
        try:
            render_wheel(
                planets, houses, ascendant, aspects,
                str(png_path), args.name, args.system,
                f"{day:02d}.{month:02d}.{year}"
            )
            chart_json['wheel_png'] = str(png_path)
            print(f"  🖼  PNG: {png_path}")
        except Exception as e:
            print(f"  ⚠️  PNG не создан: {e}")

    # ── JSON ──────────────────────────────────────────────────────────────
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(chart_json, f, ensure_ascii=False, indent=2)

    print(f"  📊 JSON: {json_path}")

    # ── Кэш для расширенных техник (транзиты, прогрессии, синастрия...) ──
    try:
        cache_file = cache_save(chart_json)
        print(f"  💾 Кэш: {cache_file}")
    except Exception as e:
        print(f"  ⚠️  Кэш не сохранён: {e}")

    # ── Краткая сводка ────────────────────────────────────────────────────
    print(f"\n  ┌── КАРТА {args.name} ({args.system.upper()}) ──")
    sun = planets.get('sun', {})
    moon = planets.get('moon', {})
    print(f"  │  ☉ Солнце:     {sun.get('sign_ru','?')} {sun.get('degrees','?')}°{' ♦д.'+str(sun.get('house','')) if has_time else ''}")
    print(f"  │  ☽ Луна:       {moon.get('sign_ru','?')} {moon.get('degrees','?')}°{' ♦д.'+str(moon.get('house','')) if has_time else ''}")
    if ascendant:
        print(f"  │  ↑ Асцендент:  {ascendant.get('sign_ru','?')} {ascendant.get('degrees','?')}°")
    else:
        print(f"  │  ↑ Асцендент:  (нет времени — только знаки планет)")
    dist = chart_json['distributions']
    print(f"  │  Стихия:       {dist['dominant_element_ru']} ({dist['elements']})")
    if dist['stelliums']:
        print(f"  │  Стеллиумы:    {'; '.join(dist['stelliums'])}")
    print(f"  └── {len(aspects)} мажорных аспектов")
    print(f"\n  ✅ Данные готовы. Следующий шаг: render_docx.py")
    return str(json_path)


if __name__ == '__main__':
    main()
