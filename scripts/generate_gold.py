"""Generate regression gold files with a legacy ReadVarsESO executable."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile


PROJECT_ROOT = Path(__file__).parents[1]
DATA_DIR = PROJECT_ROOT / "tests" / "data"
GOLD_DIR = PROJECT_ROOT / "tests" / "gold"
DEFAULT_EXECUTABLE = Path(r"C:\EnergyPlus-26.1.0\PostProcess\ReadVarsESO.exe")
REGRESSION_MODES = ("with-rvi", "without-rvi")


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
    source_data = configuration.with_suffix(".eso")
    if not source_data.is_file():
        raise FileNotFoundError(f"Missing ESO pair for {configuration}: {source_data}")

    if mode == "with-rvi":
        input_name, output_name = configuration_file_names(configuration)
        arguments = [configuration.name]
    elif mode == "without-rvi":
        input_name, output_name = "eplusout.eso", "eplusout.csv"
        arguments = []
    else:
        raise ValueError(f"Unknown regression mode: {mode}")

    with tempfile.TemporaryDirectory(prefix="readvars-gold-") as temporary:
        working_directory = Path(temporary)
        if mode == "with-rvi":
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
                f"ReadVarsESO failed for {configuration.name} with exit code "
                f"{result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )

        destination = GOLD_DIR / configuration.stem / mode / output_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(working_directory / output_name, destination)
        return destination


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
        help="Optional fixture stems to regenerate; by default all RVI/ESO pairs are used.",
    )
    args = parser.parse_args()

    executable = args.executable.resolve()
    if not executable.is_file():
        parser.error(f"legacy executable does not exist: {executable}")

    requested_cases = set(args.cases)
    configurations = sorted(DATA_DIR.glob("*.rvi"))
    if requested_cases:
        configurations = [item for item in configurations if item.stem in requested_cases]
        missing = requested_cases.difference(item.stem for item in configurations)
        if missing:
            parser.error(f"unknown regression case(s): {', '.join(sorted(missing))}")

    if not configurations:
        parser.error("no RVI/ESO regression cases found")

    for configuration in configurations:
        for mode in REGRESSION_MODES:
            destination = generate_case(executable, configuration, mode)
            print(f"Generated {destination.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
