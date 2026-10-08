from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from readvars import ReadVarsFatal, convert, list_variables
from readvars.process import (
    Options,
    Requests,
    SelectedVariable,
    format_time_stamp,
    parse_dictionary_record,
    parse_options,
    parse_rvi_variable_requests,
    process_data_records,
    select_variables,
    separator_for_output,
    write_header,
)


TEST_ESO = Path(__file__).parent / "data" / "readvars_discovery.eso"


def test_parse_legacy_options() -> None:
    assert parse_options([]) == Options("", True, 0, True, False, True)
    assert parse_options(["custom.rvi", "daily", "unlimited", "fixheader"]) == Options(
        "custom.rvi", False, 3, False, True, True
    )
    assert parse_options(["custom.rvi", "noheaderlimit"]) == Options(
        "custom.rvi", False, 0, True, False, False
    )


def test_header_labels_use_legacy_limit_by_default() -> None:
    label = "x" * 150
    selected = [SelectedVariable(7, label, True)]

    limited = StringIO()
    write_header(limited, selected, ",", True, None)
    assert limited.getvalue() == f"Date/Time,{'x' * 144}\n"

    unlimited = StringIO()
    write_header(unlimited, selected, ",", True, None, limit_header=False)
    assert unlimited.getvalue() == f"Date/Time,{label}\n"


def test_output_separator_follows_legacy_extension_rules() -> None:
    assert separator_for_output("results.csv") == ","
    assert separator_for_output("results.TAB") == "\t"
    assert separator_for_output("results.txt") == " "


def test_rvi_requests_support_numbers_names_ignores_comments_and_terminator() -> None:
    requests = parse_rvi_variable_requests(
        [
            "7 ! selected by number",
            "~8",
            "ZONE ONE, Zone Mean Air Temperature [C]",
            "~Environment,Outdoor Dry Bulb",
            "0",
            "9",
        ],
        None,
    )
    assert requests == Requests(
        track_numbers=[7],
        ignore_numbers=[8],
        find_variables=["ZONE ONE,Zone Mean Air Temperature"],
        find_variable_processed=[0],
        ignore_find_variables=["Environment,Outdoor Dry Bulb"],
    )


def test_dictionary_record_parses_key_variable_units_and_frequency() -> None:
    record = parse_dictionary_record("8,2,ZONE ONE,Zone Mean Air Temperature [C] !Hourly")
    assert record is not None
    assert (record.number, record.key, record.variable, record.units, record.frequency) == (
        8,
        "ZONE ONE",
        "Zone Mean Air Temperature",
        "C",
        "Hourly",
    )
    assert record.label == "ZONE ONE:Zone Mean Air Temperature [C](Hourly)"


def test_select_variables_applies_frequency_and_ignores() -> None:
    records = [
        parse_dictionary_record("7,2,Environment,Dry Bulb [C] !Hourly"),
        parse_dictionary_record("8,2,ZONE ONE,Temperature [C] !Hourly"),
        parse_dictionary_record("9,2,ZONE ONE,Temperature [C] !TimeStep"),
    ]
    selected = select_variables(
        [record for record in records if record is not None],
        Requests([], [7], ["ZONE ONE,Temperature"], [0], []),
        False,
        2,
        True,
        None,
    )
    assert [(item.number, item.found) for item in selected] == [(8, True)]


def test_select_all_variables_excludes_internal_timestamp_records() -> None:
    records = [
        parse_dictionary_record(
            "6,1,Calendar Year of Simulation[] ! When Annual Report Variables Requested"
        ),
        parse_dictionary_record("7,1,Environment,Dry Bulb [C] !Hourly"),
    ]

    selected = select_variables(
        [record for record in records if record is not None],
        Requests([], [], [], [], []),
        True,
        0,
        True,
        None,
    )

    assert [item.number for item in selected] == [7]


@pytest.mark.parametrize(
    ("month", "day", "hour", "start", "end", "expected"),
    [
        (1, 2, 1, 0.0, 60.0, " 01/02  01:00:00"),
        (1, 2, 1, 10.0, 10.5, " 01/02  00:10:30"),
    ],
)
def test_timestamp_format_matches_readvars(
    month: int, day: int, hour: int, start: float, end: float, expected: str
) -> None:
    assert format_time_stamp(month, day, hour, start, end) == expected


def test_monthly_records_are_flushed_with_month_label() -> None:
    output = StringIO()
    process_data_records(
        ["ignored", "4,2,1", "7,12.3", "4,2,2", "7,45.6", "End of Data"],
        1,
        [SelectedVariable(7, "Value", True)],
        output,
        "output.csv",
        ",",
        None,
        legacy_spacing=False,
    )
    assert output.getvalue().splitlines() == ["January,12.3", "February,45.6"]


def test_rows_preserve_interior_but_omit_trailing_empty_fields() -> None:
    output = StringIO()
    process_data_records(
        ["ignored", "4,2,1", "7,12.3", "9,45.6", "End of Data"],
        1,
        [
            SelectedVariable(7, "First", True),
            SelectedVariable(8, "Interior missing", True),
            SelectedVariable(9, "Last found", True),
            SelectedVariable(10, "Trailing missing", True),
        ],
        output,
        "output.csv",
        ",",
        None,
        legacy_spacing=False,
    )
    assert output.getvalue() == "January,12.3,,45.6\n"


def test_public_api_lists_and_converts(tmp_path: Path) -> None:
    records = list_variables(TEST_ESO, frequency="hourly", search="temperature")
    assert [record.number for record in records] == [8]

    output = convert(TEST_ESO, tmp_path / "result.csv", frequency="hourly")
    assert output == tmp_path / "result.csv"
    assert output.read_text(encoding="utf-8").splitlines()[0].startswith("Date/Time,Environment")


def test_public_api_rejects_unknown_frequency() -> None:
    with pytest.raises(ValueError, match="Unknown frequency"):
        list_variables(TEST_ESO, frequency="fortnightly")


def test_public_api_reports_malformed_dictionary_without_printing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    malformed = tmp_path / "malformed.eso"
    malformed.write_text("Program Version,EnergyPlus\n", encoding="utf-8")

    with pytest.raises(ReadVarsFatal, match="EOF encountered during read of ESO header records"):
        list_variables(malformed)

    assert capsys.readouterr() == ("", "")
