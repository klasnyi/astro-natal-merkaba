#!/usr/bin/env python3.11
"""
astro-natal-merkaba: render_biwheel.py
Bi-wheel PNG: натальная карта в центре + транзиты по внешнему кольцу.
Между ними — линии активных аспектов транзит → натал.

Вход:
  --natal     <path>  chart.json от build_chart.py (или из кэша)
  --transits  <path>  transits.json от build_transits.py
  --out       <path>  путь к PNG
  [--orb-max FLOAT]   максимальный орб для отображаемых аспектов (def 3.0°)

Структура колец (от центра наружу):
  0.00 - 0.40  пустой центр + текст (имя, даты)
  0.40 - 0.42  внутренний бордер
  0.42 - 0.55  кольцо линий аспектов натал↔натал
  0.55 - 0.62  натальные дома + их номера
  0.62 - 0.72  натальные планеты (символы + градусы)
  0.72 - 0.74  средний бордер (между натал и транзит)
  0.74 - 0.84  транзитные планеты
  0.84 - 0.92  кольцо линий аспектов транзит↔натал
  0.92 - 1.00  знаковое кольцо (12 секторов с цветами стихий)
"""
import argparse
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Переиспользуем символы и цвета из build_chart
from build_chart import (
    PLANET_SYMBOLS, PLANET_COLORS, PLANET_RU,
    SIGN_SYMBOLS, SIGN_ELEMENT, ELEMENT_COLORS, SIGN_RU,
    ASPECT_COLORS, MAJOR_ASPECTS,
)


# ─── СТИЛЬ (палитра МерКаБа на тёмном фоне) ──────────────────────────────────

BG_COLOR = '#1A1A2E'           # глубокий тёмно-синий фон
RING_BORDER = '#7F8C8D'        # серый-muted (палитра МерКаБа)
HOUSE_LINE = '#5D6D7E'         # тёмный grey-blue для линий домов
ANGULAR_LINE = '#D4A017'       # золото для ASC/MC/IC/DSC
TEXT_LIGHT = '#ECF0F1'         # светлый для подписей на тёмном
TEXT_GOLD = '#D4A017'          # золото — имя и даты
TEXT_MUTED = '#95A5A6'         # muted

# Радиусы колец
R_CENTER_TEXT = 0.40
R_NATAL_ASPECTS = 0.42         # внешний край внутр. круга (где аспекты натала)
R_HOUSE_INNER = 0.55           # внутренний край кольца домов
R_HOUSE_OUTER = 0.62           # внешний край кольца домов
R_NATAL_PLANETS = 0.67         # центр натальных планет (0.62-0.72)
R_NATAL_PLANETS_OUT = 0.72
R_MID_BORDER = 0.74            # разделитель натал/транзит
R_TRANSIT_PLANETS = 0.79       # центр транзитных планет (0.74-0.84)
R_TRANSIT_PLANETS_OUT = 0.84
R_TRANSIT_ASPECTS = 0.84       # старт аспектов транзит-натал
R_ZODIAC_INNER = 0.92          # внутр. край знакового кольца
R_OUT = 1.00                   # внешний край


def lon_to_angle(lon: float, asc_lon: float) -> float:
    """Эклиптическая долгота → угол matplotlib (CCW от East = 0°).
    Натальный ASC помещаем на 180° (восточный горизонт = слева)."""
    return (180.0 + (lon - asc_lon)) % 360.0


def draw_zodiac_ring(ax, asc_lon):
    """Внешнее кольцо знаков зодиака, окрашенное по стихии."""
    for i in range(12):
        lon_start = i * 30.0
        t1 = lon_to_angle(lon_start, asc_lon)
        t2 = t1 + 30.0
        color = ELEMENT_COLORS[SIGN_ELEMENT[i]]
        wedge = mpatches.Wedge(
            (0, 0), R_OUT, t1, t2,
            width=R_OUT - R_ZODIAC_INNER,
            facecolor=color, alpha=0.40,
            edgecolor=RING_BORDER, linewidth=0.5,
        )
        ax.add_patch(wedge)
        # Символ знака посередине сектора
        t_mid = math.radians(t1 + 15.0)
        r_sym = (R_ZODIAC_INNER + R_OUT) / 2
        ax.text(r_sym * math.cos(t_mid), r_sym * math.sin(t_mid),
                SIGN_SYMBOLS[i], ha='center', va='center',
                fontsize=11, color=TEXT_LIGHT, fontweight='bold', zorder=5)


