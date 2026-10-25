"""App event translation, driven by synthetic events (no window needed)."""

import pytest

import pymui
from pymui import Event, EventType, Key, Mouse, testing
from pymui.app import App
from pymui.testing import sdl_event as translate

# SDL2 ABI values for building raw events.
SDL_BUTTON_RIGHT = 3
SDL_BUTTON_X1 = 4
SDLK_LSHIFT = 0x400000E1
SDLK_KP_ENTER = 0x40000058
SDL_WINDOWEVENT_MOVED = 4
SDL_WINDOWEVENT_SIZE_CHANGED = 6


def test_mouse_events():
    app = App()
    app.handle_event(Event(EventType.MOUSEMOTION, 12, 34))
    assert (app.ctx.mouse_pos.x, app.ctx.mouse_pos.y) == (12, 34)
    app.handle_event(Event(EventType.MOUSEDOWN, 12, 34, button=Mouse.RIGHT))
    assert app.ctx.mouse_down == Mouse.RIGHT
    assert app.ctx.mouse_pressed == Mouse.RIGHT
    app.handle_event(Event(EventType.MOUSEUP, 12, 34, button=Mouse.RIGHT))
    assert app.ctx.mouse_down == 0


def test_unmapped_button_ignored():
    app = App()
    app.handle_event(Event(EventType.MOUSEDOWN, button=0))
    assert app.ctx.mouse_down == 0


def test_key_events():
    app = App()
    app.handle_event(Event(EventType.KEYDOWN, key=Key.SHIFT))
    app.handle_event(Event(EventType.KEYDOWN, key=Key.RETURN))
    assert app.ctx.key_down == Key.SHIFT | Key.RETURN
    app.handle_event(Event(EventType.KEYUP, key=Key.SHIFT))
    assert app.ctx.key_down == Key.RETURN
    app.handle_event(Event(EventType.KEYDOWN, keycode=ord("a")))
    assert app.ctx.key_down == Key.RETURN


def test_text_input_reaches_focused_textbox():
    app = App()
    ctx = app.ctx
    text = [""]
    r = pymui.Rect(10, 10, 100, 20)

    def ui():
        with ctx:
            with ctx.window("W", 0, 0, 200, 100, pymui.Option.NOTITLE):
                ctx.layout_set_next(r, 0)
                _, text[0] = ctx.textbox(text[0], key="t")

    ctx.input_mousemove(20, 20)
    ui()
    ui()
    ctx.input_mousedown(20, 20, Mouse.LEFT)
    ui()
    ctx.input_mouseup(20, 20, Mouse.LEFT)
    app.handle_event(Event(EventType.TEXT, text="h\u00e9"))
    ui()
    assert text[0] == "h\u00e9"


def test_quit_and_resize():
    app = App(width=640, height=480)
    app.running = True
    app.handle_event(Event(EventType.RESIZE, 1024, 768))
    assert (app.width, app.height) == (1024, 768)
    app.handle_event(Event(EventType.QUIT))
    assert app.running is False


def fields(ev):
    return (ev.type, ev.x, ev.y, ev.button, ev.key, ev.keycode, ev.text)


@pytest.mark.parametrize(
    "raw, expected",
    [
        (("motion", 12, 34), (EventType.MOUSEMOTION, 12, 34, 0, 0, 0, "")),
        (("down", SDL_BUTTON_RIGHT, 5, 6), (EventType.MOUSEDOWN, 5, 6, Mouse.RIGHT, 0, 0, "")),
        (("up", SDL_BUTTON_X1, 5, 6), (EventType.MOUSEUP, 5, 6, 0, 0, 0, "")),
        (("wheel", -2), (EventType.MOUSEWHEEL, 0, -2, 0, 0, 0, "")),
        (("keydown", SDLK_LSHIFT), (EventType.KEYDOWN, 0, 0, 0, Key.SHIFT, SDLK_LSHIFT, "")),
        (("keyup", SDLK_KP_ENTER), (EventType.KEYUP, 0, 0, 0, Key.RETURN, SDLK_KP_ENTER, "")),
        (("keydown", ord("a")), (EventType.KEYDOWN, 0, 0, 0, 0, ord("a"), "")),
        (("window", SDL_WINDOWEVENT_SIZE_CHANGED, 1024, 768), (EventType.RESIZE, 1024, 768, 0, 0, 0, "")),
        (("quit",), (EventType.QUIT, 0, 0, 0, 0, 0, "")),
    ],
)
def test_sdl_event_translation(raw, expected):
    assert fields(translate(*raw)) == expected


