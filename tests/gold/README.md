# Regression gold files

These files are authoritative outputs from the legacy Fortran ReadVarsESO
program. The initial gold set was generated with EnergyPlus 26.1.0.

Each directory name matches an `.rvi`/`.eso` fixture pair in `tests/data`.
The files inside retain the output names specified by the corresponding RVI.

Regenerate all gold files deliberately with:

```console
hatch run python scripts/generate_gold.py C:\path\to\ReadVarsESO.exe
```

Pass fixture stems after the executable to update only selected cases. Review
all resulting gold-file changes before committing them.
