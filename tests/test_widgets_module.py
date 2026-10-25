"""pymui.widgets and pymui.testing, driven headlessly."""

import pymui
from pymui import (
    ColorIndex,
    Command,
    Option,
    RectCommand,
    TextCommand,
    testing,
    widgets,
)


def window(body):
    def ui(ctx):
        with ctx.window("W", 0, 0, 300, 300, Option.NOTITLE) as w:
            if w.is_open:
                body(ctx)
    return ui


def text_pos(ctx, text):
    """Position of the last-drawn `text` in the last frame."""
    hits = [c.pos for c in testing.commands(ctx) if isinstance(c, TextCommand) and c.text == text]
    assert hits, f"{text!r} not drawn"
    return hits[-1]


def click_text(ctx, ui, text):
    pos = text_pos(ctx, text)
    return testing.click(ctx, ui, pos.x + 2, pos.y + 2)


def test_progress_bar_fill_and_label():
    ctx = pymui.Context()
    ui = window(lambda ctx: (ctx.layout_row([200], 20), widgets.progress_bar(ctx, 0.25)))
    cmds = testing.run_frame(ctx, ui)
    fill = ctx.style.get_color(ColorIndex.BUTTONFOCUS)
    bars = [c.rect for c in cmds if isinstance(c, RectCommand)
            and (c.color.r, c.color.g, c.color.b) == (fill.r, fill.g, fill.b) and c.rect.h == 20]
    assert [r.w for r in bars] == [50]
    assert "25%" in testing.drawn_text(ctx)


def test_progress_bar_clamps_and_custom_text():
    ctx = pymui.Context()
    ui = window(lambda ctx: (ctx.layout_row([100], 20),
                             widgets.progress_bar(ctx, 7, 0, 5),
                             widgets.progress_bar(ctx, 1, 1, 1, text="n/a")))
    testing.run_frame(ctx, ui)
    assert {"100%", "n/a"} <= set(testing.drawn_text(ctx))


def test_listbox_selects_clicked_item():
    ctx = pymui.Context()
    state = {"sel": 0, "changed": []}

    def body(ctx):
        changed, state["sel"] = widgets.listbox(ctx, "list", ["alpha", "beta", "gamma"], state["sel"])
        state["changed"].append(changed)

    ui = window(body)
    testing.run_frame(ctx, ui)
    click_text(ctx, ui, "gamma")
    assert state["sel"] == 2
    assert any(state["changed"])


def test_tabs_switch():
    ctx = pymui.Context()
    state = {"tab": 0}

    def body(ctx):
        state["tab"] = widgets.tabs(ctx, "tabs", ["One", "Two", "Three"], state["tab"])

    ui = window(body)
    testing.run_frame(ctx, ui)
    click_text(ctx, ui, "Three")
    assert state["tab"] == 2


def test_combo_opens_below_and_selects():
    ctx = pymui.Context()
    state = {"i": 0, "changed": False}

    def body(ctx):
        ctx.layout_row([120], 0)
        changed, state["i"] = widgets.combo(ctx, "size", ["Small", "Medium", "Large"], state["i"])
        state["changed"] |= changed

    ui = window(body)
    testing.run_frame(ctx, ui)
    assert "Large" not in testing.drawn_text(ctx)
    button = text_pos(ctx, "Small")
    click_text(ctx, ui, "Small")
    testing.run_frame(ctx, ui)
    assert text_pos(ctx, "Large").y > button.y
    click_text(ctx, ui, "Large")
    testing.run_frame(ctx, ui)
    assert (state["i"], state["changed"]) == (2, True)
    assert "Medium" not in testing.drawn_text(ctx)  # popup closed


def test_combo_click_outside_closes():
    ctx = pymui.Context()
    state = {"i": 0}

    def body(ctx):
        ctx.layout_row([120], 0)
        _, state["i"] = widgets.combo(ctx, "c", ["A1", "B2"], state["i"])

    ui = window(body)
    testing.run_frame(ctx, ui)
    click_text(ctx, ui, "A1")
    testing.run_frame(ctx, ui)
    assert "B2" in testing.drawn_text(ctx)
    testing.click(ctx, ui, 250, 250)
    assert "B2" not in testing.drawn_text(ctx)
    assert state["i"] == 0


def test_menu_bar_returns_choice():
    ctx = pymui.Context()
    chosen = []
    menus = {"File": ["Open", "Quit"], "Edit": ["Undo"]}

    def body(ctx):
        result = widgets.menu_bar(ctx, menus)
        if result:
            chosen.append(result)

    ui = window(body)
    testing.run_frame(ctx, ui)
    click_text(ctx, ui, "File")
    testing.run_frame(ctx, ui)
    click_text(ctx, ui, "Quit")
    assert chosen == [("File", "Quit")]
    testing.run_frame(ctx, ui)
    assert "Open" not in testing.drawn_text(ctx)


# pymui.testing

def test_commands_skip_jumps_and_drawn_text():
    ctx = pymui.Context()
    ui = window(lambda ctx: ctx.label("hi"))
    cmds = testing.run_frame(ctx, ui)
    assert cmds and all(c.type != Command.JUMP for c in cmds)
    assert testing.drawn_text(ctx) == ["hi"]


def test_click_presses_button():
    ctx = pymui.Context()
    hits = []

    def body(ctx):
        if ctx.button("Go"):
            hits.append(1)

    ui = window(body)
    testing.run_frame(ctx, ui)
    click_text(ctx, ui, "Go")
    assert hits == [1]


def test_type_text_consumes_long_input():
    ctx = pymui.Context()
    text = [""]

    def body(ctx):
        ctx.layout_row([-1], 0)
        _, text[0] = ctx.textbox(text[0], 512, key="t")

    ui = window(body)
    testing.click(ctx, ui, 20, 10)
    long = "é" * 100 + "x" * 50  # 250 bytes
    testing.type_text(ctx, ui, long)
    assert text[0] == long


def test_sdl_event_is_public():
    ev = testing.sdl_event("motion", 3, 4)
    assert (ev.type, ev.x, ev.y) == (pymui.EventType.MOUSEMOTION, 3, 4)
