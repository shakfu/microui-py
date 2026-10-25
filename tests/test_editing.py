"""Textbox caret editing, clipboard and Tab focus traversal (no window needed)."""

import pytest

import pymui
from pymui import Event, EventType, Key, Option, Rect, RectCommand, testing
from pymui.app import COMMAND_MOD, App

BOX = Rect(10, 10, 200, 20)


@pytest.fixture(autouse=True)
def _clear_clipboard():
    pymui.set_clipboard_text("")


class Form:
    """One window holding textboxes `keys`, laid out vertically."""

    def __init__(self, *texts, keys=None, bufsz=64):
        self.text = list(texts)
        self.keys = keys or [f"t{i}" for i in range(len(texts))]
        self.ids = []
        self.results = []
        self.bufsz = bufsz

    def rect(self, i):
        return Rect(BOX.x, BOX.y + 30 * i, BOX.w, BOX.h)

    def __call__(self, ctx):
        with ctx.window("W", 0, 0, 300, 200, Option.NOTITLE | Option.NOSCROLL):
            self.ids = [ctx.get_id(k) for k in self.keys]
            self.results = []
            for i, k in enumerate(self.keys):
                ctx.layout_set_next(self.rect(i), 0)
                res, self.text[i] = ctx.textbox(self.text[i], self.bufsz, key=k)
                self.results.append(res)


def focus(ctx, form, i=0):
    r = form.rect(i)
    testing.click(ctx, form, r.x + r.w - 2, r.y + 5)
    assert ctx.focus == form.ids[i]


def caret_rect(cmds):
    h = pymui.renderer_get_text_height()
    return [c.rect for c in cmds if isinstance(c, RectCommand) and c.rect.w == 1 and c.rect.h == h][-1]


def test_insert_at_caret():
    ctx, form = pymui.Context(), Form("hello")
    focus(ctx, form)
    testing.press(ctx, form, Key.LEFT)
    testing.press(ctx, form, Key.LEFT)
    testing.type_text(ctx, form, "X")
    assert form.text[0] == "helXlo"


def test_home_end_delete_backspace():
    ctx, form = pymui.Context(), Form("abcd")
    focus(ctx, form)
    testing.press(ctx, form, Key.HOME)
    testing.press(ctx, form, Key.DELETE)
    assert form.text[0] == "bcd"
    testing.press(ctx, form, Key.END)
    testing.press(ctx, form, Key.BACKSPACE)
    assert form.text[0] == "bc"
    testing.press(ctx, form, Key.HOME)
    testing.press(ctx, form, Key.BACKSPACE)  # nothing before the caret
    testing.press(ctx, form, Key.END)
    testing.press(ctx, form, Key.DELETE)  # nothing after it
    assert form.text[0] == "bc"


def test_caret_steps_over_multibyte_characters():
    ctx, form = pymui.Context(), Form("h\u00e9\u20acx")
    focus(ctx, form)
    testing.press(ctx, form, Key.HOME)
    testing.press(ctx, form, Key.RIGHT)
    testing.press(ctx, form, Key.DELETE)
    assert form.text[0] == "h\u20acx"
    testing.press(ctx, form, Key.RIGHT)
    testing.press(ctx, form, Key.BACKSPACE)
    assert form.text[0] == "hx"


def test_click_places_caret():
    ctx, form = pymui.Context(), Form("abcdef")
    cw = pymui.renderer_get_text_width("a")
    x = BOX.x + pymui.Context().style.padding + 2 * cw + 1
    testing.click(ctx, form, x, BOX.y + 5)
    testing.type_text(ctx, form, "Z")
    assert form.text[0] == "abZcdef"


def test_caret_stays_visible_in_long_text():
    ctx, form = pymui.Context(), Form("a" * 60)
    focus(ctx, form)
    cmds = testing.run_frame(ctx, form)
    assert BOX.x < caret_rect(cmds).x < BOX.x + BOX.w
    testing.press(ctx, form, Key.HOME)
    cmds = testing.run_frame(ctx, form)
    assert caret_rect(cmds).x == BOX.x + ctx.style.padding


def test_refocus_puts_caret_at_end():
    ctx, form = pymui.Context(), Form("abc", "xyz")
    focus(ctx, form, 0)
    testing.press(ctx, form, Key.HOME)
    focus(ctx, form, 1)
    testing.press(ctx, form, Key.TAB)  # wraps to the first box
    testing.type_text(ctx, form, "!")
    assert form.text[0] == "abc!"


