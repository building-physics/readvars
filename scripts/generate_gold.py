"""Generate regression gold files with a legacy ReadVarsESO executable."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4


PROJECT_ROOT = Path(__file__).parents[1]
DATA_DIR = PROJECT_ROOT / "tests" / "data"
GOLD_DIR = PROJECT_ROOT / "tests" / "gold"
TEMP_DIR = PROJECT_ROOT / ".regression"
DEFAULT_EXECUTABLE = Path(r"C:\EnergyPlus-26.1.0\PostProcess\ReadVarsESO.exe")
CONFIGURATION_DATA_SUFFIXES = {".rvi": ".eso", ".mvi": ".mtr"}


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


def generate_case(executable: Path, configuration: Path, mode: str) -> Path:
    """Generate one gold output for a fixture and invocation mode."""
    data_suffix = CONFIGURATION_DATA_SUFFIXES[configuration.suffix.lower()]
    source_data = configuration.with_suffix(data_suffix)
    if not source_data.is_file():
        raise FileNotFoundError(f"Missing data pair for {configuration}: {source_data}")

    expected_with_mode = f"with-{configuration.suffix[1:].lower()}"
    expected_without_mode = f"without-{configuration.suffix[1:].lower()}"
    if mode == expected_with_mode:
        input_name, output_name = configuration_file_names(configuration)
        arguments = [configuration.name]
    elif mode == expected_without_mode:
        input_name, output_name = "eplusout.eso", "eplusout.csv"
        arguments = []
    else:
        raise ValueError(f"Unknown regression mode: {mode}")

    return generate_output(
        executable,
        source_data,
        configuration if mode == expected_with_mode else None,
        mode,
        input_name,
        output_name,
        arguments,
    )


def generate_output(
    executable: Path,
    source_data: Path,
    configuration: Path | None,
    mode: str,
    input_name: str,
    output_name: str,
    arguments: list[str],
) -> Path:
    """Run ReadVarsESO once and save its output as a gold file."""
    TEMP_DIR.mkdir(exist_ok=True)
    working_directory = TEMP_DIR / f"readvars-gold-{uuid4().hex}"
    working_directory.mkdir()
    try:
        if configuration is not None:
            shutil.copy2(configuration, working_directory / configuration.name)
        shutil.copy2(source_data, working_directory / input_name)
        result = subprocess.run(
            [str(executable), *arguments],
            cwd=working_directory,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ReadVarsESO failed for {source_data.name} with exit code "
                f"{result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )

        destination = GOLD_DIR / source_data.stem / mode / output_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(working_directory / output_name, destination)
        return destination
    finally:
        shutil.rmtree(working_directory)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "executable",
        nargs="?",
        type=Path,
        default=DEFAULT_EXECUTABLE,
        help=f"Legacy ReadVarsESO executable (default: {DEFAULT_EXECUTABLE})",
    )
    parser.add_argument(
        "cases",
        nargs="*",
        help=(
            "Optional fixture stems to regenerate; by default all RVI/ESO and "
            "MVI/MTR pairs and associated standalone ESO modes are used."
        ),
    )
    args = parser.parse_args()

    executable = args.executable.resolve()
    if not executable.is_file():
        parser.error(f"legacy executable does not exist: {executable}")

    requested_cases = set(args.cases)
    configurations = sorted(
        configuration
        for configuration_suffix, data_suffix in CONFIGURATION_DATA_SUFFIXES.items()
        for configuration in DATA_DIR.glob(f"*{configuration_suffix}")
        if configuration.with_suffix(data_suffix).is_file()
    )
    standalone_eso_files = sorted(
        source_data
        for source_data in DATA_DIR.glob("*.eso")
        if not source_data.with_suffix(".rvi").is_file()
        and source_data.with_suffix(".mvi").is_file()
    )
    if requested_cases:
        configurations = [item for item in configurations if item.stem in requested_cases]
        standalone_eso_files = [item for item in standalone_eso_files if item.stem in requested_cases]
        found_cases = {item.stem for item in configurations + standalone_eso_files}
        missing = requested_cases.difference(found_cases)
        if missing:
            parser.error(f"unknown regression case(s): {', '.join(sorted(missing))}")

    if not configurations and not standalone_eso_files:
        parser.error("no regression cases found")

    for configuration in configurations:
        configuration_kind = configuration.suffix[1:].lower()
        for mode in (f"with-{configuration_kind}", f"without-{configuration_kind}"):
            destination = generate_case(executable, configuration, mode)
            print(f"Generated {destination.relative_to(PROJECT_ROOT)}")
    for source_data in standalone_eso_files:
        destination = generate_output(
            executable,
            source_data,
            None,
            "without-rvi",
            "eplusout.eso",
            "eplusout.csv",
            [],
        )
        print(f"Generated {destination.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
