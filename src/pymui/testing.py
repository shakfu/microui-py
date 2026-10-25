"""Drive a UI headlessly: feed input, run frames, inspect the command list.

No window is needed. `ui(ctx)` builds the UI and is called inside each frame.

    from pymui import testing

    def ui(ctx):
        with ctx.window("W", 0, 0, 200, 100) as win:
            if win.is_open and ctx.button("OK"):
                clicked.append(True)

    testing.click(ctx, ui, 100, 40)
    assert "OK" in testing.drawn_text(ctx)

microui finds the hovered window one frame late, and the hovered control
the frame after, so `click` runs two frames before pressing the button.
"""

from __future__ import annotations

from collections.abc import Callable

from .pymui import Command, Context, Event, Mouse, TextCommand, _translate_sdl_event

UI = Callable[[Context], None]


def sdl_event(kind: str, a: int = 0, b: int = 0, c: int = 0, text: bytes = b"",
              d: int = 0) -> Event | None:
    """Translate a synthetic SDL event as `poll_event()` would.

    kind and arguments:
        "quit"
        "motion": a=x, b=y
        "down" / "up": a=SDL button, b=x, c=y, d=clicks
        "wheel": a=y, b=x, c=direction (1: flipped)
        "keydown" / "keyup": a=SDL keycode, b=SDL modifier mask
        "text": text=UTF-8 bytes (at most 31)
        "drop": text=path bytes
        "window": a=SDL_WINDOWEVENT_* code, b=data1, c=data2
    """
    return _translate_sdl_event(kind, a, b, c, text, d)


def run_frame(ctx: Context, ui: UI) -> list:
    """Run one frame and return its commands."""
    with ctx:
        ui(ctx)
    return commands(ctx)


def commands(ctx: Context) -> list:
    """Commands of the last finished frame, in draw order, without jumps."""
    ctx.reset_command_iterator()
    out = []
    while (cmd := ctx.next_command()) is not None:
        if cmd.type != Command.JUMP:
            out.append(cmd)
    return out


def drawn_text(ctx: Context) -> list[str]:
    """Strings drawn by the last finished frame."""
    return [c.text for c in commands(ctx) if isinstance(c, TextCommand)]


def click(ctx: Context, ui: UI, x: int, y: int, button: int = Mouse.LEFT) -> list:
    """Move to (x, y), press and release `button`; return the last frame's commands."""
    ctx.input_mousemove(x, y)
    run_frame(ctx, ui)
    run_frame(ctx, ui)
    ctx.input_mousedown(x, y, button)
    run_frame(ctx, ui)
    ctx.input_mouseup(x, y, button)
    return run_frame(ctx, ui)


def press(ctx: Context, ui: UI, key: int) -> list:
    """Press and release `Key` `key` over one frame each."""
    ctx.input_keydown(key)
    run_frame(ctx, ui)
    ctx.input_keyup(key)
    return run_frame(ctx, ui)


def type_text(ctx: Context, ui: UI, text: str) -> list:
    """Type `text` and run frames until microui has consumed it."""
    ctx.input_text(text)
    result = run_frame(ctx, ui)
    # Text beyond microui's 31-byte buffer carries into later frames, at
    # least 28 bytes per frame after cutting on a UTF-8 boundary.
    for _ in range(len(text.encode("utf-8")) // 28):
        result = run_frame(ctx, ui)
    return result
