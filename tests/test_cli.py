from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


TEST_ESO = Path(__file__).parent / "data" / "readvars_discovery.eso"
SOURCE_ROOT = Path(__file__).parents[1] / "src"


def run_readvars(args: list[str], cwd: Path | None = None, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(SOURCE_ROOT), environment.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    return subprocess.run(
        [sys.executable, "-m", "readvars", *args],
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_list_command_filters_and_emits_json() -> None:
    result = run_readvars(
        [str(value) for value in [
            "list", TEST_ESO, "--frequency", "hourly", "--search", "temperature", "--format", "json"
        ]]
    )
    rows = json.loads(result.stdout)
    assert rows == [
        {
            "number": 8,
            "frequency": "Hourly",
            "key": "ZONE ONE",
            "variable": "Zone Mean Air Temperature",
            "units": "C",
            "label": "ZONE ONE:Zone Mean Air Temperature [C](Hourly)",
        }
    ]


def test_list_command_filters_timestamp_records() -> None:
    result = run_readvars(["--list", str(TEST_ESO), "--format", "json"])
    rows = json.loads(result.stdout)
    assert [row["number"] for row in rows] == [7, 8, 9]


def test_read_command_converts_everything_by_default(tmp_path: Path) -> None:
    input_file = tmp_path / "eplusout.eso"
    input_file.write_bytes(TEST_ESO.read_bytes())

    result = run_readvars(["read", "eplusout.eso"], cwd=tmp_path)

    assert result.stdout == "Wrote eplusout.csv\n"
    assert (tmp_path / "eplusout.csv").read_text(encoding="utf-8").splitlines() == [
        "Date/Time,Environment:Outdoor Dry Bulb [C](Hourly),ZONE ONE:Zone Mean Air Temperature [C](Hourly),ZONE ONE:Zone Air System Sensible Heating Rate [W](TimeStep)",
        " 01/01  01:00:00,-5.0,20.0,",
        " 01/01  02:00:00,-4.0,21.0,",
    ]
    assert not (tmp_path / "readvars.audit").exists()


def test_read_command_supports_output_and_filters(tmp_path: Path) -> None:
    input_file = tmp_path / "input.eso"
    input_file.write_bytes(TEST_ESO.read_bytes())

    run_readvars(
        ["read", str(input_file), "--output", "selected.csv", "--frequency", "hourly", "--search", "temperature"],
        cwd=tmp_path,
    )

    assert (tmp_path / "selected.csv").read_text(encoding="utf-8").splitlines() == [
        "Date/Time,ZONE ONE:Zone Mean Air Temperature [C](Hourly)",
        " 01/01  01:00:00,20.0",
        " 01/01  02:00:00,21.0",
    ]


@pytest.mark.parametrize("option", ["hourly", "Hourly", "h"])
def test_legacy_conversion_still_works(tmp_path: Path, option: str) -> None:
    (tmp_path / "eplusout.eso").write_bytes(TEST_ESO.read_bytes())
    (tmp_path / "custom.rvi").write_text(
        "eplusout.eso\ncustom.csv\nZONE ONE,Zone Mean Air Temperature\n",
        encoding="utf-8",
    )

    run_readvars(["custom.rvi", option, "fixheader"], cwd=tmp_path)

    assert (tmp_path / "custom.csv").read_text(encoding="utf-8").splitlines() == [
        "Date/Time,ZONE ONE:Zone Mean Air Temperature [C](Hourly)",
        " 01/01  01:00:00,20.0 ",
        " 01/01  02:00:00,21.0 ",
    ]
    assert (tmp_path / "readvars.audit").is_file()


def test_missing_modern_input_has_clean_error() -> None:
    result = run_readvars(["list", "missing.eso"], check=False)
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "Input file does not exist: missing.eso\n"
