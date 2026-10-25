# Changelog

## [Unreleased]

### Added

- `Key.ESCAPE`, `DELETE`, `LEFT`, `RIGHT`, `UP`, `DOWN`, `HOME`, `END` and `TAB`. SDL key events map to them, so applications can test `ctx.key_pressed` instead of raw keycodes.

- Textbox caret and selection. Left/Right, Home/End and clicks move the caret; Shift extends the selection, as does a mouse drag, which continues past the box edge. Typing, Backspace and Delete replace the selection. `ctx.input_select_all()`.

- Clipboard: `ctx.input_copy()`, `input_cut()`, `input_paste()`, `get_clipboard_text()`, `set_clipboard_text()`. Copy and cut take the selection. `App` maps Ctrl+A/C/X/V, or Cmd on macOS. Without SDL video the clipboard is a process-local string, so headless tests work.

- Tab and Shift+Tab cycle focus through the frame's textboxes in call order. Code that already handled Tab sees both effects.

- Images: `pymui.Image` uploads RGBA pixels to a texture; `ctx.image()` and `ctx.draw_image()` draw it. Closing the window invalidates every `Image`; using one afterwards raises instead of drawing a stale texture.

- HiDPI. Coordinates stay in logical pixels; the renderer scales to the drawable and rasterizes loaded fonts at device resolution. `renderer_get_scale()` returns the ratio. Rendering was checked at scale 2 (see `doc/development.md`); mouse input was not.

- `App(idle_timeout=...)` redraws only after input or once per timeout, instead of continuously. One extra frame follows each input, because microui settles hover and popups a frame late. `app.redraw()` requests a frame; `wait_event()` is the underlying call.

- Events: horizontal and flipped wheel scrolling, `Event.clicks`, `Event.mod` with `Mod` bits, `EventType.DROPFILE`, `FOCUS_GAINED` and `FOCUS_LOST`. `App.drop_file(path)` and `app.focused` expose the last three. `set_cursor(Cursor.*)`.

- `pymui.widgets`: `menu_bar`, `tabs`, `combo`, `listbox`, `progress_bar`, in pure Python over the custom-widget API. Menus and combo lists open below their button, not at the mouse as microui popups do.

- `pymui.testing`: headless `click`, `press`, `type_text`, `run_frame`, `drawn_text`, and `sdl_event`, the former private `_translate_sdl_event` hook. `make test-window` adds tests that need a GL window.

- `examples/desktop_demo.py`.

### Fixed

- Text that does not fit a textbox is cut at a character boundary. `textbox`, `Textbox.text` and microui's typed-input copy all cut by byte count. A split multi-byte character was decoded as U+FFFD, and the caller stored that back into its text.

- `get_container` and `open_popup` work on a new `Context`. microui treats a pool slot as free when `last_update < frame`, so at frame 0 no slot was free. The guard raised "more than 48 containers in use". The frame counter now starts at 1. Requiring `begin()` first was the alternative, but it would break the supported use of `get_container` after a frame ends.

- The renderer returns an error on a GL error during window init, so `renderer_init_window` raises `RuntimeError`. Previously an `assert` aborted debug builds, and Release builds skipped the check.

- The leak-detection workflow ran `uv add psutil`. That added psutil to the runtime dependencies and rewrote `uv.lock`. It now runs `uv sync --dev --locked`.

### Removed

- `doc/SDL2/`: 78 vendored SDL2 headers that no build path used. The build finds SDL through `find_package(SDL2)`.

### Changed

- Custom renderers must handle `Command.IMAGE`. `Command.MAX` rose by one.

- `App` scrolls horizontally on horizontal wheel input; `Event.x` of `MOUSEWHEEL` was always 0.

- The vendored microui has more pymui patches: textbox editing, caret and selection fields in `mu_Context`, and `MU_COMMAND_IMAGE`. C code built against `microui.h` must be rebuilt.

- `twine` is a dev dependency, for `make check` and `make publish-test`.

- README documents float truncation in `Vec2`/`Rect`/`Color`, textbox cut behaviour, and `Event.keycode` for keys microui does not define. `doc/usage.md` is marked as the upstream C manual.

## [0.3.0]

### Added

- `.github/workflows/wheels.yml` builds abi3 wheels for CPython 3.12+ with cibuildwheel: Linux x86_64/aarch64 (manylinux), macOS x86_64/arm64, Windows AMD64. A tag push attaches the wheels and sdist to a GitHub release, with notes from this file; PyPI uploads are manual. `scripts/build_sdl2.sh` builds SDL2 2.32.10 from a hash-checked tarball, linked statically so wheels need no system SDL2. Python 3.10 and 3.11 install from the sdist.

