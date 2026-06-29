# BenchTomlStore — single source of truth for bench.toml

## Problem

Reading and writing `bench.toml` was spread across many mechanisms:

- **Writes:** `bench_config_to_toml()` + `write_text` (typed), `BenchTomlBuilder.render()` + `write_text` (wizard creation), and `utils.write_toml()` (raw-dict round-trips) — 14 call sites.
- **Reads:** `BenchConfig.from_file()` (typed+validated), `BenchConfig._from_dict()` (typed, no validate), `BenchTomlBuilder.read_settings()` (flat dict), and scattered raw `tomllib.load()` digs — ~30 call sites.

Adding or touching a section meant hunting through several files, and every caller re-derived the path and parse/serialize step itself.

## Goal (issue frappe/pilot#128)

One object that is the single entry point for reading and writing a bench's
`bench.toml`. No change to the TOML structure or schema — a wrapper only.

## Design

`pilot/config/toml_store.py` — `BenchTomlStore`. Wraps the existing parse
(`tomllib` / `BenchConfig`) and serialize (`bench_config_to_toml` /
`write_toml`) primitives behind one interface:

| Method | Wraps | Use |
|---|---|---|
| `read(validate=True)` | `BenchConfig.from_file` / `_from_dict` | typed config; `validate=False` for half-configured files |
| `read_raw()` | `tomllib.load` | plain dict, preserves every section as written |
| `read_flat()` | `BenchTomlBuilder.read_settings` | wizard flat-key dict |
| `write(config)` | `bench_config_to_toml` + `write_text` | persist a typed config |
| `write_raw(data)` | `write_toml` | persist a raw-dict mutation |

Constructed from a bench directory or the file path directly
(`BenchTomlStore.for_bench(bench_root)` or `BenchTomlStore(toml_path)`).

### Scope decisions

- **No schema change.** `[[sites]]` and any other unmodeled section keep being
  handled via `read_raw()`/`write_raw()`, exactly as before. Lossiness of the
  typed path is out of scope for this change.
- **`BenchTomlBuilder`** keeps owning the flat-key wizard translation. Its
  `render()` is split into `build()` (returns a `BenchConfig`) so the two
  bench-creation sites write through `store.write(builder.build())` instead of
  their own `write_text`. `render()` remains for the string-only tests.
- **Lazy imports in command modules.** Command modules under `pilot/commands/`
  must not import the config layer at module load (enforced by
  `test_discovery_does_not_import_heavy_layers`), so `BenchTomlStore` is
  imported at point of use there; admin/backend modules import it normally.

## Result

Every disk read/write of `bench.toml` now goes through `BenchTomlStore`. The
parse/serialize primitives (`bench_config_to_toml`, `write_toml`,
`BenchConfig.from_file`) become internal to the store rather than called
ad hoc across the codebase.