def draw_borders(ax):
    """Концентрические окружности — границы колец."""
    for r, lw, alpha in [
        (R_OUT, 0.8, 1.0),
        (R_ZODIAC_INNER, 0.6, 0.8),
        (R_MID_BORDER, 0.7, 0.9),
        (R_HOUSE_OUTER, 0.5, 0.7),
        (R_HOUSE_INNER, 0.5, 0.7),
        (R_NATAL_ASPECTS, 0.5, 0.6),
    ]:
        circle = plt.Circle((0, 0), r, fill=False,
                            color=RING_BORDER, linewidth=lw, alpha=alpha, zorder=1)
        ax.add_patch(circle)


def draw_houses(ax, houses, asc_lon):
    """Линии домов между R_HOUSE_INNER и R_HOUSE_OUTER (с продлением до натальных планет)."""
    if not houses:
        return
    for num_str, hd in houses.items():
        num = int(num_str)
        cusp_lon = hd['abs_pos']
        t = math.radians(lon_to_angle(cusp_lon, asc_lon))
        is_angular = num in (1, 4, 7, 10)
        color = ANGULAR_LINE if is_angular else HOUSE_LINE
        lw = 1.4 if is_angular else 0.6
        # Продлеваем линии угловых домов до центра, остальные — только в кольце планет
        r_inner = R_NATAL_ASPECTS if is_angular else R_HOUSE_INNER
        r_outer = R_NATAL_PLANETS_OUT
        ax.plot(
            [r_inner * math.cos(t), r_outer * math.cos(t)],
            [r_inner * math.sin(t), r_outer * math.sin(t)],
            color=color, linewidth=lw, zorder=2, alpha=0.85,
        )
        # Номер дома — в середине дома, в кольце R_HOUSE_INNER..R_HOUSE_OUTER
        next_str = str((num % 12) + 1)
        next_cusp = houses.get(next_str)
        if next_cusp:
            mid_lon = (cusp_lon + ((next_cusp['abs_pos'] - cusp_lon) % 360) / 2) % 360
            t_mid = math.radians(lon_to_angle(mid_lon, asc_lon))
            r_lab = (R_HOUSE_INNER + R_HOUSE_OUTER) / 2
            ax.text(r_lab * math.cos(t_mid), r_lab * math.sin(t_mid),
                    str(num), ha='center', va='center',
                    fontsize=7, color=TEXT_MUTED, zorder=3)

    # ASC/DSC/MC/IC лейблы у внешнего края
    if '1' in houses:
        for lbl, lon_val in [
            ('ASC', houses['1']['abs_pos']),
            ('DSC', (houses['1']['abs_pos'] + 180) % 360),
        ]:
            t = math.radians(lon_to_angle(lon_val, asc_lon))
            ax.text(1.06 * math.cos(t), 1.06 * math.sin(t),
                    lbl, ha='center', va='center',
                    fontsize=7, color=ANGULAR_LINE, fontweight='bold', zorder=8)
    if '10' in houses:
        for lbl, lon_val in [
            ('MC', houses['10']['abs_pos']),
            ('IC', (houses['10']['abs_pos'] + 180) % 360),
        ]:
            t = math.radians(lon_to_angle(lon_val, asc_lon))
            ax.text(1.06 * math.cos(t), 1.06 * math.sin(t),
                    lbl, ha='center', va='center',
                    fontsize=7, color=ANGULAR_LINE, fontweight='bold', zorder=8)


