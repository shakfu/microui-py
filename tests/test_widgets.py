"""Widget IDs, scoped context managers, custom-widget primitives, frame recovery."""

import gc

import pytest

import pymui
from pymui import Mouse, Rect, Result, Vec2

ABS = 0  # layout_set_next: absolute screen coordinates


class Harness:
    """Run frames of `ui(ctx)` inside one untitled window covering (0,0)-(400,300)."""

    def __init__(self, ui):
        self.ctx = pymui.Context()
        self.ui = ui

    def frame(self):
        ctx = self.ctx
        with ctx:
            with ctx.window("W", 0, 0, 400, 300, pymui.Option.NOTITLE) as win:
                if win.is_open:
                    self.ui(ctx)

    def click(self, x, y):
        ctx = self.ctx
        ctx.input_mousemove(x, y)
        self.frame()
        self.frame()  # hover root is resolved one frame late
        ctx.input_mousedown(x, y, Mouse.LEFT)
        self.frame()
        ctx.input_mouseup(x, y, Mouse.LEFT)
        self.frame()

    def drag(self, x0, x1, y):
        ctx = self.ctx
        ctx.input_mousemove(x0, y)
        self.frame()
        self.frame()
        ctx.input_mousedown(x0, y, Mouse.LEFT)
        self.frame()
        ctx.input_mousemove(x1, y)
        self.frame()
        ctx.input_mouseup(x1, y, Mouse.LEFT)
        self.frame()


ROW = [Rect(10, 10 + 30 * i, 200, 20) for i in range(3)]


def test_sliders_without_keys_are_independent():
    vals = [10.0, 10.0]

    def ui(ctx):
        for i in range(2):
            ctx.layout_set_next(ROW[i], ABS)
            _, vals[i] = ctx.slider(vals[i], 0, 100)

    h = Harness(ui)
    h.drag(100, 190, ROW[1].y + 10)
    assert vals[0] == 10.0
    assert vals[1] > 80


def test_numbers_without_keys_are_independent():
    vals = [5.0, 5.0]

    def ui(ctx):
        for i in range(2):
            ctx.layout_set_next(ROW[i], ABS)
            _, vals[i] = ctx.number(vals[i], 1.0)

    h = Harness(ui)
    h.drag(100, 140, ROW[0].y + 10)
    assert vals[0] > 5.0
    assert vals[1] == 5.0


def test_checkboxes_are_independent():
    states = [0, 0]

    def ui(ctx):
        for i in range(2):
            ctx.layout_set_next(ROW[i], ABS)
            _, states[i] = ctx.checkbox(f"c{i}", states[i])

    h = Harness(ui)
    h.click(15, ROW[1].y + 10)
    assert states == [0, 1]


def test_checkbox_key_disambiguates_equal_labels():
    states = [0, 0]

    def ui(ctx):
        for i in range(2):
            ctx.layout_set_next(ROW[i], ABS)
            _, states[i] = ctx.checkbox("same", states[i], key=i)

    h = Harness(ui)
    h.click(15, ROW[0].y + 10)
    assert states == [1, 0]


def test_explicit_slider_key_survives_reordering():
    vals = {"a": 10.0, "b": 10.0}
    order = ["a", "b"]

    def ui(ctx):
        for i, k in enumerate(order):
            ctx.layout_set_next(ROW[i], ABS)
            _, vals[k] = ctx.slider(vals[k], 0, 100, key=k)

    h = Harness(ui)
    ctx = h.ctx
    y = ROW[1].y + 10
    ctx.input_mousemove(100, y)
    h.frame()
    h.frame()
    ctx.input_mousedown(100, y, Mouse.LEFT)
    h.frame()  # "b" focused
    order.reverse()  # "b" now drawn in row 0, under no mouse
    ctx.input_mousemove(190, y)
    h.frame()
    # Focus follows the key, so "b" keeps the drag although it moved rows.
    assert vals["b"] > 80
    assert vals["a"] == 10.0


def test_textbox_keeps_focus_across_frames():
    texts = ["", ""]

    def ui(ctx):
        for i in range(2):
            ctx.layout_set_next(ROW[i], ABS)
            _, texts[i] = ctx.textbox(texts[i], 64)

    h = Harness(ui)
    h.click(50, ROW[1].y + 10)
    h.ctx.input_text("ab")
    h.frame()
    h.ctx.input_text("c")
    h.frame()
    assert texts == ["", "abc"]


def test_textbox_cuts_on_character_boundary():
    out = []

    def ui(ctx):
        out.append(ctx.textbox("éééé", 6)[1])

    Harness(ui).frame()
    assert out == ["éé"]
    tb = pymui.Textbox(6)
    tb.text = "éééé"
    assert tb.text == "éé"


