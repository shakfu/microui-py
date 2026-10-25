"""Composite widgets built from the public `Context` API.

microui has no list, tab, dropdown or menu controls. These compose them from
`layout_next`, `update_control`, popups and drawing calls, so they behave
like microui widgets: call them every frame and keep the returned state.

    from pymui import widgets

    changed, choice = widgets.combo(ctx, "size", ["S", "M", "L"], choice)
    tab = widgets.tabs(ctx, "main", ["General", "Advanced"], tab)
    widgets.progress_bar(ctx, done / total)

`name` arguments are ID keys and popup/panel names; they must be unique
within the enclosing window.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .pymui import (
    ColorIndex,
    Context,
    Mouse,
    Option,
    Rect,
    clamp,
    renderer_get_text_width,
)


def _item(ctx: Context, label: str, key: str, selected: bool = False,
          framed: bool = False, center: bool = False) -> tuple[bool, Rect]:
    """Clickable cell; return (clicked, rect). Mirrors mu_button_ex's input logic."""
    r = ctx.layout_next()
    wid = ctx.get_id(key)
    ctx.update_control(wid, r)
    clicked = bool(ctx.mouse_pressed == Mouse.LEFT and ctx.focus == wid)
    style = ctx.style
    if selected:
        ctx.draw_rect(r, style.get_color(ColorIndex.BUTTONFOCUS))
    elif framed:
        ctx.draw_control_frame(wid, r, ColorIndex.BUTTON)
    elif ctx.hover == wid:
        ctx.draw_rect(r, style.get_color(ColorIndex.BUTTONHOVER))
    ctx.draw_control_text(label, r, ColorIndex.TEXT, Option.ALIGNCENTER if center else 0)
    return clicked, r


def _text_w(ctx: Context, items: Sequence[str]) -> int:
    pad = ctx.style.padding
    return max((renderer_get_text_width(s) for s in items), default=0) + 2 * pad + 2


def _close_current(ctx: Context) -> None:
    cnt = ctx.get_current_container()
    if cnt is not None:
        cnt.open = False


def _open_below(ctx: Context, name: str, r: Rect) -> None:
    """Open popup `name` under `r` instead of at the mouse."""
    ctx.open_popup(name)
    ctx.get_container(name).rect = Rect(r.x, r.y + r.h, max(r.w, 1), 1)


def progress_bar(ctx: Context, value: float, low: float = 0.0, high: float = 1.0,
                 text: str | None = None) -> None:
    """Draw a bar filled to `value` in [low, high], labelled with `text` or a percentage."""
    r = ctx.layout_next()
    style = ctx.style
    frac = clamp((value - low) / (high - low), 0.0, 1.0) if high != low else 0.0
    ctx.draw_rect(r, style.get_color(ColorIndex.BASE))
    ctx.draw_rect(Rect(r.x, r.y, int(r.w * frac), r.h), style.get_color(ColorIndex.BUTTONFOCUS))
    if style.get_color(ColorIndex.BORDER).a:
        ctx.draw_box(r, style.get_color(ColorIndex.BORDER))
    ctx.draw_control_text(f"{frac:.0%}" if text is None else text, r,
                          ColorIndex.TEXT, Option.ALIGNCENTER)


def listbox(ctx: Context, name: str, items: Sequence[str], selected: int,
            height: int = 100) -> tuple[bool, int]:
    """Scrollable single-selection list; return (changed, selected)."""
    changed = False
    ctx.layout_row([-1], height)
    with ctx.panel(name):
        ctx.layout_row([-1], 0)
        for i, item in enumerate(items):
            if _item(ctx, str(item), f"{name}#{i}", selected=i == selected)[0]:
                selected, changed = i, True
    return changed, selected


def tabs(ctx: Context, name: str, labels: Sequence[str], index: int) -> int:
    """Row of equal-width tab buttons; return the selected index."""
    if not labels:
        return index
    style = ctx.style
    cnt = ctx.get_current_container()
    body_w = cnt.body.w if cnt is not None else 0
    n = len(labels)
    w = max((body_w - 2 * style.padding - (n - 1) * style.spacing) // n, 1)
    ctx.layout_row([w] * n, 0)
    for i, label in enumerate(labels):
        if _item(ctx, label, f"{name}#{i}", selected=i == index, framed=i != index,
                 center=True)[0]:
            index = i
    return index


def combo(ctx: Context, name: str, items: Sequence[str], index: int) -> tuple[bool, int]:
    """Dropdown: a button showing `items[index]` that opens a list below it.

    Return (changed, index).
    """
    changed = False
    label = items[index] if 0 <= index < len(items) else ""
    clicked, r = _item(ctx, label, f"{name}#button", framed=True, center=True)
    if clicked:
        _open_below(ctx, name, r)
    with ctx.popup(name) as is_open:
        if is_open:
            ctx.layout_row([max(r.w - 2 * ctx.style.padding, _text_w(ctx, items))], 0)
            for i, item in enumerate(items):
                if _item(ctx, item, f"{name}#{i}", selected=i == index)[0]:
                    changed, index = i != index, i
                    _close_current(ctx)
    return changed, index


def menu_bar(ctx: Context, menus: Mapping[str, Sequence[str]],
             name: str = "menu") -> tuple[str, str] | None:
    """Row of menu buttons with dropdowns; return (menu, item) when an item is chosen."""
    titles = list(menus)
    ctx.layout_row([_text_w(ctx, [t]) for t in titles], 0)
    for title in titles:
        clicked, r = _item(ctx, title, f"{name}/{title}")
        if clicked:
            _open_below(ctx, f"{name}/{title}", r)
    chosen = None
    for title in titles:
        with ctx.popup(f"{name}/{title}") as is_open:
            if is_open:
                ctx.layout_row([_text_w(ctx, menus[title])], 0)
                for item in menus[title]:
                    if _item(ctx, item, f"{name}/{title}/{item}")[0]:
                        chosen = (title, item)
                        _close_current(ctx)
    return chosen
