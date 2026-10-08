from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


DATA_DIR = Path(__file__).parent / "data"
GOLD_DIR = Path(__file__).parent / "gold"
SOURCE_ROOT = Path(__file__).parents[1] / "src"
CONFIGURATION_DATA_SUFFIXES = {".rvi": ".eso", ".mvi": ".mtr"}
REGRESSION_CASES = sorted(
    (
        configuration.stem,
        configuration.suffix,
        data_suffix,
    )
    for configuration_suffix, data_suffix in CONFIGURATION_DATA_SUFFIXES.items()
    for configuration in DATA_DIR.glob(f"*{configuration_suffix}")
    if configuration.with_suffix(data_suffix).is_file()
)
CONFIGURED_REGRESSION_PARAMETERS = [
    pytest.param(
        case_name,
        configuration_suffix,
        data_suffix,
        mode,
        id=f"{case_name}-{mode}",
    )
    for case_name, configuration_suffix, data_suffix in REGRESSION_CASES
    for mode in (
        f"with-{configuration_suffix[1:]}",
        f"without-{configuration_suffix[1:]}",
    )
]
UNCONFIGURED_ESO_PARAMETERS = [
    pytest.param(
        source_data.stem,
        None,
        source_data.suffix,
        "without-rvi",
        id=f"{source_data.stem}-without-rvi",
    )
    for source_data in sorted(DATA_DIR.glob("*.eso"))
    if not source_data.with_suffix(".rvi").is_file()
    and source_data.with_suffix(".mvi").is_file()
]
REGRESSION_PARAMETERS = CONFIGURED_REGRESSION_PARAMETERS + UNCONFIGURED_ESO_PARAMETERS


def configuration_file_names(configuration: Path) -> tuple[str, str]:
    lines = []
    for raw_line in configuration.read_text(encoding="utf-8-sig").splitlines():
        value = raw_line.split("!", 1)[0].strip()
        if value:
            lines.append(value)
        if len(lines) == 2:
            break

    input_name = lines[0] if lines else "eplusout.eso"
    output_name = lines[1] if len(lines) > 1 else "eplusout.csv"
    return input_name, output_name


def run_checked(command: list[str], cwd: Path, environment: dict[str, str] | None = None) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Command failed with exit code {result.returncode}: {command!r}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def first_byte_difference(expected: bytes, actual: bytes) -> str:
    shared_length = min(len(expected), len(actual))
    offset = next(
        (index for index in range(shared_length) if expected[index] != actual[index]),
        shared_length,
    )
    window_start = max(0, offset - 40)
    window_end = offset + 80
    return (
        f"first differing byte offset: {offset}\n"
        f"legacy size: {len(expected)} bytes; Python size: {len(actual)} bytes\n"
        f"legacy context: {expected[window_start:window_end]!r}\n"
        f"Python context: {actual[window_start:window_end]!r}"
    )


@pytest.mark.regression
@pytest.mark.parametrize(
    ("case_name", "configuration_suffix", "data_suffix", "mode"),
    REGRESSION_PARAMETERS,
)
def test_legacy_output_is_byte_exact(
    case_name: str,
    configuration_suffix: str | None,
    data_suffix: str,
    mode: str,
    tmp_path: Path,
) -> None:
    configuration = (
        DATA_DIR / f"{case_name}{configuration_suffix}"
        if configuration_suffix is not None
        else None
    )
    source_data = DATA_DIR / f"{case_name}{data_suffix}"
    with_configuration = mode.startswith("with-")
    if with_configuration:
        assert configuration is not None
        input_name, output_name = configuration_file_names(configuration)
        arguments = [configuration.name]
    else:
        input_name, output_name = "eplusout.eso", "eplusout.csv"
        arguments = []

    python_directory = tmp_path / "python"
    python_directory.mkdir()
    if with_configuration:
        assert configuration is not None
        shutil.copy2(configuration, python_directory / configuration.name)
    shutil.copy2(source_data, python_directory / input_name)

    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(SOURCE_ROOT), environment.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    run_checked(
        [sys.executable, "-m", "readvars", *arguments],
        python_directory,
        environment,
    )

    gold_output = GOLD_DIR / case_name / mode / output_name
    assert gold_output.is_file(), (
        f"Missing gold output for {case_name} ({mode}): {gold_output}. "
        "Run scripts/generate_gold.py with the legacy ReadVarsESO executable."
    )
    # Gold files preserve the CRLF bytes emitted by the Windows Fortran
    # executable. On other platforms, compare against the native line endings
    # that the corresponding native ReadVarsESO build would produce.
    expected = gold_output.read_bytes().replace(b"\r\n", os.linesep.encode())
    actual = (python_directory / output_name).read_bytes()
    if actual != expected:
        pytest.fail(first_byte_difference(expected, actual))
