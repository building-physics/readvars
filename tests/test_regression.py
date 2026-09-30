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
REGRESSION_CASES = sorted(
    configuration.stem
    for configuration in DATA_DIR.glob("*.rvi")
    if configuration.with_suffix(".eso").is_file()
)


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
@pytest.mark.parametrize("case_name", REGRESSION_CASES)
def test_legacy_output_is_byte_exact(
    case_name: str,
    tmp_path: Path,
) -> None:
    configuration = DATA_DIR / f"{case_name}.rvi"
    source_data = DATA_DIR / f"{case_name}.eso"
    input_name, output_name = configuration_file_names(configuration)
    python_directory = tmp_path / "python"
    python_directory.mkdir()
    shutil.copy2(configuration, python_directory / configuration.name)
    shutil.copy2(source_data, python_directory / input_name)

    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(SOURCE_ROOT), environment.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    run_checked(
        [sys.executable, "-m", "readvars", configuration.name],
        python_directory,
        environment,
    )

    gold_output = GOLD_DIR / case_name / output_name
    assert gold_output.is_file(), (
        f"Missing gold output for {case_name}: {gold_output}. "
        "Run scripts/generate_gold.py with the legacy ReadVarsESO executable."
    )
    # Gold files preserve the CRLF bytes emitted by the Windows Fortran
    # executable. On other platforms, compare against the native line endings
    # that the corresponding native ReadVarsESO build would produce.
    expected = gold_output.read_bytes().replace(b"\r\n", os.linesep.encode())
    actual = (python_directory / output_name).read_bytes()
    if actual != expected:
        pytest.fail(first_byte_difference(expected, actual))