def test_insert_respects_buffer_size():
    ctx, form = pymui.Context(), Form("abc", bufsz=6)
    focus(ctx, form)
    testing.press(ctx, form, Key.HOME)
    testing.type_text(ctx, form, "\u00e9\u00e9")  # 4 bytes; 2 are free
    assert form.text[0] == "\u00e9abc"


def test_textbox_class_caret():
    ctx = pymui.Context()
    box = pymui.Textbox(32)
    box.text = "ac"

    def ui(ctx):
        with ctx.window("W", 0, 0, 300, 100, Option.NOTITLE):
            ctx.layout_set_next(BOX, 0)
            box.update(ctx)

    testing.click(ctx, ui, BOX.x + BOX.w - 2, BOX.y + 5)
    testing.press(ctx, ui, Key.LEFT)
    testing.type_text(ctx, ui, "b")
    assert box.text == "abc"


# Clipboard. Without SDL video, the clipboard is process-local.

def test_clipboard_roundtrip_without_window():
    pymui.set_clipboard_text("x\0y")
    assert pymui.get_clipboard_text() == "x"


def test_copy_focused_textbox():
    ctx, form = pymui.Context(), Form("one", "two")
    focus(ctx, form, 1)
    ctx.input_select_all()
    ctx.input_copy()
    testing.run_frame(ctx, form)
    assert pymui.get_clipboard_text() == "two"
    assert form.text == ["one", "two"]


def test_copy_without_focus_does_nothing():
    ctx, form = pymui.Context(), Form("one")
    testing.run_frame(ctx, form)
    ctx.input_copy()
    testing.run_frame(ctx, form)
    assert pymui.get_clipboard_text() == ""


def test_copy_request_expires_after_one_frame():
    ctx, form = pymui.Context(), Form("one")
    ctx.input_copy()
    testing.run_frame(ctx, form)  # nothing focused: request dropped
    focus(ctx, form)
    assert pymui.get_clipboard_text() == ""


def test_cut_clears_and_reports_change():
    ctx, form = pymui.Context(), Form("cut me")
    focus(ctx, form)
    ctx.input_select_all()
    ctx.input_cut()
    testing.run_frame(ctx, form)
    assert pymui.get_clipboard_text() == "cut me"
    assert form.text[0] == ""
    assert form.results[0] & pymui.Result.CHANGE


def test_cut_textbox_class():
    ctx = pymui.Context()
    box = pymui.Textbox(32)
    box.text = "abc"

    def ui(ctx):
        with ctx.window("W", 0, 0, 300, 100, Option.NOTITLE):
            ctx.layout_set_next(BOX, 0)
            box.update(ctx)

    testing.click(ctx, ui, BOX.x + 5, BOX.y + 5)
    ctx.input_select_all()
    ctx.input_cut()
    testing.run_frame(ctx, ui)
    assert (box.text, pymui.get_clipboard_text()) == ("", "abc")
    testing.run_frame(ctx, ui)
    assert box.text == ""


def test_paste_inserts_at_caret():
    ctx, form = pymui.Context(), Form("ad")
    pymui.set_clipboard_text("bc" * 30)  # more than one frame of input
    focus(ctx, form)
    testing.press(ctx, form, Key.LEFT)
    ctx.input_paste()
    for _ in range(3):
        testing.run_frame(ctx, form)
    assert form.text[0] == "a" + "bc" * 30 + "d"


@pytest.mark.parametrize(
    "char, text, clip",
    [("c", "copy", "copy"), ("x", "", "copy"), ("v", "clip", "clip")],
)
def test_app_clipboard_shortcuts(char, text, clip):
    app = App()
    form = Form("copy")
    pymui.set_clipboard_text("clip")
    focus(app.ctx, form)
    for c in ("a", char):  # select all, then the shortcut
        app.handle_event(Event(EventType.KEYDOWN, keycode=ord(c), mod=COMMAND_MOD))
        testing.run_frame(app.ctx, form)
    assert (form.text[0], pymui.get_clipboard_text()) == (text, clip)
    assert app.ctx.key_down == 0


def test_app_plain_letter_is_not_a_shortcut():
    app = App()
    form = Form("copy")
    focus(app.ctx, form)
    app.handle_event(Event(EventType.KEYDOWN, keycode=ord("x")))
    testing.run_frame(app.ctx, form)
    assert form.text[0] == "copy"


