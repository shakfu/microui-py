# Code Review: microui-py (pymui) 0.3.0

Reviewed at commit `19ee4cf` with uncommitted changes to `pyproject.toml` and `uv.lock`.

## Summary

The project is in good shape. The Cython layer guards microui's `abort()` paths
well: 26 misuse probes all raised catchable Python exceptions, and none aborted
the process. The test suite passes, and `mypy` and `ruff` are clean on `src/`.

The findings below are mostly correctness edges and maintenance issues. None is a
crash. The most important is that `textbox` silently truncates input and can
store a U+FFFD replacement character in the user's string. The second is that
`get_container` fails on a fresh context with a misleading error.

| # | Severity | Area | Summary |
|---|----------|------|---------|
| 1 | Medium | `textbox_ex`, `Textbox` | Silent truncation; mid-codepoint cut stores U+FFFD |
| 2 | Medium | `get_container`, `open_popup` | Fail on a fresh context before the first `begin()` |
| 3 | Medium | CI workflow | `uv add psutil` rewrites `pyproject.toml`/`uv.lock` on every run |
| 4 | Medium | Docs | `doc/usage.md` is the upstream C manual, not a Python guide |
| 5 | Low | `renderer.c` | `assert(glGetError())` aborts in debug builds; contradicts "errors, not aborts" |
| 6 | Low | Numeric args | `Color(1.5)` silently becomes `1`; floats are truncated, not rejected |
| 7 | Low | Shipped extension | `_translate_sdl_event` test hook is in the production module |
| 8 | Low | Input | Only 5 keys are mapped; no arrows, Delete, Home/End, Tab or Escape |
| 9 | Low | Repo hygiene | 78 unused vendored SDL headers (2.5 MB) in `doc/SDL2/` |
| 10 | Low | Tests/examples | 27 ruff findings in `tests/`, `examples/`, `scripts/` |
| 11 | Info | Working tree | `twine` added to dev deps and `uv.lock` (+595 lines), uncommitted |

## Verification performed