@pytest.mark.parametrize(
    "sym, key",
    [
        (27, Key.ESCAPE),
        (127, Key.DELETE),
        (0x40000050, Key.LEFT),
        (0x4000004F, Key.RIGHT),
        (0x40000052, Key.UP),
        (0x40000051, Key.DOWN),
        (0x4000004A, Key.HOME),
        (0x4000004D, Key.END),
        (9, Key.TAB),
    ],
)
def test_navigation_keys_mapped(sym, key):
    assert translate("keydown", sym).key == key
    app = App()
    app.handle_event(translate("keydown", sym))
    assert app.ctx.key_down == key
    assert app.ctx.key_pressed == key


def test_key_bits_distinct():
    names = [n for n in dir(Key) if n.isupper()]
    bits = [getattr(Key, n) for n in names]
    assert len(set(bits)) == len(bits) == 14
    assert all(b and b & (b - 1) == 0 for b in bits)


def test_sdl_text_translation():
    assert translate("text", text="h\u00e9".encode()).text == "h\u00e9"
    assert translate("text", text=b"\xff").text == "\ufffd"
    assert translate("text", text=b"x" * 100).text == "x" * 31


def test_untranslated_sdl_event_dropped():
    assert translate("window", SDL_WINDOWEVENT_MOVED, 1, 2) is None


def test_default_bg_not_shared():
    a, b = App(), App()
    a.bg.r = 0
    assert b.bg.r == 90


class FakeClock:
    def __init__(self):
        self.now = 100.0
        self.slept = []

    def perf_counter(self):
        return self.now

    def sleep(self, dt):
        self.slept.append(round(dt, 6))
        self.now += dt


def test_frame_rate_cap(monkeypatch):
    import pymui.app

    clock = FakeClock()
    monkeypatch.setattr(pymui.app.time, "perf_counter", clock.perf_counter)
    monkeypatch.setattr(pymui.app.time, "sleep", clock.sleep)
    app = App(max_fps=100)  # 10 ms per frame
    app._limit_rate()  # first frame: schedule only
    assert clock.slept == []
    clock.now += 0.002  # fast frame: wait out the slot
    app._limit_rate()
    assert clock.slept == [0.008]
    clock.now += 0.004
    app._limit_rate()
    assert clock.slept == [0.008, 0.006]  # cadence kept, no drift
    clock.now += 0.050  # slow frame: no sleep, schedule restarts
    app._limit_rate()
    assert clock.slept == [0.008, 0.006]
    clock.now += 0.001
    app._limit_rate()
    assert clock.slept[-1] == 0.009


def test_frame_rate_cap_disabled_and_validated(monkeypatch):
    import pymui.app

    clock = FakeClock()
    monkeypatch.setattr(pymui.app.time, "perf_counter", clock.perf_counter)
    monkeypatch.setattr(pymui.app.time, "sleep", clock.sleep)
    app = App(max_fps=None)
    for _ in range(3):
        app._limit_rate()
    assert clock.slept == []
    for bad in (0, -5):
        with pytest.raises(ValueError):
            App(max_fps=bad)
        with pytest.raises(ValueError):
            app.max_fps = bad


