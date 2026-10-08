# Regression gold files

These files are authoritative outputs from the legacy Fortran ReadVarsESO
program. The initial gold set was generated with EnergyPlus 26.1.0.

Each directory name matches an `.rvi`/`.eso` fixture pair in `tests/data`.
Each case contains two invocation modes:

- `with-rvi` passes the included RVI file to ReadVarsESO and retains the output
  name specified by that file.
- `without-rvi` invokes ReadVarsESO without arguments, using `eplusout.eso` and
  `eplusout.csv` defaults.

Regenerate all gold files deliberately with:

```console
hatch run python scripts/generate_gold.py C:\path\to\ReadVarsESO.exe
```

Pass fixture stems after the executable to update only selected cases. Both
invocation modes are regenerated for every selected case. Review all resulting
gold-file changes before committing them.
