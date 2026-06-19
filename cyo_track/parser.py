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


# ── School name normalization ──────────────────────────────────────────────────

_SCHOOL_ALIASES: dict[str, str] = {
    "ST STEPHEN": "Stephen",
    "STEPH": "Stephen",
    "EPIPHANY": "Epiphany",
    "EPI": "Epiphany",
    "ST BARNABAS": "BARN",
    "St Barnabas": "BARN",
    "K BARN": "BARN",
}


def _normalize_school(name: str) -> str:
    return _SCHOOL_ALIASES.get(name, name)


# ── Student name normalization ───────────────────────────────────────────────
#
# Different meets are scored by different volunteers (and some exports
# truncate names to 18 characters), so the same student can show up under
# several spellings across meets, e.g. "DeLuca, Andrew" vs "Deluca, Andrew",
# or "Sutherland, Peyto" vs "Sutherland, Peyton" (truncated). Pairs below were
# found by fuzzy-matching names within the same school and manually
# confirming each pair is the same student (same gender, overlapping/
# progressing age group, or a clean truncation of the other). Pairs that
# could plausibly be different siblings (different first names sharing a
# surname, e.g. "Patterson, Malik" vs "Patterson, Malique") are deliberately
# excluded.
#
# Keyed by (school name AFTER _normalize_school, name AS PARSED) -> canonical.
_NAME_ALIASES: dict[tuple[str, str], str] = {
    ("SFDC", "Deluca, Andrew"): "DeLuca, Andrew",
    ("IONA", "De los Santos, Ty"): "De Los Santos, Ty",
    ("Epiphany", "Zurl, liam"): "Zurl, Liam",
    ("Annunciation", "Gilchrist, Ronan"): "Gillchrist, Ronan",
    ("OL Grace", "Willis, Kourtney"): "Willlis, Kourtney",
    ("MVP", "Kroczak, Emillia"): "Kroczak, Emilia",
    ("Epiphany", "Bourjolly, Simone"): "Bourgolly, Simone",
    ("Sacred Heart - H", "Echezona, Iejoma"): "Echezona, Ijeoma",
    ("Joseph YORK", "Morales, Matthew"): "Moralis, Matthew",
    ("IONA", "Atkonson, Miles"): "Atkinson, Miles",
    ("Epiphany", "Cariaso, Mill"): "Cariaso, Milo",
    ("SMSG", "Brown II, Sean"): "Brown, Sean",
    ("Annunciation", "Gallotta, Madelin"): "Gallotta, Maddie",
    ("SMSG", "Matesic, Valentin"): "Matesic, Valentina",
    ("SMSG", "Sanchez, Valentin"): "Sanchez, Valentina",
    ("SFA", "Sutherland, Peyto"): "Sutherland, Peyton",
    ("Stephen", "Akala, Christophe"): "Akala, Christopher",
    ("ASD", "Cosentino, Massim"): "Cosentino, Massimo",
    ("NWP", "Patterson, Malach"): "Patterson, Malachi",
    ("NDA", "Saporito, Laurett"): "Saporito, Lauretta",
    ("OLSS", "Otterbeck, Natali"): "Otterbeck, Natalie",
    ("IS 34", "French, Maddison"): "French, Madison",
    ("IS 34", "Dadamo, Gianna"): "D'Adamo, Gianna",
}


def _normalize_student_name(school: str, name: str) -> str:
    return _NAME_ALIASES.get((school, name), name)


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
    if len(line) < 40:
        return None
    if not _RESULT_LINE_RE.match(line):
        return None

    placement = line[0:3].strip()
    bib_number = line[4:10].strip().lstrip('#').strip()
    name = line[11:29].strip()
    year = line[30:32].strip()

    # Parse school and score from the rest of the line. Older files pad the
    # school column to 30 chars so the score starts at position 63; newer files
    # use a shorter column. Find the first token that looks like a score
    # (starts with a digit) to split school from score/heat/points.
    rest_tokens = line[33:].split()
    score_idx = next(
        (i for i, t in enumerate(rest_tokens) if _parse_score(t) != (None, None)),
        None,
    )
    if score_idx is None:
        return None

    school = _normalize_school(' '.join(rest_tokens[:score_idx]))
    remaining = rest_tokens[score_idx:]
    if not remaining:
        return None

    score_raw = remaining[0]
    score_seconds, score_feet = _parse_score(score_raw)

    if has_heat:
        heat_num = remaining[1] if len(remaining) >= 2 else None
        points_raw = remaining[2] if len(remaining) >= 3 else None
    else:
        heat_num = None
        points_raw = remaining[1] if len(remaining) >= 2 else None

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


def _is_first_last_format(text: str) -> bool:
    """Return True if result names in this file use 'First Last' rather than 'Last, First'."""
    names = []
    for line in text.splitlines():
        if _RESULT_LINE_RE.match(line) and len(line) >= 40:
            name = line[11:29].strip()
            if name:
                names.append(name)
        if len(names) >= 20:
            break
    return bool(names) and not any(',' in n for n in names)


def _normalize_name(name: str, first_last: bool) -> str:
    """Convert 'First Last' → 'Last, First' when the file uses that order."""
    if not first_last or ',' in name:
        return name
    parts = name.split(None, 1)
    if len(parts) == 2:
        return f"{parts[1]}, {parts[0]}"
    return name


def parse_text(text: str) -> list[MeetResult]:
    """Parse HY-TEK results text and return all individual results."""
    results: list[MeetResult] = []
    first_last = _is_first_last_format(text)

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
                result.name = _normalize_name(result.name, first_last)
                result.name = _normalize_student_name(result.school, result.name)
                results.append(result)

    return results