SDL_WINDOWEVENT_FOCUS_GAINED = 12
SDL_WINDOWEVENT_FOCUS_LOST = 13
SDL_MOUSEWHEEL_FLIPPED = 1
KMOD_LCTRL = 0x0040


def test_wheel_horizontal_and_flipped():
    ev = translate("wheel", 1, 3)
    assert (ev.x, ev.y) == (3, 1)
    ev = translate("wheel", 1, 3, SDL_MOUSEWHEEL_FLIPPED)
    assert (ev.x, ev.y) == (-3, -1)


def test_double_click_count():
    assert translate("down", 1, 5, 6, d=2).clicks == 2


def test_key_modifiers():
    ev = translate("keydown", ord("c"), KMOD_LCTRL)
    assert ev.mod & pymui.Mod.CTRL
    assert not ev.mod & pymui.Mod.SHIFT


def test_drop_file_event():
    ev = translate("drop", text=b"/tmp/a b.txt")
    assert (ev.type, ev.text) == (EventType.DROPFILE, "/tmp/a b.txt")


@pytest.mark.parametrize(
    "code, kind",
    [(SDL_WINDOWEVENT_FOCUS_GAINED, EventType.FOCUS_GAINED),
     (SDL_WINDOWEVENT_FOCUS_LOST, EventType.FOCUS_LOST)],
)
def test_focus_events(code, kind):
    assert translate("window", code).type == kind


def test_app_horizontal_scroll():
    app = App()
    ctx = app.ctx

    def ui(ctx):
        with ctx.window("S", 0, 0, 100, 100) as w:
            if w.is_open:
                ctx.layout_row([400], 400)
                ctx.label("wide")

    ctx.input_mousemove(50, 50)
    testing.run_frame(ctx, ui)
    testing.run_frame(ctx, ui)
    app.handle_event(Event(EventType.MOUSEWHEEL, 2, -1))
    testing.run_frame(ctx, ui)
    scroll = ctx.get_container("S").scroll
    assert scroll.x > 0 and scroll.y > 0


def test_app_drop_and_focus():
    dropped = []

    class MyApp(App):
        def drop_file(self, path):
            dropped.append(path)

    app = MyApp()
    app.handle_event(Event(EventType.DROPFILE, text="/x"))
    app.handle_event(Event(EventType.FOCUS_LOST))
    assert dropped == ["/x"] and app.focused is False
    app.handle_event(Event(EventType.FOCUS_GAINED))
    assert app.focused is True


def test_idle_step_waits_only_when_no_redraw_is_due(monkeypatch):
    import pymui.app as app_mod

    waits, frames = [], []
    queue = []
    monkeypatch.setattr(app_mod, "render", lambda ctx, bg: None)
    monkeypatch.setattr(app_mod, "poll_event", lambda: queue.pop(0) if queue else None)

    def fake_wait(timeout):
        waits.append(timeout)
        return Event(EventType.MOUSEMOTION, 1, 1) if len(waits) == 2 else None

    monkeypatch.setattr(app_mod, "wait_event", fake_wait)
    app = App(idle_timeout=0.25, max_fps=None)

    def frame(ctx):
        frames.append(1)

    app.step(frame)  # first frame: no wait
    assert waits == []
    app.step(frame)  # waits, times out, draws anyway
    assert waits == [0.25]
    app.step(frame)  # waits, gets input
    app.step(frame)  # settle frame after input: no wait
    assert waits == [0.25, 0.25]
    app.redraw()
    app.step(frame)
    assert waits == [0.25, 0.25]
    app.step(frame)
    assert waits == [0.25, 0.25, 0.25]
    assert len(frames) == 6


def test_continuous_step_never_waits(monkeypatch):
    import pymui.app as app_mod

    monkeypatch.setattr(app_mod, "render", lambda ctx, bg: None)
    monkeypatch.setattr(app_mod, "wait_event", lambda t: pytest.fail("waited"))
    app = App(max_fps=None)
    app.step(lambda ctx: None)
    app.step(lambda ctx: None)
