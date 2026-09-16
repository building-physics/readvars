# readvars

`readvars` is a stand-alone Python implementation of EnergyPlus's historical
ReadVarsESO utility. It reads EnergyPlus ESO and MTR files and writes the same
row-oriented delimited output expected by existing ReadVarsESO workflows.

The package supports both the legacy RVI/MVI interface and a modern interface
for discovering and filtering output variables. It has no runtime
dependencies.

## Installation

```console
python -m pip install readvars
```

This installs both `readvars` and `ReadVarsESO` console commands. The latter is
provided for compatibility with tools that invoke the legacy executable name.

## Command line

Convert every variable in an ESO file:

```console
readvars read eplusout.eso
```

Choose an output file and select hourly temperature variables:

```console
readvars read eplusout.eso --output temperatures.csv \
  --frequency hourly --search temperature
```

Inspect the data dictionary as a table, CSV, or JSON:

```console
readvars list eplusout.eso --format table
readvars list eplusout.eso --frequency hourly --format json
```

The `--list` and `--read` spellings are accepted as aliases. Run
`readvars --help` for all modern options.

### Legacy compatibility

An existing RVI or MVI file can be passed exactly as it was to ReadVarsESO:

```console
ReadVarsESO custom.rvi hourly unlimited fixheader
```

With no arguments, the command reads `eplusout.eso`, writes `eplusout.csv`,
and creates the traditional `readvars.audit` file. Output extensions select
the legacy delimiter: `.csv` uses a comma, `.tab` a tab, and `.txt` a space.

## Python API

```python
from readvars import convert, list_variables

variables = list_variables(
    "eplusout.eso",
    frequency="hourly",
    search="temperature",
)

output_path = convert(
    "eplusout.eso",
    "temperatures.csv",
    frequency="hourly",
    search="temperature",
)
```

`list_variables` returns `DictionaryRecord` objects. `convert` returns the
output `pathlib.Path`. Accepted frequency names are `timestep`, `time-step`,
`detailed`, `detail`, `hourly`, `daily`, `monthly`, `annual`, `runperiod`, and
`run-period`.

## Development

Install the test dependencies and run pytest:

```console
python -m pip install -e ".[test]"
pytest
```

The integration tests exercise modern conversion and the legacy RVI path
against an EnergyPlus ESO fixture; unit tests cover parsing, filtering, and
time aggregation behavior.

## License

`readvars` is distributed under the EnergyPlus license in
[`LICENSE.txt`](LICENSE.txt).