# Tab focus traversal

def test_tab_cycles_forward_and_wraps():
    ctx, form = pymui.Context(), Form("a", "b", "c")
    focus(ctx, form, 0)
    testing.press(ctx, form, Key.TAB)
    assert ctx.focus == form.ids[1]
    testing.press(ctx, form, Key.TAB)
    testing.press(ctx, form, Key.TAB)
    assert ctx.focus == form.ids[0]


def test_shift_tab_cycles_backward():
    ctx, form = pymui.Context(), Form("a", "b", "c")
    focus(ctx, form, 0)
    ctx.input_keydown(Key.SHIFT)
    testing.press(ctx, form, Key.TAB)
    assert ctx.focus == form.ids[2]
    testing.press(ctx, form, Key.TAB)
    assert ctx.focus == form.ids[1]


def test_tab_without_focus_picks_first_or_last():
    ctx, form = pymui.Context(), Form("a", "b")
    testing.run_frame(ctx, form)
    testing.press(ctx, form, Key.TAB)
    assert ctx.focus == form.ids[0]
    ctx.set_focus(0)
    testing.run_frame(ctx, form)
    ctx.input_keydown(Key.SHIFT)
    testing.press(ctx, form, Key.TAB)
    assert ctx.focus == form.ids[1]


def test_tab_then_type_goes_to_next_box():
    ctx, form = pymui.Context(), Form("a", "b")
    focus(ctx, form, 0)
    testing.press(ctx, form, Key.TAB)
    testing.type_text(ctx, form, "!")
    assert form.text == ["a", "b!"]


def test_tab_with_no_textboxes_is_harmless():
    ctx = pymui.Context()

    def ui(ctx):
        with ctx.window("W", 0, 0, 100, 100):
            ctx.label("x")

    testing.press(ctx, ui, Key.TAB)
    assert ctx.focus == 0


# Selection

def shift_press(ctx, ui, key):
    ctx.input_keydown(Key.SHIFT)
    testing.press(ctx, ui, key)
    ctx.input_keyup(Key.SHIFT)


def copied(ctx, ui):
    pymui.set_clipboard_text("<none>")
    ctx.input_copy()
    testing.run_frame(ctx, ui)
    return pymui.get_clipboard_text()


def char_x(i, text="abcdef"):
    """Screen x of the boundary before character `i` of short `text` in BOX."""
    return BOX.x + pymui.Context().style.padding + pymui.renderer_get_text_width(text[:i])


def test_shift_arrows_select_and_typing_replaces():
    ctx, form = pymui.Context(), Form("abcdef")
    focus(ctx, form)
    shift_press(ctx, form, Key.LEFT)
    shift_press(ctx, form, Key.LEFT)
    assert copied(ctx, form) == "ef"
    testing.type_text(ctx, form, "X")
    assert form.text[0] == "abcdX"


def test_shift_home_selects_to_start():
    ctx, form = pymui.Context(), Form("abc")
    focus(ctx, form)
    testing.press(ctx, form, Key.LEFT)
    shift_press(ctx, form, Key.HOME)
    assert copied(ctx, form) == "ab"


def test_arrow_without_shift_collapses_selection():
    ctx, form = pymui.Context(), Form("abcdef")
    focus(ctx, form)
    ctx.input_select_all()
    testing.press(ctx, form, Key.LEFT)  # caret to selection start
    assert copied(ctx, form) == "<none>"
    testing.type_text(ctx, form, "X")
    assert form.text[0] == "Xabcdef"
    ctx.input_select_all()
    testing.press(ctx, form, Key.RIGHT)  # caret to selection end
    testing.type_text(ctx, form, "Y")
    assert form.text[0] == "XabcdefY"


@pytest.mark.parametrize("key", [Key.BACKSPACE, Key.DELETE])
def test_delete_keys_remove_selection(key):
    ctx, form = pymui.Context(), Form("abcdef")
    focus(ctx, form)
    testing.press(ctx, form, Key.LEFT)
    shift_press(ctx, form, Key.LEFT)
    shift_press(ctx, form, Key.LEFT)
    testing.press(ctx, form, key)
    assert form.text[0] == "abcf"