- `pymui.poll_event()` returns the next window event as a `pymui.Event`, or `None`. `EventType` names the translated kinds; other SDL events are dropped.

- `App(max_fps=120)` caps the frame rate after each render. Drivers and compositors may ignore the vsync request; with vsync forced off, the showcase ran at 2,099 fps using 47% of a core, and at 117 fps and 5% with the cap. The default is 120 rather than 60 so a working vsync on high-refresh displays is not halved. `max_fps=None` disables it. A late frame restarts the schedule instead of triggering catch-up frames.

- `pymui.load_font(path_or_bytes, size)`, `reset_font()` and `font_loaded()`: render and measure text with any TrueType/OpenType font, via vendored stb_truetype v1.26. The bundled bitmap font covers ASCII only and draws other characters as a box. Glyphs rasterize on first use into the renderer's texture, now 512x512 and shared with the icons. stb_truetype was chosen over SDL2_ttf to avoid a new system library dependency. It does not validate font tables, so only trusted files should be loaded; pymui rejects data whose table directory points past its end.

- `examples/showcase.py` (`make showcase`): a tour of the API, including live triggering of each guarded error. `tests/test_examples.py` runs it and `examples/demo.py` headless.

- `pymui.app.App`: SDL window, event translation, and render loop. Subclass and override `frame(ctx)`, or pass a callable to `run()`. The demo (`make demo`) now uses it.

- `pymui.render(ctx, bg)` draws the command list in C, with no per-command Python objects. Added `renderer_init_window(title, width, height, resizable)`, `renderer_resize()` and `renderer_shutdown()`. The renderer now requests vsync; it previously busy-looped at 100% CPU.

- Context managers `treenode`, `popup`, `panel`, `column` and `id_scope`. Each calls its `end_*` function even if the body raises.

- Custom-widget primitives: `update_control`, `draw_control_frame`, `draw_control_text`, `bring_to_front`, and read-only `hover`, `focus`, `last_id`, `mouse_pos`, `mouse_delta`, `mouse_down`, `mouse_pressed`, `key_down`, `key_pressed`, `in_frame`.

- `key=` argument on `button`, `checkbox`, `slider`, `number`, `textbox`, `textbox_ex`. Settable `ContainerWrapper.rect`, `.scroll`, `.open`; new `.zindex`.

- `DuplicateIDError`, raised when two widgets in one frame resolve to the same ID, or a window is begun twice. Shared IDs make widgets share hover, focus and clicks. A repeated window overwrites its head jump and silently drops the first instance's content.

### Changed

- `pymui.app` no longer depends on pysdl2, and `App.handle_event` takes a `pymui.Event` instead of an `sdl2.SDL_Event`. pysdl2 loads its own SDL2 through ctypes. With SDL2 inside the wheel, the window would live in one SDL instance while `App` polled events from the other, so no input arrived. `renderer_init_window()` now initializes SDL video, and `renderer_shutdown()` calls `SDL_Quit()`.

