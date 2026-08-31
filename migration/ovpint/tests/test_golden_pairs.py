"""Golden-pair characterization tests for OVPINT.

Every expected value in this directory was captured from an actual run of
src/OVPINT.cbl compiled by ./tools/build.sh (GnuCOBOL 3.1.2):

  fixtures/shipped_*    -- ./run/pipeline.sh over the fixtures shipped in data/
  fixtures/synthetic_*  -- the same binary over the six synthetic module
                           records in fixtures/synthetic_MODMAST.txt, built
                           in a scratch copy of the repository

Nothing here is derived from the IRM or from the rule as documented.
"""

import pathlib

import pytest
from conftest import FIXTURES

from ovpint import run

CASES = ["shipped", "synthetic"]


@pytest.fixture(params=CASES)
def golden(request, tmp_path):
    name = request.param
    modot = tmp_path / "MODINT.dat"
    report = tmp_path / "OVPINT.rpt"
    counts = run(
        str(FIXTURES / f"{name}_MODFRZ.dat"), str(modot), str(report)
    )
    return name, counts, modot, report


def test_module_output_file_matches_cobol_byte_for_byte(golden):
    name, _, modot, _ = golden
    expected = (FIXTURES / f"{name}_MODINT.dat").read_bytes()
    assert modot.read_bytes() == expected


def test_report_matches_cobol_line_for_line(golden):
    name, _, _, report = golden
    expected = (FIXTURES / f"{name}_OVPINT.rpt").read_text()
    assert report.read_text() == expected


def test_console_counters_match_cobol(golden):
    name, counts, _, _ = golden
    produced = (
        "OVPINT  READ    %06d\n"
        "OVPINT  WRITTEN %06d\n"
        "OVPINT  INTEREST%06d\n"
        "OVPINT  45 DAY  %06d\n"
        % (
            counts["read"],
            counts["written"],
            counts["interest"],
            counts["forty_five"],
        )
    )
    assert produced == (FIXTURES / f"{name}_counters.txt").read_text()


def test_records_are_never_dropped_or_added(golden):
    _, counts, modot, _ = golden
    assert counts["read"] == counts["written"]
    assert modot.stat().st_size == counts["written"] * 150