def _spread_planets(planet_items, asc_lon, min_sep_deg=6.0):
    """Раскидываем близкие планеты по углу: при перекрытии < min_sep_deg смещаем последующую.
    Возвращает list of (key, abs_pos, angle_deg, retrograde, offset_layer)."""
    sorted_items = sorted(planet_items, key=lambda x: x[1].get('abs_pos', x[1].get('absolute', 0)))
    result = []
    last_angle = None
    layer = 0
    for key, data in sorted_items:
        abs_pos = data.get('abs_pos', data.get('absolute'))
        if abs_pos is None:
            continue
        angle_deg = lon_to_angle(abs_pos, asc_lon)
        retro = bool(data.get('retrograde', False))
        # Проверка близости к последней
        if last_angle is not None:
            diff = abs((angle_deg - last_angle + 180) % 360 - 180)
            if diff < min_sep_deg:
                layer = (layer + 1) % 3  # циклически смещаем по 3 уровням радиуса
            else:
                layer = 0
        else:
            layer = 0
        result.append((key, abs_pos, angle_deg, retro, layer))
        last_angle = angle_deg
    return result


def draw_natal_planets(ax, natal_planets, asc_lon):
    """Натальные планеты: символы между R_HOUSE_OUTER и R_NATAL_PLANETS_OUT."""
    items = list(natal_planets.items())
    spread = _spread_planets(items, asc_lon, min_sep_deg=6.0)
    R_BASE = R_NATAL_PLANETS
    for key, abs_pos, angle_deg, retro, layer in spread:
        # Layer offset — небольшое смещение по радиусу при перекрытии
        r = R_BASE - layer * 0.025
        t = math.radians(angle_deg)
        x, y = r * math.cos(t), r * math.sin(t)
        color = PLANET_COLORS.get(key, '#FFFFFF')
        symbol = PLANET_SYMBOLS.get(key, '?')

        # Кружок-фон
        dot = plt.Circle((x, y), 0.022, color=color, alpha=0.85, zorder=6)
        ax.add_patch(dot)
        # Символ
        ax.text(x, y, symbol, ha='center', va='center',
                fontsize=10, color='#1A1A2E', fontweight='bold', zorder=7)
        # Градус и ретроград — наружу от символа
        deg_in_sign = abs_pos % 30
        deg_label = f"{int(deg_in_sign)}°{'℞' if retro else ''}"
        r_lbl = r + 0.045
        ax.text(r_lbl * math.cos(t), r_lbl * math.sin(t),
                deg_label, ha='center', va='center',
                fontsize=5.5, color=TEXT_LIGHT, zorder=7)


def draw_transit_planets(ax, transit_planets, asc_lon):
    """Транзитные планеты: между R_MID_BORDER и R_TRANSIT_ASPECTS."""
    items = list(transit_planets.items())
    spread = _spread_planets(items, asc_lon, min_sep_deg=6.0)
    R_BASE = R_TRANSIT_PLANETS
    for key, abs_pos, angle_deg, retro, layer in spread:
        r = R_BASE + layer * 0.025
        t = math.radians(angle_deg)
        x, y = r * math.cos(t), r * math.sin(t)
        color = PLANET_COLORS.get(key, '#FFFFFF')
        symbol = PLANET_SYMBOLS.get(key, '?')

        dot = plt.Circle((x, y), 0.024, color=color, alpha=0.95, zorder=6)
        ax.add_patch(dot)
        ax.text(x, y, symbol, ha='center', va='center',
                fontsize=11, color='#1A1A2E', fontweight='bold', zorder=7)
        deg_in_sign = abs_pos % 30
        deg_label = f"{int(deg_in_sign)}°{'℞' if retro else ''}"
        r_lbl = r + 0.05
        ax.text(r_lbl * math.cos(t), r_lbl * math.sin(t),
                deg_label, ha='center', va='center',
                fontsize=6, color=TEXT_LIGHT, zorder=7)


def draw_natal_aspects(ax, natal_aspects, planet_angles, max_orb=8.0):
    """Внутренний круг — линии аспектов натала."""
    for asp in natal_aspects:
        if asp.get('aspect') not in MAJOR_ASPECTS:
            continue
        if asp.get('orb', 999) > max_orb:
            continue
        k1 = asp['p1'].lower().replace(' ', '_')
        k2 = asp['p2'].lower().replace(' ', '_')
        if k1 not in planet_angles or k2 not in planet_angles:
            continue
        t1 = planet_angles[k1]
        t2 = planet_angles[k2]
        color = ASPECT_COLORS.get(asp['aspect'], '#888888')
        # Чем точнее орб — тем менее прозрачно
        alpha = max(0.18, 0.55 - asp['orb'] * 0.04)
        r = R_NATAL_ASPECTS * 0.97
        ax.plot(
            [r * math.cos(t1), r * math.cos(t2)],
            [r * math.sin(t1), r * math.sin(t2)],
            color=color, linewidth=0.7, alpha=alpha, zorder=2,
        )


