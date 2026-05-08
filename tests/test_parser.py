"""Tests for the HY-TEK result file parser."""

import pytest
from pathlib import Path

from cyo_track.parser import (
    MeetResult,
    _parse_score,
    _parse_event_header,
    parse_text,
    parse_file,
)

RESULTS_DIR = Path(__file__).parent.parent / "results" / "2026"
R1 = RESULTS_DIR / "r1"
R2 = RESULTS_DIR / "r2"
R3 = RESULTS_DIR / "r3"


# ── Score parsing ──────────────────────────────────────────────────────────────

class TestParseScore:
    def test_decimal_seconds(self):
        secs, feet = _parse_score("17.41")
        assert secs == pytest.approx(17.41)
        assert feet is None

    def test_minutes_seconds(self):
        secs, feet = _parse_score("1:30.04")
        assert secs == pytest.approx(90.04)
        assert feet is None

    def test_long_time(self):
        secs, feet = _parse_score("8:17.19")
        assert secs == pytest.approx(497.19)
        assert feet is None

    def test_long_jump_feet_inches(self):
        # "9-10.00" = 9 feet 10.00 inches
        secs, feet = _parse_score("9-10.00")
        assert secs is None
        assert feet == pytest.approx(9 + 10.0 / 12)

    def test_javelin_feet_inches(self):
        # "17-04" = 17 feet 4 inches (no hundredths)
        secs, feet = _parse_score("17-04")
        assert secs is None
        assert feet == pytest.approx(17 + 4 / 12)

    def test_large_javelin(self):
        secs, feet = _parse_score("65-08")
        assert secs is None
        assert feet == pytest.approx(65 + 8 / 12)

    def test_long_jump_zero_inches(self):
        secs, feet = _parse_score("5-00.00")
        assert secs is None
        assert feet == pytest.approx(5.0)


# ── Event header parsing ───────────────────────────────────────────────────────

class TestParseEventHeader:
    def test_girls_heat_dash(self):
        g, ag, et = _parse_event_header("Girls 2&U 100 Meter Dash")
        assert g == "Girls"
        assert ag == "2&U"
        assert et == "100 Meter Dash"

    def test_boys_age_range(self):
        g, ag, et = _parse_event_header("Boys 7-8 1600 Meter Run")
        assert g == "Boys"
        assert ag == "7-8"
        assert et == "1600 Meter Run"

    def test_long_jump(self):
        g, ag, et = _parse_event_header("Girls 5-6 Long Jump")
        assert g == "Girls"
        assert ag == "5-6"
        assert et == "Long Jump"

    def test_javelin(self):
        g, ag, et = _parse_event_header("Boys 3-4 Javelin Throw")
        assert g == "Boys"
        assert ag == "3-4"
        assert et == "Javelin Throw"

    def test_non_event_returns_none(self):
        assert _parse_event_header("Finals") is None
        assert _parse_event_header("    Name    Year School") is None


# ── Fixed-width column extraction ──────────────────────────────────────────────

class TestColumnExtraction:
    """Verify every fixed-width field via parse_text on crafted snippets."""

    def _parse_one(self, result_line: str, has_heat: bool = True) -> MeetResult:
        header = (
            "Girls 2&U 100 Meter Dash\n"
            "===================================================================================\n"
            "    Name                    Year School                  Seed     Finals  H# Points\n"
            "===================================================================================\n"
            if has_heat else
            "Girls 2&U Long Jump\n"
            "================================================================================\n"
            "    Name                    Year School                  Seed     Finals  Points\n"
            "================================================================================\n"
        )
        results = parse_text(header + result_line + "\n")
        assert len(results) == 1, f"Expected 1 result, got {len(results)}"
        return results[0]

    def test_heat_with_points(self):
        r = self._parse_one(
            "  1 #  278 Daiga, Astrid       2 SMSG                              17.41   6  10   "
        )
        assert r.placement == "1"
        assert r.bib_number == "278"
        assert r.name == "Daiga, Astrid"
        assert r.year == "2"
        assert r.school == "SMSG"
        assert r.score_raw == "17.41"
        assert r.score_seconds == pytest.approx(17.41)
        assert r.heat_num == "6"
        assert r.points == 10.0
        assert r.has_heat is True

    def test_heat_no_points(self):
        r = self._parse_one(
            " 11 #  296 Echezona, Ijeoma    5 Sacred Heart - H                  42.94   8 "
        )
        assert r.placement == "11"
        assert r.name == "Echezona, Ijeoma"
        assert r.year == "5"
        assert r.school == "Sacred Heart - H"
        assert r.heat_num == "8"
        assert r.points is None

    def test_blank_year(self):
        r = self._parse_one(
            " 14 #  612 Tobin, Maeve          IHM                               21.24   4 "
        )
        assert r.year == ""
        assert r.school == "IHM"

    def test_pk_year(self):
        r = self._parse_one(
            " 38 #  233 Willis, Kali       PK OL Grace                          22.29   1 "
        )
        assert r.year == "PK"
        assert r.school == "OL Grace"

    def test_k_year(self):
        r = self._parse_one(
            "  4 #    2 Duffell, Jenny      K Annunciation                      16.61   7   5   "
        )
        assert r.year == "K"
        assert r.bib_number == "2"
        assert r.points == 5.0

    def test_minute_time(self):
        r = self._parse_one(
            "  2 #  281 Sanchez, Ximena     2 SMSG                            1:37.21   2   8   "
        )
        assert r.score_raw == "1:37.21"
        assert r.score_seconds == pytest.approx(97.21)
        assert r.points == 8.0

    def test_non_heat_long_time(self):
        r = self._parse_one(
            "  9 #  572 Vincent, Morgan     1 John Paul                       4:35.90 ",
            has_heat=False,
        )
        assert r.score_raw == "4:35.90"
        assert r.score_seconds == pytest.approx(275.90)
        assert r.heat_num is None
        assert r.points is None

    def test_long_jump_decimal_points(self):
        r = self._parse_one(
            "  7 #  281 Sanchez, Ximena     2 SMSG                            5-00.00    1.50",
            has_heat=False,
        )
        assert r.score_raw == "5-00.00"
        assert r.score_feet == pytest.approx(5.0)
        assert r.score_seconds is None
        assert r.points == pytest.approx(1.5)

    def test_javelin_heat(self):
        r = self._parse_one(
            "  2 #  278 Daiga, Astrid       2 SMSG                              17-04   1   8   "
        )
        assert r.score_raw == "17-04"
        assert r.score_feet == pytest.approx(17 + 4 / 12)
        assert r.heat_num == "1"
        assert r.points == 8.0