def test_typed_input_does_not_split_character_when_full():
    text = ["ab"]

    def ui(ctx):
        ctx.layout_set_next(ROW[0], ABS)
        _, text[0] = ctx.textbox(text[0], 4, key="t")  # room for 1 byte

    h = Harness(ui)
    h.click(50, ROW[0].y + 10)
    h.ctx.input_text("é")
    h.frame()
    assert text[0] == "ab"
    h.ctx.input_text("c")
    h.frame()
    assert text[0] == "abc"


def test_get_container_before_first_frame():
    ctx = pymui.Context()
    win = ctx.get_container("W")
    win.rect = Rect(5, 5, 50, 50)
    ctx.open_popup("P")
    with ctx:
        with ctx.window("W", 0, 0, 100, 100):
            pass
    assert ctx.get_container("W").rect.w == 50


def test_textbox_submit_flag():
    res = []
    text = ["x"]

    def ui(ctx):
        ctx.layout_set_next(ROW[0], ABS)
        r, text[0] = ctx.textbox(text[0], key="t")
        res.append(r)

    h = Harness(ui)
    h.click(50, ROW[0].y + 10)
    h.ctx.input_keydown(pymui.Key.RETURN)
    h.frame()
    assert res[-1] & Result.SUBMIT


@pytest.mark.parametrize("fmt", ["%.2f", "%.0f", "%g", "%5.1e", "%%%.1f%%", "v=%.3f"])
def test_valid_formats(fmt):
    with pymui.Context() as ctx:
        with ctx.window("W", 0, 0, 200, 100) as win:
            assert win.is_open
            ctx.slider(1.0, 0, 2, fmt=fmt)
            ctx.number(1.0, 1, fmt=fmt)


@pytest.mark.parametrize(
    "fmt",
    [
        "%s",
        "%d",
        "%n",
        "%200f",
        "%.99f",
        "%f%f",
        "no conversion",
        "%99f" + "\u00e9" * 15,
    ],
)
def test_unsafe_formats_rejected(fmt):
    with pymui.Context() as ctx:
        with ctx.window("W", 0, 0, 200, 100):
            with pytest.raises(ValueError):
                ctx.slider(1.0, 0, 2, fmt=fmt)
            with pytest.raises(ValueError):
                ctx.number(1.0, 1, fmt=fmt)


def test_container_fields_write_through():
    ctx = pymui.Context()
    with ctx:
        with ctx.window("W", 10, 10, 200, 150):
            win = ctx.get_current_container()
            win.rect = Rect(20, 30, 250, 160)
            win.scroll = Vec2(0, 5)
    win = ctx.get_container("W")
    assert (win.rect.x, win.rect.y, win.rect.w, win.rect.h) == (20, 30, 250, 160)
    assert win.scroll.y == 5
    win.open = False
    assert win.open == 0


def test_style_and_container_outlive_context_reference():
    style = pymui.Context().style
    gc.collect()
    assert style.padding >= 0  # would read freed memory without the ref

    ctx = pymui.Context()
    with ctx:
        with ctx.window("W", 0, 0, 100, 100):
            pass
    win = ctx.get_container("W")
    del ctx
    gc.collect()
    assert win.rect.w == 100