def draw_transit_natal_aspects(ax, transit_aspects, transit_angles, natal_angles,
                               natal_house_angles, orb_max=3.0):
    """Линии аспектов транзит → натал. Идут от транзитного планетного кольца к натальному."""
    for asp in transit_aspects:
        if asp.get('aspect') not in MAJOR_ASPECTS:
            continue
        if asp.get('orb', 999) > orb_max:
            continue
        tp_key = asp.get('transit_planet')
        np_key = asp.get('natal_point')
        if tp_key not in transit_angles:
            continue
        # Натальная точка может быть планетой или ASC/MC
        if np_key in natal_angles:
            np_angle = natal_angles[np_key]
        elif np_key == 'ascendant' and '1' in natal_house_angles:
            np_angle = natal_house_angles['1']
        elif np_key == 'mc' and '10' in natal_house_angles:
            np_angle = natal_house_angles['10']
        else:
            continue

        tp_angle = transit_angles[tp_key]
        color = ASPECT_COLORS.get(asp['aspect'], '#888888')
        # Чем точнее — тем заметнее
        alpha = max(0.30, 0.85 - asp['orb'] * 0.15)
        # Линия от внутреннего края транзитного кольца до внешнего края натального кольца планет
        r_outer = R_TRANSIT_PLANETS - 0.025
        r_inner = R_NATAL_PLANETS_OUT - 0.005
        ax.plot(
            [r_outer * math.cos(tp_angle), r_inner * math.cos(np_angle)],
            [r_outer * math.sin(tp_angle), r_inner * math.sin(np_angle)],
            color=color, linewidth=1.2, alpha=alpha, zorder=3,
        )


def draw_center_text(ax, name, natal_date, transit_date):
    """Центральная информация."""
    ax.text(0, 0.20, name, ha='center', va='center',
            fontsize=14, color=TEXT_GOLD, fontweight='bold', zorder=10)
    ax.text(0, 0.10, f"Натал: {natal_date}", ha='center', va='center',
            fontsize=8, color=TEXT_LIGHT, zorder=10)
    ax.text(0, 0.02, f"Транзит: {transit_date}", ha='center', va='center',
            fontsize=8, color=TEXT_LIGHT, zorder=10)
    ax.text(0, -0.10, 'BI-WHEEL', ha='center', va='center',
            fontsize=7, color=TEXT_MUTED, fontstyle='italic', zorder=10,
            alpha=0.7, fontweight='bold')
    # Лёгкое золотое кольцо вокруг текста
    inner_circle = plt.Circle(
        (0, 0), R_CENTER_TEXT,
        fill=False, color=TEXT_GOLD, linewidth=0.6, alpha=0.4, zorder=2,
    )
    ax.add_patch(inner_circle)


