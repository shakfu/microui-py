"""Features that need a real window and GL context: images, scale, cursor, SDL clipboard.

Opt in with PYMUI_WINDOW_TESTS=1 on a machine with a display; SDL's dummy
video driver has no GL.
"""

import os
import time

import pytest

import pymui
from pymui import Command, Option, Rect, testing

pytestmark = pytest.mark.skipif(
    os.environ.get("PYMUI_WINDOW_TESTS") != "1", reason="set PYMUI_WINDOW_TESTS=1 to open windows"
)


@pytest.fixture
def window():
    pymui.renderer_init_window("pymui test", 320, 240, False)
    yield
    pymui.renderer_shutdown()


def red(w, h):
    return bytes([255, 0, 0, 255]) * (w * h)


def test_image_lifecycle(window):
    img = pymui.Image(4, 2, red(4, 2))
    assert (img.width, img.height, img.closed) == (4, 2, False)
    img.update(bytes(4 * 2 * 4))
    img.close()
    assert img.closed
    with pytest.raises(RuntimeError):
        img.update(red(4, 2))


def test_image_rejects_bad_data(window):
    with pytest.raises(ValueError):
        pymui.Image(4, 4, b"\0" * 10)
    with pytest.raises(ValueError):
        pymui.Image(0, 4)
    img = pymui.Image(2, 2)
    with pytest.raises(ValueError):
        img.update(b"\0")


def test_image_dies_with_window():
    pymui.renderer_init_window("pymui test", 320, 240, False)
    img = pymui.Image(2, 2)
    pymui.renderer_shutdown()
    assert img.closed
    pymui.renderer_init_window("pymui test", 320, 240, False)
    try:
        assert img.closed  # a new window does not revive it
        with pytest.raises(RuntimeError):
            pymui.Context().draw_image(img, Rect(0, 0, 1, 1))
    finally:
        pymui.renderer_shutdown()


def test_image_without_window_raises():
    with pytest.raises(RuntimeError):
        pymui.Image(2, 2)


def test_draw_image_command_and_render(window):
    img = pymui.Image(8, 8, red(8, 8))
    ctx = pymui.Context()

    def ui(ctx):
        with ctx.window("W", 0, 0, 200, 200, Option.NOTITLE):
            ctx.layout_row([64], 32)
            ctx.image(img)
            ctx.draw_image(img, Rect(150, 150, 100, 100), pymui.Color(255, 255, 255, 128))

    cmds = testing.run_frame(ctx, ui)
    images = [c for c in cmds if c.type == Command.IMAGE]
    assert len(images) == 2
    assert (images[0].rect.w, images[0].rect.h) == (64, 32)
    assert images[1].color.a == 128
    # second image overflows the window: it is wrapped in clip commands
    pymui.render(ctx, pymui.Color(0, 0, 0))
    pymui.render(ctx)


def test_drawn_image_outlives_its_name(window):
    ctx = pymui.Context()

    def ui(ctx):
        with ctx.window("W", 0, 0, 200, 200):
            ctx.layout_row([32], 32)
            ctx.image(pymui.Image(2, 2, red(2, 2)))  # no other reference

    testing.run_frame(ctx, ui)
    pymui.render(ctx)  # texture still valid


def test_scale_is_at_least_one(window):
    assert pymui.renderer_get_scale() >= 1.0
    pymui.renderer_resize(400, 300)
    assert pymui.renderer_get_scale() >= 1.0


def test_set_cursor(window):
    for c in (pymui.Cursor.HAND, pymui.Cursor.IBEAM, pymui.Cursor.ARROW):
        pymui.set_cursor(c)
    with pytest.raises(ValueError):
        pymui.set_cursor(99)


def test_sdl_clipboard(window):
    pymui.set_clipboard_text("pymui clipboard test")
    assert pymui.get_clipboard_text() == "pymui clipboard test"


def test_wait_event_times_out(window):
    while pymui.poll_event() is not None:
        pass
    t0 = time.monotonic()
    pymui.wait_event(0.05)
    assert time.monotonic() - t0 < 1.0