# ── Full-file parsing ──────────────────────────────────────────────────────────

class TestParseFile:
    def test_r1_parses_without_error(self):
        results = parse_file(R1)
        assert len(results) > 0

    def test_r2_parses_without_error(self):
        results = parse_file(R2)
        assert len(results) > 0

    def test_r3_parses_without_error(self):
        results = parse_file(R3)
        assert len(results) > 0

    def test_r1_event_count(self):
        results = parse_file(R1)
        events = {r.event for r in results}
        # r1 has both heat and non-heat events across Girls and Boys
        assert len(events) >= 20

    def test_r1_has_long_jump_results(self):
        results = parse_file(R1)
        lj = [r for r in results if r.event_type == "Long Jump"]
        assert len(lj) > 0
        # All long jump scores should be in feet, not seconds
        assert all(r.score_feet is not None for r in lj)
        assert all(r.score_seconds is None for r in lj)

    def test_r1_has_javelin_results(self):
        results = parse_file(R1)
        jav = [r for r in results if r.event_type == "Javelin Throw"]
        assert len(jav) > 0
        assert all(r.score_feet is not None for r in jav)

    def test_r1_has_timed_results(self):
        results = parse_file(R1)
        timed = [r for r in results if "Meter" in (r.event_type or "")]
        assert len(timed) > 0
        assert all(r.score_seconds is not None for r in timed)

    def test_r1_specific_result(self):
        results = parse_file(R1)
        # First result: Girls 2&U 100 Meter Dash, Daiga Astrid, place 1
        r = results[0]
        assert r.gender == "Girls"
        assert r.age_group == "2&U"
        assert r.event_type == "100 Meter Dash"
        assert r.name == "Daiga, Astrid"
        assert r.placement == "1"
        assert r.points == 10.0

    def test_r1_long_jump_top_result(self):
        results = parse_file(R1)
        lj = [r for r in results if r.event == "Girls 3-4 Long Jump"]
        assert lj[0].name == "Purce, Mary Elza"
        assert lj[0].score_raw == "11-07.00"
        assert lj[0].score_feet == pytest.approx(11 + 7.0 / 12)

    def test_r1_javelin_feet_inches_units(self):
        results = parse_file(R1)
        # Boys 7-8 Javelin: top throw is 67-08 = 67'8"
        jav = [r for r in results if r.event == "Boys 7-8 Javelin Throw"]
        top = next(r for r in jav if r.placement == "1")
        assert top.score_raw == "67-08"
        assert top.score_feet == pytest.approx(67 + 8 / 12)

    def test_all_results_have_score(self):
        for path in (R1, R2, R3):
            for r in parse_file(path):
                assert r.score_raw, f"Empty score in {r}"
                assert (r.score_seconds is not None) ^ (r.score_feet is not None), (
                    f"Expected exactly one of score_seconds/score_feet for {r}"
                )

    def test_no_team_ranking_rows_parsed(self):
        for path in (R1, R2, R3):
            for r in parse_file(path):
                # Team ranking lines look like "1) SMSG  263.50" – none should leak through
                assert not r.name.strip().endswith(")"), f"Ranking row leaked: {r}"

    def test_r2_girls_5_6_100m(self):
        results = parse_file(R2)
        dash = [r for r in results if r.event == "Girls 5-6 100 Meter Dash"]
        assert dash[0].name == "Brewster, Jasmia"
        assert dash[0].score_seconds == pytest.approx(14.58)
        assert dash[0].points == 10.0

    def test_r3_girls_2u_100m_has_finals_marker(self):
        # r3 first event uses "Finals" marker before results
        results = parse_file(R3)
        dash = [r for r in results if r.event == "Girls 2&U 100 Meter Dash"]
        assert len(dash) > 0
        assert dash[0].placement == "1"