def test_text_command_is_copied():
    ctx = pymui.Context()
    with ctx:
        with ctx.window("W", 0, 0, 200, 100):
            ctx.label("first")
    cmds = []
    while (cmd := ctx.next_command()) is not None:
        cmds.append(cmd)
    texts = [c for c in cmds if c.type == pymui.Command.TEXT]
    with ctx:
        with ctx.window("W", 0, 0, 200, 100):
            ctx.label("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    assert "first" in [t.text for t in texts]


def test_draw_text_is_queued():
    ctx = pymui.Context()
    with ctx:
        with ctx.window("W", 0, 0, 200, 100):
            body = ctx.get_current_container().body
            ctx.draw_text("queued", Vec2(body.x + 2, body.y + 2), pymui.Color(1, 2, 3))
    found = []
    while (cmd := ctx.next_command()) is not None:
        if cmd.type == pymui.Command.TEXT:
            found.append((cmd.text, cmd.color.r))
    assert ("queued", 1) in found


def test_exception_inside_window_does_not_abort():
    ctx = pymui.Context()
    with pytest.raises(KeyError):
        with ctx:
            ctx.begin_window("W", Rect(0, 0, 100, 100))
            ctx.push_id("x")
            ctx.layout_begin_column()
            raise KeyError("boom")
    assert ctx.next_command() is None  # aborted frame is dropped
    with ctx:
        with ctx.window("W", 0, 0, 100, 100):
            ctx.label("ok")
    assert ctx.next_command() is not None


def test_scoped_context_managers_balance():
    ctx = pymui.Context()
    seen = {}
    for _ in range(2):
        with ctx:
            with ctx.window("W", 0, 0, 300, 300):
                with ctx.id_scope("scope"):
                    with ctx.treenode("node", pymui.Option.EXPANDED) as expanded:
                        seen["tree"] = expanded
                        if expanded:
                            ctx.label("child")
                with ctx.column():
                    ctx.label("in column")
                ctx.layout_row([-1], 50)
                with ctx.panel("P") as panel:
                    seen["panel"] = panel
                    ctx.label("in panel")
                with ctx.popup("never opened") as is_open:
                    seen["popup"] = is_open
    assert seen["tree"] is True
    assert seen["popup"] is False
    assert seen["panel"] is not None


def test_popup_opens():
    ctx = pymui.Context()
    states = []
    for i in range(2):
        with ctx:
            with ctx.window("W", 0, 0, 300, 300):
                if i == 0:
                    ctx.open_popup("menu")
                with ctx.popup("menu") as is_open:
                    states.append(is_open)
                    if is_open:
                        ctx.label("item")
    assert states == [True, True]


def test_exception_inside_treenode_propagates():
    ctx = pymui.Context()
    with pytest.raises(ValueError):
        with ctx:
            with ctx.window("W", 0, 0, 300, 300):
                with ctx.treenode("n", pymui.Option.EXPANDED):
                    raise ValueError
    with ctx:
        pass


def test_custom_widget_primitives():
    clicks = []
    r = Rect(10, 10, 80, 20)

    def ui(ctx):
        wid = ctx.get_id("custom")
        ctx.update_control(wid, r)
        ctx.draw_control_frame(wid, r, pymui.ColorIndex.BUTTON)
        ctx.draw_control_text("hi", r, pymui.ColorIndex.TEXT, pymui.Option.ALIGNCENTER)
        if ctx.mouse_pressed & Mouse.LEFT and ctx.focus == wid:
            clicks.append(wid)

    h = Harness(ui)
    h.click(30, 20)
    assert len(clicks) == 1
    assert h.ctx.mouse_pos.x == 30


def test_control_color_index_bounds():
    with pymui.Context() as ctx:
        with ctx.window("W", 0, 0, 100, 100):
            with pytest.raises(IndexError):
                ctx.draw_control_frame(
                    1, Rect(0, 0, 1, 1), pymui.ColorIndex.SCROLLTHUMB
                )
            with pytest.raises(IndexError):
                ctx.draw_control_text("x", Rect(0, 0, 1, 1), 99)


def test_bring_to_front():
    ctx = pymui.Context()
    for _ in range(2):
        with ctx:
            with ctx.window("A", 0, 0, 100, 100):
                pass
            with ctx.window("B", 0, 0, 100, 100):
                pass
    a = ctx.get_container("A")
    ctx.bring_to_front(a)
    assert a.zindex > ctx.get_container("B").zindex


def test_render_requires_window():
    pymui.renderer_shutdown()  # other tests may have opened one
    ctx = pymui.Context()
    with ctx:
        pass
    with pytest.raises(RuntimeError):
        pymui.render(ctx)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.label("x"),
        lambda c: c.text("x"),
        lambda c: c.button("x"),
        lambda c: c.checkbox("x", 0),
        lambda c: c.slider(1, 0, 2),
        lambda c: c.number(1, 1),
        lambda c: c.textbox("x"),
        lambda c: c.header("x"),
        lambda c: c.begin_treenode("x"),
        lambda c: c.begin_panel("x"),
        lambda c: c.layout_row([10], 0),
        lambda c: c.layout_width(10),
        lambda c: c.layout_next(),
        lambda c: c.layout_begin_column(),
    ],
)
def test_layout_calls_outside_window_raise(call):
    ctx = pymui.Context()
    with pytest.raises(RuntimeError):
        with ctx:
            call(ctx)
    assert ctx.get_current_container() is None


def test_end_column_without_begin_raises():
    with pytest.raises(RuntimeError):
        with pymui.Context() as ctx:
            with ctx.window("W", 0, 0, 100, 100):
                ctx.layout_end_column()


def test_layout_row_width_limit():
    with pymui.Context() as ctx:
        with ctx.window("W", 0, 0, 100, 100):
            ctx.layout_row([1] * 16, 0)
            with pytest.raises(ValueError):
                ctx.layout_row([1] * 17, 0)
