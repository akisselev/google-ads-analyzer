"""
Locale-aware holiday and seasonal peak calendars for Google Ads analysis.

Supported locales: CH (Switzerland), US, GB (United Kingdom).
All other locales return empty data silently.
"""

from __future__ import annotations
import calendar
import re
from datetime import date, timedelta

from dateutil.easter import easter
from dateutil import parser as dparser


# ── private helpers ───────────────────────────────────────────────────────────

def _nth_weekday(year: int, month: int, n: int, weekday: int) -> date:
    """Return the n-th (1-based) occurrence of weekday (Mon=0, Sun=6) in month."""
    d = date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + timedelta(days=offset) + timedelta(weeks=n - 1)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Return the last occurrence of weekday (Mon=0, Sun=6) in month."""
    last = date(year, month, calendar.monthrange(year, month)[1])
    offset = (last.weekday() - weekday) % 7
    return last - timedelta(days=offset)


def _advent_sundays(year: int) -> list[date]:
    """Return the 4 Advent Sundays (Advent 1 through Advent 4) for the year."""
    dec24 = date(year, 12, 24)
    days_back = (dec24.weekday() - 6) % 7
    advent4 = dec24 - timedelta(days=days_back)
    return [advent4 - timedelta(weeks=3 - i) for i in range(4)]


# ── holiday calendars ─────────────────────────────────────────────────────────

def get_holidays(locale: str, year: int) -> dict[date, tuple[str, str]]:
    """
    Return {date: (name, type)} for the given locale and year.
    type is one of: 'public_holiday', 'gifting_peak', 'shopping_peak'.
    Unsupported locales return {}.
    """
    if locale == 'CH':
        return _holidays_ch(year)
    if locale == 'US':
        return _holidays_us(year)
    if locale == 'GB':
        return _holidays_gb(year)
    return {}


def _holidays_ch(year: int) -> dict[date, tuple[str, str]]:
    e = easter(year)
    hols: dict[date, tuple[str, str]] = {
        date(year, 1, 1):  ("New Year's Day / Neujahr",         'public_holiday'),
        date(year, 2, 14): ("Valentine's Day / Valentinstag",   'gifting_peak'),
        e - timedelta(2):  ("Good Friday / Karfreitag",          'public_holiday'),
        e:                 ("Easter Sunday / Ostersonntag",      'public_holiday'),
        date(year, 5, 1):  ("Labour Day / Tag der Arbeit",       'public_holiday'),
        e + timedelta(39): ("Ascension / Auffahrt",              'public_holiday'),
        e + timedelta(49): ("Pentecost / Pfingsten",             'public_holiday'),
        _nth_weekday(year, 5, 2, 6): ("Mother's Day / Muttertag", 'gifting_peak'),
        _nth_weekday(year, 6, 1, 6): ("Father's Day / Vatertag",  'gifting_peak'),
        date(year, 8, 1):  ("National Day / Nationalfeiertag",   'public_holiday'),
        date(year, 12, 25): ("Christmas / Weihnachten",          'public_holiday'),
        date(year, 12, 26): ("St. Stephen's Day / Stephanstag",  'public_holiday'),
    }
    for i, d in enumerate(_advent_sundays(year), 1):
        hols[d] = (f'Advent Sunday {i}', 'shopping_peak')
    return hols


def _holidays_us(year: int) -> dict[date, tuple[str, str]]:
    thanksgiving = _nth_weekday(year, 11, 4, 3)
    return {
        date(year, 1, 1):    ("New Year's Day",    'public_holiday'),
        date(year, 2, 14):   ("Valentine's Day",   'gifting_peak'),
        _nth_weekday(year, 5, 2, 6):  ("Mother's Day",    'gifting_peak'),
        _last_weekday(year, 5, 0):    ("Memorial Day",    'public_holiday'),
        _nth_weekday(year, 6, 3, 6):  ("Father's Day",    'gifting_peak'),
        date(year, 7, 4):    ("Independence Day",  'public_holiday'),
        _nth_weekday(year, 9, 1, 0):  ("Labor Day",       'public_holiday'),
        date(year, 10, 31):  ("Halloween",         'shopping_peak'),
        thanksgiving:                 ("Thanksgiving",    'public_holiday'),
        thanksgiving + timedelta(1):  ("Black Friday",    'shopping_peak'),
        thanksgiving + timedelta(4):  ("Cyber Monday",    'shopping_peak'),
        date(year, 12, 25):  ("Christmas Day",     'public_holiday'),
    }


def _holidays_gb(year: int) -> dict[date, tuple[str, str]]:
    e = easter(year)
    thanksgiving = _nth_weekday(year, 11, 4, 3)
    return {
        date(year, 1, 1):             ("New Year's Day",              'public_holiday'),
        e - timedelta(21):            ("Mother's Day (Mothering Sunday)", 'gifting_peak'),
        e - timedelta(2):             ("Good Friday",                  'public_holiday'),
        e + timedelta(1):             ("Easter Monday",                'public_holiday'),
        _nth_weekday(year, 5, 1, 0):  ("Early May Bank Holiday",      'public_holiday'),
        _last_weekday(year, 5, 0):    ("Spring Bank Holiday",         'public_holiday'),
        _nth_weekday(year, 6, 3, 6):  ("Father's Day",                'gifting_peak'),
        _last_weekday(year, 8, 0):    ("Summer Bank Holiday",         'public_holiday'),
        thanksgiving + timedelta(1):  ("Black Friday",                'shopping_peak'),
        thanksgiving + timedelta(4):  ("Cyber Monday",                'shopping_peak'),
        date(year, 12, 25):           ("Christmas Day",               'public_holiday'),
        date(year, 12, 26):           ("Boxing Day",                  'public_holiday'),
    }


# ── date range parsing ────────────────────────────────────────────────────────

def _parse_period(text: str) -> tuple[date | None, date | None]:
    """Parse 'Apr 1, 2026 – May 6, 2026' or 'Apr 1, 2026' into (start, end)."""
    try:
        parts = re.split(r'\s*[–—]\s*|\s+-\s+', text.strip())
        if len(parts) >= 2:
            start = dparser.parse(parts[0]).date()
            end = dparser.parse(parts[1]).date()
            return start, end
        single = dparser.parse(parts[0]).date()
        return single, single
    except Exception:
        return None, None


# ── main public function ──────────────────────────────────────────────────────

_TYPE_LABEL = {
    'public_holiday': 'Public holiday',
    'gifting_peak':   'Gifting peak',
    'shopping_peak':  'Shopping peak',
}

SUPPORTED_LOCALES = {'CH', 'US', 'GB'}


def get_seasonality_context(locale: str | None, date_range_str: str) -> str | None:
    """
    Return a formatted multi-line seasonality context string, or None if nothing to show.

    date_range_str examples:
      "Apr 1, 2026 – May 6, 2026"
      "Apr 1, 2026 – May 6, 2026 compared to Mar 1, 2026 – Mar 31, 2026"
    """
    if not locale or locale not in SUPPORTED_LOCALES:
        return None

    # Split into current and (optional) previous period
    parts = re.split(r'\s+compared to\s+', date_range_str, flags=re.IGNORECASE)
    curr_text = parts[0].strip()
    prev_text = parts[1].strip() if len(parts) >= 2 else None

    curr_start, curr_end = _parse_period(curr_text)
    if curr_start is None or curr_end is None:
        return None

    prev_start, prev_end = _parse_period(prev_text) if prev_text else (None, None)

    # Collect holidays for all relevant years
    years: set[int] = set(range(curr_start.year, curr_end.year + 1))
    if prev_start and prev_end:
        years.update(range(prev_start.year, prev_end.year + 1))
    all_hols: dict[date, tuple[str, str]] = {}
    for y in sorted(years):
        all_hols.update(get_holidays(locale, y))

    window = timedelta(days=14)

    def _classify(start: date, end: date) -> tuple[list, list, list]:
        in_r, pre_r, post_r = [], [], []
        for d, (name, typ) in sorted(all_hols.items()):
            if start <= d <= end:
                in_r.append((d, name, typ))
            elif start - window <= d < start:
                pre_r.append((d, name, typ))
            elif end < d <= end + window:
                post_r.append((d, name, typ))
        return in_r, pre_r, post_r

    in_range, pre_range, post_range = _classify(curr_start, curr_end)

    def _overlaps_pre_christmas(start: date, end: date) -> bool:
        for y in range(start.year, end.year + 1):
            if start <= date(y, 12, 24) and end >= date(y, 12, 10):
                return True
        return False

    xmas_overlap = _overlaps_pre_christmas(curr_start, curr_end)

    if not in_range and not pre_range and not post_range and not xmas_overlap:
        return None

    lines: list[str] = []
    lines.append(f'SEASONALITY CONTEXT ({locale})')
    lines.append('─' * 60)

    def _fmt_row(d: date, name: str, typ: str) -> str:
        label = _TYPE_LABEL.get(typ, typ)
        return f'  {d.strftime("%b %-d"):<10}  {name:<40}  [{label}]'

    if in_range:
        lines.append('Holidays/peaks within this period:')
        for row in in_range:
            lines.append(_fmt_row(*row))

    if pre_range:
        lines.append('Recent (within 14 days before period start):')
        for row in pre_range:
            lines.append(_fmt_row(*row))

    if post_range:
        lines.append('Upcoming (within 14 days after period end):')
        for row in post_range:
            lines.append(_fmt_row(*row))

    if xmas_overlap:
        lines.append('Pre-Christmas shopping window (Dec 10–24) overlaps with this period.')

    shopping = [(d, n) for d, n, t in in_range if t == 'shopping_peak']
    gifting  = [(d, n) for d, n, t in in_range if t == 'gifting_peak']
    if shopping or gifting:
        lines.append('')
    if shopping:
        lines.append(f'Note: Period contains {len(shopping)} shopping peak(s): '
                     f'{", ".join(n for _, n in shopping)}')
    if gifting:
        lines.append(f'Note: Period contains gifting event(s): '
                     f'{", ".join(n for _, n in gifting)} — expect elevated purchase intent')

    # Comparison asymmetry
    if prev_start and prev_end:
        prev_in, _, _ = _classify(prev_start, prev_end)
        curr_names = {n for _, n, _ in in_range}
        prev_names = {n for _, n, _ in prev_in}
        only_curr = sorted(curr_names - prev_names)
        only_prev = sorted(prev_names - curr_names)
        if only_curr or only_prev:
            lines.append('')
            lines.append('Holiday asymmetry between periods (may explain metric differences):')
            if only_curr:
                lines.append(f'  Current period only:  {", ".join(only_curr)}')
            if only_prev:
                lines.append(f'  Previous period only: {", ".join(only_prev)}')

    return '\n'.join(lines)