def test_copy_with_empty_selection_keeps_clipboard():
    ctx, form = pymui.Context(), Form("abc")
    focus(ctx, form)
    assert copied(ctx, form) == "<none>"
    ctx.input_cut()
    testing.run_frame(ctx, form)
    assert form.text[0] == "abc"


def test_multibyte_selection_copy():
    ctx, form = pymui.Context(), Form("a\u00e9\u20acb")
    focus(ctx, form)
    testing.press(ctx, form, Key.LEFT)
    shift_press(ctx, form, Key.LEFT)
    shift_press(ctx, form, Key.LEFT)
    assert copied(ctx, form) == "\u00e9\u20ac"


def test_mouse_drag_selects():
    ctx, form = pymui.Context(), Form("abcdef")
    y = BOX.y + 5
    ctx.input_mousemove(char_x(1), y)
    testing.run_frame(ctx, form)
    testing.run_frame(ctx, form)
    ctx.input_mousedown(char_x(1), y, pymui.Mouse.LEFT)
    testing.run_frame(ctx, form)
    ctx.input_mousemove(char_x(4), y)
    testing.run_frame(ctx, form)
    ctx.input_mouseup(char_x(4), y, pymui.Mouse.LEFT)
    testing.run_frame(ctx, form)
    assert copied(ctx, form) == "bcd"


def test_drag_past_edge_selects_to_end():
    ctx, form = pymui.Context(), Form("abcdef")
    y = BOX.y + 5
    ctx.input_mousemove(char_x(2), y)
    testing.run_frame(ctx, form)
    testing.run_frame(ctx, form)
    ctx.input_mousedown(char_x(2), y, pymui.Mouse.LEFT)
    testing.run_frame(ctx, form)
    ctx.input_mousemove(BOX.x + BOX.w + 40, y + 30)  # outside the box
    testing.run_frame(ctx, form)
    ctx.input_mouseup(BOX.x + BOX.w + 40, y + 30, pymui.Mouse.LEFT)
    testing.run_frame(ctx, form)
    assert ctx.focus == form.ids[0]
    assert copied(ctx, form) == "cdef"


def test_shift_click_extends():
    ctx, form = pymui.Context(), Form("abcdef")
    testing.click(ctx, form, char_x(1), BOX.y + 5)
    ctx.input_keydown(Key.SHIFT)
    testing.click(ctx, form, char_x(3), BOX.y + 5)
    ctx.input_keyup(Key.SHIFT)
    assert copied(ctx, form) == "bc"


def test_plain_click_clears_selection():
    ctx, form = pymui.Context(), Form("abcdef")
    focus(ctx, form)
    ctx.input_select_all()
    testing.run_frame(ctx, form)
    testing.click(ctx, form, char_x(2), BOX.y + 5)
    assert copied(ctx, form) == "<none>"


def test_selection_is_highlighted():
    ctx, form = pymui.Context(), Form("abcdef")
    focus(ctx, form)
    shift_press(ctx, form, Key.LEFT)
    shift_press(ctx, form, Key.LEFT)
    cmds = testing.run_frame(ctx, form)
    hl = ctx.style.get_color(pymui.ColorIndex.BUTTONFOCUS)
    rects = [c.rect for c in cmds if isinstance(c, RectCommand)
             and (c.color.r, c.color.g, c.color.b) == (hl.r, hl.g, hl.b)
             and c.rect.h == pymui.renderer_get_text_height()]
    assert [(r.x, r.w) for r in rects] == [(char_x(4), pymui.renderer_get_text_width("ef"))]


def test_textbox_class_selection():
    ctx = pymui.Context()
    box = pymui.Textbox(32)
    box.text = "hello"

    def ui(ctx):
        with ctx.window("W", 0, 0, 300, 100, Option.NOTITLE):
            ctx.layout_set_next(BOX, 0)
            box.update(ctx)

    testing.click(ctx, ui, BOX.x + BOX.w - 2, BOX.y + 5)
    shift_press(ctx, ui, Key.LEFT)
    ctx.input_cut()
    testing.run_frame(ctx, ui)
    assert (box.text, pymui.get_clipboard_text()) == ("hell", "o")


def test_tab_focus_starts_without_selection():
    ctx, form = pymui.Context(), Form("abc", "xyz")
    focus(ctx, form, 0)
    ctx.input_select_all()
    testing.run_frame(ctx, form)
    testing.press(ctx, form, Key.TAB)
    assert copied(ctx, form) == "<none>"