- `.venv/bin/pytest` with `SDL_VIDEODRIVER=dummy`: **241 passed**.
- `ruff check src/`: clean. `ruff check tests/ examples/ scripts/`: 27 findings (see #10).
- `mypy src/`: no issues.
- The compiled `pymui.abi3.so` is newer than `pymui.pyx`, `microui.c` and `renderer.c`, so the tests ran against current sources.
- Wrote 26 misuse probes (each in its own subprocess, to catch aborts). Results are summarized under "Checked and sound".
- Reproduced findings 1, 2 and 6 with small scripts.

Limits: this is macOS, CPython 3.13 only. I did not exercise the GL renderer on screen, fuzz the font loader, or run the GitHub workflows. I could not confirm that the action versions referenced in the workflows (for example `actions/checkout@v7`, `upload-artifact@v7`) exist.

---

## Findings

### 1. Medium: `textbox` truncates silently and can corrupt UTF-8 text

`src/pymui/pymui.pyx:978`, `:994`, and `Textbox.text` setter at `:1819`.

`textbox_ex` cuts the encoded input at `bufsz - 1` bytes without regard to
character boundaries, then decodes with `errors='replace'`. The result is that
a multi-byte character cut in half becomes U+FFFD.

Reproduction:

```python
ctx.textbox('éééé', 6)   # -> (0, 'éé\ufffd')
ctx.textbox('héllo wörld', 8)   # -> (0, 'héllo ')   # silent truncation
```

The caller stores the returned string back, so the replacement character becomes
permanent after one frame.

**Recommendation:** cut on a UTF-8 boundary, as `_flush_text` already does for
input. Consider raising or returning a flag when the text does not fit. At minimum,
document that the returned text may be shorter than the input.

### 2. Medium: `get_container` and `open_popup` fail on a fresh context

`src/pymui/pymui.pyx:608-611` (`_require_pool_slot`) and `:1149` (`get_container`).

`_require_pool_slot` treats a pool slot as free when `last_update < frame`. On a
new context `frame == 0` and every slot has `last_update == 0`, so no slot is
free and the call raises "more than 48 containers in use in one frame". That
message is wrong, and the failure is only avoided by calling `begin()` first.

Reproduction:

```python
c = pymui.Context()
c.get_container('z')   # RuntimeError: more than 48 containers in use in one frame
```

Unlike `_begin_root`, `get_container` and `open_popup` do not call `_require_frame()`,
so the behaviour is inconsistent with the rest of the API.

**Recommendation:** either call `_require_frame()` in both methods and raise
"must be called between begin() and end()", or fix the free-slot rule so that
never-used slots count as free. The first option matches the other container
APIs.

### 3. Medium: CI modifies the lock file on every run

`.github/workflows/memory-leak-detection.yml:52` and `:145` run `uv add psutil`.

`psutil` is already in `[dependency-groups] dev`, so the step does nothing useful
except rewrite `pyproject.toml` and `uv.lock`. The leak-detection job therefore
tests against dependencies that were not reviewed or committed. `uv sync --dev`
is also not run with `--locked` or `--frozen`.

**Recommendation:** delete both `uv add psutil` steps and use `uv sync --dev --locked`.

### 4. Medium: `doc/usage.md` is the upstream C manual

`doc/usage.md` documents the C API with C snippets such as
`mu_textbox(ctx, buf, sizeof(buf))` and `mu_layout_row(ctx, 3, (int[]){...}, 0)`.
A Python user reading `doc/` will find no Python usage guide. The README covers
the Python API, but `doc/` points to the C manual.

**Recommendation:** mark the file as upstream C reference, or replace it with a
Python-oriented usage guide.

### 5. Low: `assert(glGetError() == 0)` in the renderer

`microui/sdl/renderer.c:278`.

With `NDEBUG` (the default for the wheel's Release build) the check, including the
`glGetError()` call, is compiled out, so it does nothing. In a debug build it
aborts the process on any GL error during init. That conflicts with the project's
"raise, don't abort" policy.

**Recommendation:** check the error and return `-1`. `renderer_init_window` already
turns that into a `RuntimeError`.

### 6. Low: numeric arguments are truncated, not rejected

`Color(1.5, 0, 0)` returns `Color(1, 0, 0, 255)`. The same applies to `Vec2`, `Rect`
and the `int` parameters of most methods. Cython coerces floats to `int` silently.

**Recommendation:** accept only `numbers.Integral` (or use `operator.index`) in the
constructors and setters, as `Textbox.__cinit__` already does with `operator.index`.

### 7. Low: test hook in the shipped module

`src/pymui/pymui.pyx:1965` `_translate_sdl_event` is compiled into the wheel. It
is underscore-prefixed and not exported from `__init__.py`, but it is still
reachable as `pymui.pymui._translate_sdl_event`. Its docstring says it bypasses
the SDL queue because of a bug in the sdl2-compat shim.

**Recommendation:** move the hook into a test-only helper, or at least document
that it is internal. The sdl2-compat comment also suggests local macOS builds may
link sdl2-compat rather than the SDL2 2.32.10 that the wheels bundle. Worth
confirming which library `find_package(SDL2)` picks up locally.

### 8. Low: limited keyboard mapping

`_map_key` (`pymui.pyx`, near `_translate`) maps only Shift, Ctrl, Alt, Return and
Backspace. There is no way to move the caret with arrows, delete forward, use
Home/End, or Tab between widgets, and Escape is unavailable to applications. This
is a usability gap in `App`, not a correctness bug.

**Recommendation:** expose more `Key` values or pass the raw keycode to
applications through `Event.keycode`, which already exists.

### 9. Low: vendored headers not used by the build

`doc/SDL2/` holds 78 SDL2 headers (2.5 MB). The build resolves SDL through
`find_package(SDL2)` and the include paths `microui/` and `microui/sdl/`. Nothing
includes `doc/SDL2`.

**Recommendation:** delete the directory, or document why it is there.

### 10. Low: lint findings outside `src/`

`ruff check tests/ examples/ scripts/` reports 27 issues: unused locals (F841, 16),
unused imports (F401, 7, mostly `hypothesis`), module-level imports after code
(E402, 3), and one bare `except` (E722, `tests/test_memory_safety.py:226`). None affects behaviour,
but a clean ruff run would make regressions easier to see.

### 11. Info: uncommitted changes

`pyproject.toml` adds `twine>=7.0.0` to dev dependencies. `uv.lock` gains 595 lines
to match. This is probably intended, but it is not committed.

---

## Checked and sound

- **Textbox IDs.** microui's `mu_get_id` hashes the bytes that the pointer
  parameter points to, not the pointer's address. `mu_textbox_ex` therefore hashes
  the buffer pointer value, which is unique per `Textbox`. I tested two boxes in one
  window: typing into one leaves the other unchanged. The `Textbox` comment is
  correct.
- **Slider, number and checkbox IDs.** These hash the value pointer, which is a
  fixed slot, so they all share a base ID. `push_id(key)` disambiguates them. This
  is handled correctly.
- **Misuse guards.** These all raise catchable exceptions without aborting: nested
  panels past the layout limit, unbalanced `pop_clip_rect`, `draw_*` outside a
  window, a 1 MB textbox, invalid slider formats, duplicate IDs, too many containers,
  input-text flooding, out-of-range icons, `end()` without `begin()`, `render()`
  without a window, and `next_command()` during a frame.
- **Input buffering.** `_flush_text` cuts on a UTF-8 boundary, and `mu_end` clears
  microui's input buffer, so the pending-text queue is consistent.
- **Glyph cache.** `glyph_cache_reset` calls `flush()` before clearing the atlas, so
  queued quads are drawn with the old texture. `utf8_decode` never reads past a NUL
  and rejects overlong and surrogate sequences.
- **Font loading.** Failed loads leave the previous font in place. The table-directory
  bounds check runs before `stbtt_InitFont`. The docs state that the loader does not
  validate tables; that caveat is accurate.
- **Frame lifecycle.** `abort_frame` resets every stack, and `Window.__exit__` and
  `Context.__exit__` both run on exceptions.
- **Build.** `mypy src/` is clean, and `pymui.abi3.so` is up to date.

## Suggested order of work

1. Fix #1 (textbox truncation). It silently changes user data.
2. Fix #2 and make the container APIs consistent with the frame check.
3. Remove the `uv add psutil` steps (#3) and use `--locked` in CI.
4. Replace the `assert` in the renderer (#5) and the float truncation (#6).
5. Tidy up: #4, #7, #9, #10.
