#!/usr/bin/env python3.11
"""
astro-natal-simond: astro_helpers.py
Общие утилиты для модулей скила (натал, транзиты, прогрессии, синастрия и т.д.).

Содержит:
  • Кэш натальных карт (~/.astro-natal-simond/cache/) — для переиспользования
    наталов в расширенных техниках без повторного запроса данных.
  • Slug-генерацию для имён файлов.
  • Парсеры даты/времени/системы (общие для всех модулей).
"""
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── ПУТИ ────────────────────────────────────────────────────────────────────

CACHE_ROOT = Path.home() / ".astro-natal-simond" / "cache"


def cache_dir() -> Path:
    """Возвращает путь к кэш-директории, создаёт если нужно."""
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    return CACHE_ROOT


# ─── SLUGIFY ─────────────────────────────────────────────────────────────────

# Транслит для русского — для безопасных filename-ов на любой ФС
_TRANSLIT = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh',
    'з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o',
    'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'ts',
    'ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
}


def slugify(text: str) -> str:
    """
    Преобразует строку в безопасный slug для filename.
    Кириллица → транслит, всё остальное → ascii lowercase + дефисы.
    Пустые/некорректные входы → "unknown".
    """
    if not text:
        return "unknown"
    s = text.strip().lower()
    # Транслит кириллицы
    out = []
    for ch in s:
        if ch in _TRANSLIT:
            out.append(_TRANSLIT[ch])
        else:
            out.append(ch)
    s = ''.join(out)
    # Убрать диакритику (для латинских алфавитов с акцентами)
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    # Только латиница, цифры, дефис
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = s.strip('-')
    return s or "unknown"


# ─── ПАРСЕРЫ ─────────────────────────────────────────────────────────────────

def parse_date(s: str) -> tuple[int, int, int]:
    """
    Парсит дату из формата ДД.ММ.ГГГГ (или ДД/ММ/ГГГГ или ДД-ММ-ГГГГ).
    Возвращает (year, month, day). Бросает ValueError при ошибке.
    """
    if not s:
        raise ValueError("Пустая дата")
    parts = re.split(r'[./\-]', s.strip())
    if len(parts) != 3:
        raise ValueError(f"Неверный формат даты: '{s}' (ожидается ДД.ММ.ГГГГ)")
    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
    # Валидация
    if not (1 <= day <= 31):
        raise ValueError(f"Неверный день: {day}")
    if not (1 <= month <= 12):
        raise ValueError(f"Неверный месяц: {month}")
    if not (1900 <= year <= 2100):
        raise ValueError(f"Год вне диапазона 1900-2100: {year}")
    return year, month, day


def parse_time(s: str) -> Optional[tuple[int, int]]:
    """
    Парсит время из формата ЧЧ:ММ (или Ч:ММ).
    Возвращает (hour, minute) или None если время неизвестно.
    Слова "неизвестно", "не знаю", "nope", "нет", пустая строка → None.
    """
    if not s:
        return None
    s = s.strip().lower()
    if s in ('неизвестно', 'не знаю', 'не известно', 'nope', 'нет', 'none', 'unknown', '-', '?'):
        return None
    m = re.match(r'^(\d{1,2}):(\d{2})$', s)
    if not m:
        raise ValueError(f"Неверный формат времени: '{s}' (ожидается ЧЧ:ММ)")
    hour, minute = int(m.group(1)), int(m.group(2))
    if not (0 <= hour <= 23):
        raise ValueError(f"Неверный час: {hour}")
    if not (0 <= minute <= 59):
        raise ValueError(f"Неверная минута: {minute}")
    return hour, minute


def parse_system(s: str) -> str:
    """
    Парсит систему. Возвращает 'western' или 'vedic'.
    Падает если 'обе' — обе системы должны вызываться отдельными прогонами.
    """
    if not s:
        return 'western'  # default
    s = s.strip().lower()
    if 'ведич' in s or 'лахир' in s or 'накшатр' in s or 'vedic' in s or 'sidereal' in s:
        return 'vedic'
    if 'западн' in s or 'плацид' in s or 'тропич' in s or 'western' in s:
        return 'western'
    if 'обе' in s or 'both' in s:
        raise ValueError("'обе' — запустите дважды с --system western и --system vedic отдельно")
    # Default
    return 'western'


# ─── КЭШ ─────────────────────────────────────────────────────────────────────