def render_biwheel(natal_chart, transits_data, output_path,
                   max_aspect_orb=3.0):
    """Главная функция: рисует bi-wheel и сохраняет PNG.

    Args:
        natal_chart: dict из chart.json
        transits_data: dict из transits.json
        output_path: куда сохранить PNG
        max_aspect_orb: максимальный орб транзитного аспекта для линий
    """
    fig, ax = plt.subplots(figsize=(11, 11), dpi=150)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.set_xlim(-1.18, 1.18)
    ax.set_ylim(-1.18, 1.18)
    ax.set_aspect('equal')
    ax.axis('off')

    # ── Опорная точка: натальный ASC ─────────────────────────────────────────
    natal_houses = natal_chart.get('houses', {})
    natal_planets = natal_chart.get('planets', {})
    asc_lon = 0.0
    if natal_chart.get('ascendant'):
        asc_lon = natal_chart['ascendant'].get('abs_pos', 0.0)
    elif '1' in natal_houses:
        asc_lon = natal_houses['1'].get('abs_pos', 0.0)

    # ── Зодиакальное кольцо ──────────────────────────────────────────────────
    draw_zodiac_ring(ax, asc_lon)
    draw_borders(ax)

    # ── Натальные дома ───────────────────────────────────────────────────────
    draw_houses(ax, natal_houses, asc_lon)

    # ── Углы натальных планет (для аспектов и поиска) ────────────────────────
    natal_planet_angles = {
        k: math.radians(lon_to_angle(p['abs_pos'], asc_lon))
        for k, p in natal_planets.items() if p.get('abs_pos') is not None
    }
    natal_house_angles = {
        k: math.radians(lon_to_angle(h['abs_pos'], asc_lon))
        for k, h in natal_houses.items() if h.get('abs_pos') is not None
    }

    # ── Аспекты натал↔натал (внутренний круг) ────────────────────────────────
    draw_natal_aspects(ax, natal_chart.get('aspects', []), natal_planet_angles)

    # ── Натальные планеты ────────────────────────────────────────────────────
    draw_natal_planets(ax, natal_planets, asc_lon)

    # ── Транзитные планеты ───────────────────────────────────────────────────
    transit_planets = transits_data.get('transit_planets', {})
    draw_transit_planets(ax, transit_planets, asc_lon)

    # ── Углы транзитных планет (для линий аспектов) ──────────────────────────
    transit_planet_angles = {
        k: math.radians(lon_to_angle(p['absolute'], asc_lon))
        for k, p in transit_planets.items() if p.get('absolute') is not None
    }

    # ── Линии транзит↔натал ──────────────────────────────────────────────────
    draw_transit_natal_aspects(
        ax,
        transits_data.get('all_aspects', []),
        transit_planet_angles,
        natal_planet_angles,
        natal_house_angles,
        orb_max=max_aspect_orb,
    )

    # ── Центральный текст ────────────────────────────────────────────────────
    name = natal_chart.get('meta', {}).get('name', 'Без имени')
    natal_date = natal_chart.get('meta', {}).get('date', '?')
    transit_date = transits_data.get('meta', {}).get('transit_date', '?')
    draw_center_text(ax, name, natal_date, transit_date)

    # ── Заголовок и подпись ──────────────────────────────────────────────────
    ax.set_title(
        f"Натал × Транзиты — {name}",
        color=TEXT_GOLD, fontsize=14, pad=12, fontweight='bold',
    )
    fig.text(
        0.5, 0.02,
        f"Внутри — натальная карта · Снаружи — транзиты на {transit_date} · "
        f"Линии — активные аспекты (орб ≤ {max_aspect_orb}°)",
        ha='center', color=TEXT_MUTED, fontsize=8, style='italic',
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return output_path


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description='Bi-wheel PNG: натал + транзиты')
    ap.add_argument('--natal', required=True, help='Путь к chart.json')
    ap.add_argument('--transits', required=True, help='Путь к transits.json')
    ap.add_argument('--out', required=True, help='Путь к PNG')
    ap.add_argument('--orb-max', type=float, default=3.0,
                    help='Макс. орб аспектов транзит-натал для отображения линий (def 3.0°)')
    args = ap.parse_args()

    natal_path = Path(args.natal).expanduser()
    transits_path = Path(args.transits).expanduser()
    out_path = Path(args.out).expanduser()

    if not natal_path.exists():
        print(f"❌ Натальная карта не найдена: {natal_path}", file=sys.stderr)
        sys.exit(1)
    if not transits_path.exists():
        print(f"❌ Транзиты не найдены: {transits_path}", file=sys.stderr)
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(natal_path, 'r', encoding='utf-8') as f:
        natal = json.load(f)
    with open(transits_path, 'r', encoding='utf-8') as f:
        transits = json.load(f)

    print(f"  📖 Натал: {natal_path.name}")
    print(f"  🌌 Транзиты: {transits_path.name}")
    print(f"  🎨 Рисую bi-wheel...")
    result = render_biwheel(natal, transits, str(out_path),
                            max_aspect_orb=args.orb_max)
    print(f"  🖼  PNG: {result}")
    return str(result)


if __name__ == '__main__':
    main()
