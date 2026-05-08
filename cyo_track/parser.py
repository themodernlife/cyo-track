"""
Parser for HY-TEK Meet Manager fixed-width result files.

Column layout (0-indexed):
  0-2   placement    3 chars, right-justified
  3     space
  4-9   bib_number   6 chars, starts with '#'
  10    space
  11-28 name         18 chars, left-justified
  29    space
  30-31 year         2 chars, right-justified (e.g. ' 2', 'PK', ' K', '  ')
  32    space
  33-62 school       30 chars, left-justified
  63+   rest         space + score(8) + space + [heat(3) + space + points(5)] or [points(6)]

Score formats:
  Times:     "17.41"   (seconds)
             "1:30.04" (m:ss.cc)
             "8:17.19" (m:ss.cc)
  Distances: "9-10.00" (feet-inches.hundredths, Long Jump)
             "17-04"   (feet-inches, Javelin Throw)

Whether a result section has a heat column is determined by the column header line:
  - Contains "H#" → heat event (3-column suffix: score heat points)
  - No "H#"       → non-heat event (2-column suffix: score points)
"""

import re
from dataclasses import dataclass
from typing import Optional
from pathlib import Path


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class MeetResult:
    event: str                  # full event string e.g. "Girls 2&U 100 Meter Dash"
    gender: Optional[str]       # "Girls" or "Boys"
    age_group: Optional[str]    # e.g. "2&U", "3-4", "5-6", "7-8"
    event_type: Optional[str]   # e.g. "100 Meter Dash", "Long Jump", "Javelin Throw"
    placement: str              # raw placement, e.g. "1", "11"
    bib_number: str             # numeric part only, e.g. "278"
    name: str                   # e.g. "Daiga, Astrid"
    year: str                   # grade/age, e.g. "2", "K", "PK", "" (blank)
    school: str                 # e.g. "SMSG", "Sacred Heart - H"
    score_raw: str              # as printed, e.g. "17.41", "1:30.04", "9-10.00", "17-04"
    score_seconds: Optional[float]  # for timed events, in seconds; None for field events
    score_feet: Optional[float]     # for field events, in decimal feet; None for timed events
    heat_num: Optional[str]         # heat number string, or None
    points: Optional[float]         # e.g. 10.0, 1.5, or None
    has_heat: bool                  # whether this event used heats


# ── Parsing helpers ────────────────────────────────────────────────────────────

_EVENT_RE = re.compile(r'^(Girls|Boys)\s+([\w&-]+)\s+(.+)$')
_RESULT_LINE_RE = re.compile(r'^[ \d]{3} #')
_TIME_RE = re.compile(r'^(\d+):(\d{2}\.\d{2})$')
_SECONDS_RE = re.compile(r'^\d+\.\d+$')
_FEET_INCHES_RE = re.compile(r'^(\d+)-(\d{2}(?:\.\d+)?)$')


def _parse_score(raw: str) -> tuple[Optional[float], Optional[float]]:
    """Return (score_seconds, score_feet). Exactly one will be non-None."""
    m = _FEET_INCHES_RE.match(raw)
    if m:
        feet = int(m.group(1))
        inches = float(m.group(2))
        return None, feet + inches / 12.0

    m = _TIME_RE.match(raw)
    if m:
        minutes = int(m.group(1))
        seconds = float(m.group(2))
        return minutes * 60 + seconds, None

    if _SECONDS_RE.match(raw):
        return float(raw), None

    return None, None


def _parse_event_header(line: str) -> Optional[tuple[str, str, str]]:
    """Parse 'Girls 2&U 100 Meter Dash' → (gender, age_group, event_type)."""
    m = _EVENT_RE.match(line.strip())
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3)


def _parse_result_line(
    line: str,
    event: str,
    gender: Optional[str],
    age_group: Optional[str],
    event_type: Optional[str],
    has_heat: bool,
) -> Optional[MeetResult]:
    """Parse one fixed-width result line into a MeetResult."""
    if len(line) < 64:
        return None
    if not _RESULT_LINE_RE.match(line):
        return None

    placement = line[0:3].strip()
    bib_number = line[4:10].strip().lstrip('#').strip()
    name = line[11:29].strip()
    year = line[30:32].strip()
    school = line[33:63].strip()

    tokens = line[63:].split()
    if not tokens:
        return None

    score_raw = tokens[0]
    score_seconds, score_feet = _parse_score(score_raw)

    if has_heat:
        heat_num = tokens[1] if len(tokens) >= 2 else None
        points_raw = tokens[2] if len(tokens) >= 3 else None
    else:
        heat_num = None
        points_raw = tokens[1] if len(tokens) >= 2 else None

    points = float(points_raw) if points_raw is not None else None

    return MeetResult(
        event=event,
        gender=gender,
        age_group=age_group,
        event_type=event_type,
        placement=placement,
        bib_number=bib_number,
        name=name,
        year=year,
        school=school,
        score_raw=score_raw,
        score_seconds=score_seconds,
        score_feet=score_feet,
        heat_num=heat_num,
        points=points,
        has_heat=has_heat,
    )


# ── Top-level file parser ──────────────────────────────────────────────────────

def parse_file(path: str | Path) -> list[MeetResult]:
    """Parse an entire HY-TEK results file and return all individual results."""
    text = Path(path).read_text(encoding='utf-8', errors='replace')
    return parse_text(text)


def parse_text(text: str) -> list[MeetResult]:
    """Parse HY-TEK results text and return all individual results."""
    results: list[MeetResult] = []

    current_event: Optional[str] = None
    gender: Optional[str] = None
    age_group: Optional[str] = None
    event_type: Optional[str] = None
    has_heat: bool = False
    in_results: bool = False

    for line in text.splitlines():
        stripped = line.strip()

        if not stripped:
            in_results = False
            continue

        if stripped.startswith('Licensed to') or re.match(r'\d+\)', stripped):
            in_results = False
            continue

        parsed = _parse_event_header(stripped)
        if parsed:
            gender, age_group, event_type = parsed
            current_event = stripped
            in_results = False
            continue

        if 'Name' in line and 'Year' in line and 'School' in line:
            has_heat = 'H#' in line
            continue

        if stripped.startswith('='):
            in_results = True
            continue

        if stripped == 'Finals':
            continue

        if in_results and current_event and _RESULT_LINE_RE.match(line):
            result = _parse_result_line(
                line, current_event, gender, age_group, event_type, has_heat
            )
            if result:
                results.append(result)

    return results