- CMake locates SDL2 and OpenGL with `find_package` (SDL2's CMake config) instead of the Homebrew prefix and `-lSDL2`. GCC/Clang-only flags are skipped under MSVC.

- The distribution is renamed from `pymui` to `microui-py`, because `pymui` on PyPI belongs to an unrelated project. The import name stays `pymui`; `pyproject.toml` sets `wheel.packages` because scikit-build-core would otherwise look for `src/microui_py`.

- Renderer text is decoded as UTF-8, with malformed sequences drawn as U+FFFD. Previously each non-ASCII lead byte mapped to the box glyph and continuation bytes were skipped, so a cut sequence could be measured and drawn inconsistently.

- `renderer_draw_rect/text/icon`, `renderer_set_clip_rect`, `renderer_clear` and `renderer_present` raise `RuntimeError` without a window; they issued GL calls with no context. `renderer_get_text_width`'s `length` is optional and counts UTF-8 bytes.

- CI tests Python 3.13 and installs `fonts-dejavu-core` for the font tests.

- `CMakeLists.txt` no longer declares a project version; it said 1.4.8 while the package was 0.2.0. `pyproject.toml` is the only source.

- `slider`, `number` and `textbox` default IDs come from the calling code location plus an occurrence count within the current ID scope. A per-window call-order counter was the alternative; it shifts every later ID when a widget above appears or disappears.

- Calls that microui would `abort()` on, or that read past a stack, now raise. See the README table "Errors Instead of Aborts". This covers widget calls outside a window, mismatched `end_*`/`pop_*` calls, stack and pool limits, and a full command buffer. `end_*` calls are matched against a Python-side scope stack, so mismatches are caught before they unbalance microui's stacks.

- `begin()` twice, `end()` without `begin()`, and `next_command()` during a frame raise `RuntimeError`.

- `input_text()` queues text beyond microui's 31-byte per-frame buffer for later frames. microui aborts on overflow, which several SDL text events in one frame could trigger.

- `Color` channels outside 0..255 raise `ValueError`; they wrapped modulo 256 (`Color(300)` gave `r=44`).

- `draw_text(text, pos, color)` drops the unused `font` argument. It now queues a command; before, it drew immediately, outside the command list and clip rect.

- `textbox(text, bufsz=256, opt=0, key=None)` returns `(result, text)`. It was a stub that drew nothing and returned `0`.

- `button` with an empty label takes its ID from `icon`, as microui intends; the wrapper passed `""`, so all icon buttons shared one ID.

- `layout_row` accepts at most 16 widths (`MU_MAX_WIDTHS`), not 1000.

- `begin_panel` rejects `Option.CLOSED`, which made microui dereference NULL.

- Demos moved from `tests/` to `examples/` (`pymui_sdl_demo.py` is now `examples/demo.py`). Removed 16 debug scripts from `tests/` that contained no assertions; several opened an SDL window during collection, and `test_minimal.py` did so at import time, leaving a window open for the whole session.

- CI runs `pytest` against the built wheel. Tests and `scripts/memory_leak_test.py` no longer prepend `src/` to `sys.path`, so they import the installed package. CI steps use `uv run --no-sync`: a plain `uv run` reinstalled the editable project over the wheel, so the leak checks never exercised what ships.

- The property-based and performance suites run under `make test`; the `test-safe` and `test-all` targets are removed. The performance test now fails when a benchmark raises; it previously skipped it.

### Fixed

- `slider`, `number` and `checkbox` without a surrounding `push_id` shared one widget ID. microui derives their IDs from the value pointer, which was a C stack local at the same address on every call. Dragging one slider moved every slider in the window. `textbox_ex` hashed a freshly allocated buffer, so it lost focus every frame.

- An exception inside a window aborted the process: `Context.__exit__` called `mu_end()`, which asserts all stacks are empty. It now calls the new `abort_frame()`, which resets the stacks and drops the frame's commands.

- `slider`/`number` passed `fmt` to microui's `sprintf` into a 128-byte buffer. A format such as `"%s"` or `"%200f"` corrupted memory. `fmt` must now contain one `%f`/`%e`/`%g` conversion, with width <= 99, precision <= 20 and at most 32 bytes.

- `Style` and `ContainerWrapper` kept raw pointers into the `Context` without a reference, so they read freed memory once the context was collected. `TextCommand` read its string from the command buffer, which the next frame overwrites; it now copies on creation.

- `Context.__new__(Context)`, or a subclass skipping `__init__`, left a NULL pointer that segfaulted on use. Allocation moved to `__cinit__`. An unbound `Style` raises `ValueError` instead of dereferencing NULL.

- `clamp()` rounded floats to 32 bits through a C `float` fused type.

- `Textbox(n)` with `n` outside the C int range raised `OverflowError`; it now raises `ValueError` like other invalid sizes.

- Encoding errors in `text()` and `begin_window()` raised `TypeError`: the handler constructed `UnicodeEncodeError` with one argument, but the constructor requires five.

- `scripts/memory_leak_test.py` called `text()` outside a window and swallowed every exception, so failed iterations still reported "no leaks". Errors now propagate.

- `scripts/memory_leak_test.py --threshold` was parsed but ignored; every check used a hard-coded 50 MB. It now applies, with its documented default of 5 MB. Measured growth is under 1 MB per scenario at 2000 iterations.

- `microui/sdl/demo/build.sh` pointed at `../src/microui.c`, which does not exist; it now builds from `../renderer.c` and `../../microui.c`.

- Added OpenGL linking (`-lGL`) for Linux in `microui/sdl/CMakeLists.txt`

- Added `-fPIC` compile option to `microui` and `microui_sdl` libraries to support building shared libraries

- Updated `Makefile` to use `uv pip install -e .` for building, which properly integrates with scikit-build-core

- Added `install(TARGETS pymui DESTINATION pymui)` to `src/CMakeLists.txt`. Without an install rule scikit-build-core staged nothing, so `uv build` produced a wheel containing only the Python files: `import pymui` then failed with `No module named 'pymui.pymui'`. Every local workflow uses `uv pip install -e .`, whose redirecting finder points at the build tree, so the gap only appeared when CI installed the wheel itself.
