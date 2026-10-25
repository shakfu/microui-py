#!/usr/bin/env python3
"""Desktop features: composite widgets, caret editing, Tab focus, clipboard,
images, file drop and idle redraw."""

import pymui
from pymui import Option, widgets
from pymui.app import App

FILES = ["README.md", "CHANGELOG.md", "pyproject.toml"]


def gradient(w, h):
    return b"".join(bytes([x * 255 // w, y * 255 // h, 160, 255]) for y in range(h) for x in range(w))


class Desktop(App):
    def __init__(self):
        super().__init__("pymui desktop demo", 640, 480, idle_timeout=1.0)
        self.name = "Ada"
        self.email = "ada@example.com"
        self.tab = 0
        self.size = 1
        self.row = 0
        self.progress = 0.0
        self.status = "Drop a file on the window"
        self.image = None

    def drop_file(self, path):
        FILES.append(path)
        self.status = f"Dropped {path}"

    def frame(self, ctx):
        if self.image is None:
            self.image = pymui.Image(64, 64, gradient(64, 64))
        with ctx.window("Desktop", 10, 10, 620, 460, Option.NOCLOSE) as win:
            if not win.is_open:
                return
            choice = widgets.menu_bar(ctx, {"File": ["Reset", "Quit"], "Help": ["About"]})
            if choice == ("File", "Quit"):
                self.quit()
            elif choice == ("File", "Reset"):
                self.progress = 0.0
            elif choice:
                self.status = "pymui " + pymui.version()
            self.tab = widgets.tabs(ctx, "tabs", ["Form", "Files"], self.tab)
            if self.tab == 0:
                self.form(ctx)
            else:
                self.files(ctx)
            ctx.layout_row([-1], 0)
            ctx.label(self.status)

    def form(self, ctx):
        ctx.layout_row([80, -1], 0)
        ctx.label("Name")
        _, self.name = ctx.textbox(self.name, 64, key="name")
        ctx.label("Email")
        _, self.email = ctx.textbox(self.email, 64, key="email")
        ctx.label("Size")
        _, self.size = widgets.combo(ctx, "size", ["Small", "Medium", "Large"], self.size)
        ctx.layout_row([-1], 0)
        ctx.label("Tab moves focus. Ctrl+A/C/X/V (Cmd on macOS) select and use the clipboard.")
        ctx.layout_row([100, -1], 0)
        if ctx.button("Step", opt=Option.ALIGNCENTER):
            self.progress = min(self.progress + 0.1, 1.0)
        widgets.progress_bar(ctx, self.progress)
        ctx.layout_row([64], 64)
        ctx.image(self.image)

    def files(self, ctx):
        changed, self.row = widgets.listbox(ctx, "files", FILES, self.row, height=200)
        if changed:
            self.status = f"Selected {FILES[self.row]}"


if __name__ == "__main__":
    Desktop().run()