def cache_key(name: str, year: int, month: int, day: int, city: str, system: str = 'western') -> str:
    """
    Ключ кэша: <name_slug>_<YYYY-MM-DD>_<city_slug>_<system>.
    Например: 'dmitriy_1993-08-13_moskva_western'.
    """
    name_slug = slugify(name)
    city_slug = slugify(city) if city else 'nocity'
    date_str = f"{year:04d}-{month:02d}-{day:02d}"
    return f"{name_slug}_{date_str}_{city_slug}_{system}"


def cache_path(name: str, year: int, month: int, day: int, city: str, system: str = 'western') -> Path:
    """Возвращает путь к JSON-файлу кэша для данной карты."""
    return cache_dir() / f"{cache_key(name, year, month, day, city, system)}.json"


def cache_save(chart_dict: dict) -> Path:
    """
    Сохраняет chart_dict в кэш. Извлекает name/date/city/system из самого dict.
    Перезаписывает если уже есть. Возвращает путь.

    Ожидаемая структура chart_dict (из build_chart.py):
      {
        'meta': {'name': str, 'date': 'YYYY-MM-DD', 'city': str, 'system': str, ...},
        ...
      }
    """
    meta = chart_dict.get('meta', {})
    name = meta.get('name', 'unknown')
    date_iso = meta.get('date', '0000-00-00')
    city = meta.get('city', 'unknown')
    system = meta.get('system', 'western')

    try:
        year, month, day = (int(x) for x in date_iso.split('-'))
    except (ValueError, AttributeError):
        # Если дата кривая — используем 'invalid'
        year, month, day = 0, 0, 0

    path = cache_path(name, year, month, day, city, system)

    # Добавим timestamp кэширования в meta (без мутации входа)
    chart_copy = dict(chart_dict)
    meta_copy = dict(meta)
    meta_copy['cached_at'] = datetime.now().isoformat(timespec='seconds')
    chart_copy['meta'] = meta_copy

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(chart_copy, f, ensure_ascii=False, indent=2)
    return path


def cache_load(name: str, year: int, month: int, day: int, city: str, system: str = 'western') -> Optional[dict]:
    """Возвращает chart_dict из кэша или None если нет."""
    path = cache_path(name, year, month, day, city, system)
    if not path.exists():
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def cache_list() -> list[dict]:
    """
    Возвращает список всех кэшированных карт.
    Каждый элемент: {slug, name, date, city, system, cached_at, path}.
    Сортировка по cached_at (новые сначала).
    """
    out = []
    if not CACHE_ROOT.exists():
        return out
    for path in CACHE_ROOT.glob("*.json"):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                chart = json.load(f)
            meta = chart.get('meta', {})
            out.append({
                'slug': path.stem,
                'name': meta.get('name', '?'),
                'date': meta.get('date', '?'),
                'city': meta.get('city', '?'),
                'system': meta.get('system', '?'),
                'cached_at': meta.get('cached_at', '?'),
                'path': str(path),
            })
        except (json.JSONDecodeError, OSError):
            continue
    # Новые сначала
    out.sort(key=lambda x: x.get('cached_at', ''), reverse=True)
    return out


def cache_find(name_query: str) -> list[dict]:
    """
    Нечёткий поиск по имени в кэше.
    Возвращает список совпадений (по подстроке slug имени).
    """
    if not name_query:
        return []
    query_slug = slugify(name_query)
    results = []
    for entry in cache_list():
        entry_name_slug = slugify(entry.get('name', ''))
        if query_slug in entry_name_slug or entry_name_slug in query_slug:
            results.append(entry)
    return results


# ─── CLI для отладки кэша ────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Использование:")
        print("  astro_helpers.py list                  — все кэшированные карты")
        print("  astro_helpers.py find <name>           — поиск по имени")
        print("  astro_helpers.py path                  — путь к кэшу")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == 'list':
        entries = cache_list()
        if not entries:
            print(f"Кэш пуст ({cache_dir()})")
        else:
            print(f"Кэш ({len(entries)} карт) в {cache_dir()}:")
            for e in entries:
                print(f"  • {e['name']} {e['date']} {e['city']} ({e['system']}) — {e['cached_at']}")
                print(f"    slug: {e['slug']}")
    elif cmd == 'find':
        if len(sys.argv) < 3:
            print("Укажи имя для поиска: astro_helpers.py find <name>")
            sys.exit(1)
        results = cache_find(sys.argv[2])
        if not results:
            print(f"Не найдено карт по запросу '{sys.argv[2]}'")
        else:
            print(f"Найдено {len(results)} карт:")
            for e in results:
                print(f"  • {e['name']} {e['date']} {e['city']} ({e['system']})")
                print(f"    {e['path']}")
    elif cmd == 'path':
        print(cache_dir())
    else:
        print(f"Неизвестная команда: {cmd}")
        sys.exit(1)
