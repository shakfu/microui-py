
from libc.stdlib cimport malloc, calloc, realloc, free
from libc.string cimport memcpy, memset, strlen
import operator
import os
import re
import sys
import time
from contextlib import contextmanager

cimport pymui


cdef bint _window_open = False
cdef str _clipboard = ""  # used while SDL video is not initialized
cdef SDL_Cursor* _cursors[16]  # system cursors, created on first use

# Command-buffer bytes kept free before each drawing call, beyond the call's
# own text. One window with title, frame and scrollbars uses under 1 KB.
cdef Py_ssize_t _CMD_MARGIN = 2048
# Worst-case command bytes per wrapped line of ctx.text(), excluding the text.
cdef Py_ssize_t _TEXT_LINE_COST = sizeof(mu_TextCommand) + 2 * sizeof(mu_ClipCommand)
cdef Py_ssize_t _MAX_PENDING_TEXT = 64 * 1024
cdef Py_ssize_t _MAX_FONT_BYTES = 64 * 1024 * 1024


cdef int _require_window() except -1:
    if not _window_open:
        raise RuntimeError("No renderer window; call renderer_init_window() first")
    return 0


class DuplicateIDError(RuntimeError):
    """Two widgets or containers in one frame resolved to the same ID."""


@contextmanager
def _scoped(value, end):
    """Yield `value`, then call `end` if given.

    If the body raised, an error from `end` is dropped so the original
    exception propagates; the frame is discarded either way.
    """
    try:
        yield value
    except BaseException:
        if end is not None:
            try:
                end()
            except RuntimeError:
                pass
        raise
    if end is not None:
        end()


# One float conversion, bounded so microui's sprintf output fits its
# MU_MAX_FMT + 1 byte buffer. "%%" escapes are allowed around it.
_FMT_RE = re.compile(r"(?:[^%]|%%)*%[-+ #0]*\d{0,2}(?:\.(?:1\d|20|\d))?[fFeEgG](?:[^%]|%%)*")


cdef bytes _check_fmt(str fmt):
    # Worst case: 99-wide field + 32 - 4 literal bytes < 128.
    cdef bytes bfmt = fmt.encode('utf-8')
    if len(bfmt) > 32 or _FMT_RE.fullmatch(fmt) is None:
        raise ValueError(f"invalid number format {fmt!r}: need one %f/%e/%g conversion")
    return bfmt


cdef int _channel(int v) except -1:
    """Validate a color channel; mu_Color stores unsigned char, which would wrap."""
    if not 0 <= v <= 255:
        raise ValueError(f"color channel must be 0..255, got {v}")
    return v


cdef Py_ssize_t _utf8_cut(bytes b, Py_ssize_t n):
    """Largest length <= n that does not split a UTF-8 sequence in `b`."""
    if n >= len(b):
        return len(b)
    while n > 0 and (b[n] & 0xC0) == 0x80:
        n -= 1
    return n


cdef bytes _to_bytes(object data):
    """Encode an ID key: bytes pass through, everything else via str()."""
    if isinstance(data, bytes):
        return data
    return str(data).encode('utf-8')



# Fused types
# Version function
def version() -> str:
    """Get the microui library version.

    Returns:
        str: The version string of the underlying microui library.
    """
    return MU_VERSION.decode()

def clamp(x, a, b):
    """Clamp a value between minimum and maximum bounds.

    Args:
        x: The value to clamp
        a: The minimum bound
        b: The maximum bound

    Returns:
        The clamped value, guaranteed to be between a and b (inclusive)
    """
    # Untyped on purpose: a C float parameter would round to 32 bits.
    return min(b, max(a, x))

# Global convenience functions
def vec2(int x, int y) -> Vec2:
    """Create a 2D vector with the given coordinates.

    Args:
        x (int): The x coordinate
        y (int): The y coordinate

    Returns:
        Vec2: A new Vec2 instance with the specified coordinates
    """
    return Vec2.from_c(mu_vec2(x, y))

def rect(int x, int y, int w, int h) -> Rect:
    """Create a rectangle with the given position and dimensions.

    Args:
        x (int): The x coordinate of the top-left corner
        y (int): The y coordinate of the top-left corner
        w (int): The width of the rectangle
        h (int): The height of the rectangle

    Returns:
        Rect: A new Rect instance with the specified dimensions
    """
    return Rect.from_c(mu_rect(x, y, w, h))

def color(int r, int g, int b, int a=255) -> Color:
    """Create a color with the given RGBA values.

    Args:
        r (int): Red component (0-255)
        g (int): Green component (0-255)
        b (int): Blue component (0-255)
        a (int, optional): Alpha component (0-255). Defaults to 255 (fully opaque).

    Returns:
        Color: A new Color instance with the specified RGBA values
    """
    return Color(r, g, b, a)


# Basic struct classes
cdef class Vec2:
    """A 2D vector with integer coordinates.

    This class represents a 2D vector with x and y integer coordinates,
    commonly used for positions, sizes, and offsets in the UI system.

    Attributes:
        x (int): The x coordinate
        y (int): The y coordinate

    Example:
        >>> v = Vec2(10, 20)
        >>> print(v.x, v.y)  # Output: 10 20
        >>> v.x = 30
        >>> print(v)  # Output: Vec2(30, 20)
    """
    cdef mu_Vec2 _vec

    def __cinit__(self, int x=0, int y=0):
        """Initialize a Vec2 with the given coordinates.

        Args:
            x (int, optional): The x coordinate. Defaults to 0.
            y (int, optional): The y coordinate. Defaults to 0.
        """
        self._vec.x = x
        self._vec.y = y

    @property
    def x(self) -> int:
        """Get or set the x coordinate."""
        return self._vec.x

    @x.setter
    def x(self, int value):
        self._vec.x = value

    @property
    def y(self) -> int:
        """Get or set the y coordinate."""
        return self._vec.y

    @y.setter
    def y(self, int value):
        self._vec.y = value

    def __repr__(self):
        return f"Vec2({self.x}, {self.y})"

    @staticmethod
    cdef Vec2 from_c(mu_Vec2 vec):
        cdef Vec2 result = Vec2.__new__(Vec2)
        result._vec = vec
        return result

    cdef mu_Vec2 to_c(self):
        return self._vec


cdef class Rect:
    """A rectangle defined by position and dimensions.

    This class represents a rectangle with integer coordinates and dimensions,
    commonly used for UI element bounds, clipping regions, and layout calculations.

    Attributes:
        x (int): The x coordinate of the top-left corner
        y (int): The y coordinate of the top-left corner
        w (int): The width of the rectangle
        h (int): The height of the rectangle

    Example:
        >>> r = Rect(10, 20, 100, 50)
        >>> print(f"Position: ({r.x}, {r.y}), Size: {r.w}x{r.h}")
        Position: (10, 20), Size: 100x50
    """
    cdef mu_Rect _rect

    def __cinit__(self, int x=0, int y=0, int w=0, int h=0):
        """Initialize a Rect with the given position and dimensions.

        Args:
            x (int, optional): The x coordinate of the top-left corner. Defaults to 0.
            y (int, optional): The y coordinate of the top-left corner. Defaults to 0.
            w (int, optional): The width of the rectangle. Defaults to 0.
            h (int, optional): The height of the rectangle. Defaults to 0.
        """
        self._rect.x = x
        self._rect.y = y
        self._rect.w = w
        self._rect.h = h

    @property
    def x(self) -> int:
        """Get or set the x coordinate of the top-left corner."""
        return self._rect.x

    @x.setter
    def x(self, int value):
        self._rect.x = value

    @property
    def y(self) -> int:
        """Get or set the y coordinate of the top-left corner."""
        return self._rect.y

    @y.setter
    def y(self, int value):
        self._rect.y = value

    @property
    def w(self) -> int:
        """Get or set the width of the rectangle."""
        return self._rect.w

    @w.setter
    def w(self, int value):
        self._rect.w = value

    @property
    def h(self) -> int:
        """Get or set the height of the rectangle."""
        return self._rect.h

    @h.setter
    def h(self, int value):
        self._rect.h = value

    def __repr__(self):
        return f"Rect({self.x}, {self.y}, {self.w}, {self.h})"

    @staticmethod
    cdef Rect from_c(mu_Rect rect):
        cdef Rect result = Rect.__new__(Rect)
        result._rect = rect
        return result

    cdef mu_Rect to_c(self):
        return self._rect


cdef class Color:
    """An RGBA color with 8-bit components.

    This class represents a color with red, green, blue, and alpha components,
    each ranging from 0 to 255. It's used throughout the UI system for
    rendering text, backgrounds, borders, and other visual elements.

    Attributes:
        r (int): Red component (0-255)
        g (int): Green component (0-255)
        b (int): Blue component (0-255)
        a (int): Alpha component (0-255, where 0 is transparent and 255 is opaque)

    Example:
        >>> red = Color(255, 0, 0)        # Fully opaque red
        >>> semi_blue = Color(0, 0, 255, 128)  # Semi-transparent blue
        >>> print(red)  # Output: Color(255, 0, 0, 255)
    """
    cdef mu_Color _color

    def __cinit__(self, int r=0, int g=0, int b=0, int a=255):
        """Initialize a Color with the given RGBA values.

        Args:
            r (int, optional): Red component (0-255). Defaults to 0.
            g (int, optional): Green component (0-255). Defaults to 0.
            b (int, optional): Blue component (0-255). Defaults to 0.
            a (int, optional): Alpha component (0-255). Defaults to 255 (fully opaque).
        """
        self._color.r = _channel(r)
        self._color.g = _channel(g)
        self._color.b = _channel(b)
        self._color.a = _channel(a)

    @property
    def r(self) -> int:
        """Get or set the red component (0-255)."""
        return self._color.r

    @r.setter
    def r(self, int value):
        self._color.r = _channel(value)

    @property
    def g(self) -> int:
        """Get or set the green component (0-255)."""
        return self._color.g

    @g.setter
    def g(self, int value):
        self._color.g = _channel(value)

    @property
    def b(self) -> int:
        """Get or set the blue component (0-255)."""
        return self._color.b

    @b.setter
    def b(self, int value):
        self._color.b = _channel(value)

    @property
    def a(self) -> int:
        """Get or set the alpha component (0-255, where 0 is transparent)."""
        return self._color.a

    @a.setter
    def a(self, int value):
        self._color.a = _channel(value)

    def __repr__(self):
        return f"Color({self.r}, {self.g}, {self.b}, {self.a})"

    @staticmethod
    cdef Color from_c(mu_Color color):
        cdef Color result = Color.__new__(Color)
        result._color = color
        return result

    cdef mu_Color to_c(self):
        return self._color


cdef class Style:
    cdef mu_Style* ptr
    cdef bint owner
    cdef object _ref  # keeps the owning Context alive

    def __cinit__(self):
        self.ptr = NULL
        self.owner = False

    def __dealloc__(self):
        # De-allocate if not null and flag is set
        if self.ptr is not NULL and self.owner is True:
            free(self.ptr)
            self.ptr = NULL

    def __init__(self):
        # Prevent accidental instantiation from normal Python code
        # since we cannot pass a struct pointer into a Python constructor.
        raise TypeError("This class cannot be instantiated directly.")

    cdef mu_Style* _p(self) except NULL:
        if self.ptr is NULL:
            raise ValueError("Style is not bound to a Context")
        return self.ptr

    @staticmethod
    cdef Style from_ptr(mu_Style* ptr, bint owner=False, object ref=None):
        cdef Style wrapper = Style.__new__(Style)
        wrapper.ptr = ptr
        wrapper.owner = owner
        wrapper._ref = ref
        return wrapper

    @property
    def size(self) -> Vec2:
        return Vec2.from_c(self._p().size)

    @size.setter
    def size(self, Vec2 value):
        self._p().size = value.to_c()

    @property
    def padding(self) -> int:
        return self._p().padding

    @padding.setter
    def padding(self, int value):
        self._p().padding = value

    @property
    def spacing(self) -> int:
        return self._p().spacing

    @spacing.setter
    def spacing(self, int value):
        self._p().spacing = value

    @property
    def indent(self) -> int:
        return self._p().indent

    @indent.setter
    def indent(self, int value):
        self._p().indent = value

    @property
    def title_height(self) -> int:
        return self._p().title_height

    @title_height.setter
    def title_height(self, int value):
        self._p().title_height = value

    @property
    def scrollbar_size(self) -> int:
        return self._p().scrollbar_size

    @scrollbar_size.setter
    def scrollbar_size(self, int value):
        self._p().scrollbar_size = value

    @property
    def thumb_size(self) -> int:
        return self._p().thumb_size

    @thumb_size.setter
    def thumb_size(self, int value):
        self._p().thumb_size = value

    def get_color(self, int index) -> Color:
        if 0 <= index < MU_COLOR_MAX:
            return Color.from_c(self._p().colors[index])
        raise IndexError("Color index out of range")

    def set_color(self, int index, Color color):
        if 0 <= index < MU_COLOR_MAX:
            self._p().colors[index] = color.to_c()
        else:
            raise IndexError("Color index out of range")


cdef int text_width(mu_Font font, const char *text, int len) noexcept:
    return r_get_text_width(text, len)


cdef int text_height(mu_Font font) noexcept:
    return r_get_text_height()


# Main Context class
cdef class Context:
    """The main microui context for creating and managing UI elements.

    This is the primary class for building immediate-mode user interfaces.
    It manages the UI state, handles input events, and provides methods
    for creating windows, widgets, and controlling layout.

    The Context follows an immediate-mode paradigm where UI elements
    are created and processed each frame rather than being persistent objects.

    The Context supports Python's context manager protocol for both frame and
    window management, providing automatic cleanup with the 'with' statement.

    Examples:
        Modern approach (recommended - context managers for frame and window):
        >>> with Context() as ctx:
        ...     with ctx.window("My Window", 10, 10, 200, 150) as window:
        ...         if window.is_open:
        ...             ctx.label("Hello, World!")
        ...             if ctx.button("Click me"):
        ...                 print("Button clicked!")

        Alternative (manual window management):
        >>> with Context() as ctx:
        ...     if ctx.begin_window("My Window", rect(10, 10, 200, 150)):
        ...         ctx.label("Hello, World!")
        ...         ctx.end_window()

        Legacy (manual frame management):
        >>> ctx = Context()
        >>> ctx.begin()
        >>> try:
        ...     # UI code here
        ...     pass
        ... finally:
        ...     ctx.end()

    Note:
        The recommended approach uses context managers for both frame and window
        management. This provides automatic cleanup, exception safety, and cleaner code.
        The window context manager automatically calls begin_window() and end_window(),
        while the frame context manager automatically calls begin() and end().
    """
    cdef mu_Context* ptr
    cdef mu_Command* current_command
    # Fixed addresses for slider/number/checkbox values. microui derives
    # those widgets' IDs from the value pointer, so it must not vary.
    cdef mu_Real _real_slot
    cdef int _int_slot
    cdef bint _in_frame
    cdef list _scopes        # open begin_*/push_* scopes, innermost last
    cdef set _frame_ids      # widget/container IDs claimed this frame
    cdef dict _auto_ids      # (scope id, code, offset) -> next occurrence
    cdef bytes _pending_text # input text beyond microui's 32-byte buffer
    cdef list _focus_order   # textbox IDs in this frame's order, for Tab
    cdef list _frame_images  # Images drawn this frame, kept alive until render

    def __cinit__(self, *args, **kwargs):
        # Allocated here, not in __init__, so no instance has a NULL ptr.
        self.ptr = <mu_Context*>malloc(sizeof(mu_Context))
        if self.ptr is NULL:
            raise MemoryError("Failed to allocate Context")
        mu_init(self.ptr)
        # Pool slots are free when last_update < frame; at frame 0 none would be.
        self.ptr.frame = 1
        self.ptr.text_width = text_width
        self.ptr.text_height = text_height
        self.current_command = NULL
        self._in_frame = False
        self._scopes = []
        self._frame_ids = set()
        self._auto_ids = {}
        self._pending_text = b""
        self._focus_order = []
        self._frame_images = []

    def __dealloc__(self):
        if self.ptr is not NULL:
            free(self.ptr)
            self.ptr = NULL

    def __init__(self):
        """Create a microui context.

        Raises:
            MemoryError: If allocation fails.
        """

    @property
    def style(self) -> Style:
        """The live style (colors, spacing, sizes) used by this context."""
        return Style.from_ptr(<mu_Style*>self.ptr.style, False, self)

    # ------------------------------------------------------------------
    # Guards. microui checks its invariants with abort(), and some paths
    # (empty layout or clip stack) are unchecked out-of-bounds reads. Every
    # call that can reach one is checked here first and raises instead.

    cdef int _require_frame(self) except -1:
        if not self._in_frame:
            raise RuntimeError("must be called between begin() and end()")
        return 0

    cdef int _require_layout(self, int depth=1) except -1:
        if self.ptr.layout_stack.idx < depth:
            raise RuntimeError("must be called inside a window or panel")
        return 0

    cdef int _require_clip(self) except -1:
        if self.ptr.clip_stack.idx == 0:
            raise RuntimeError("must be called inside a window or panel")
        return 0

    cdef int _reserve(self, int ids=0, int clips=0, int layouts=0,
                      int containers=0, int roots=0, Py_ssize_t cmd=0) except -1:
        """Raise unless the stacks and command buffer have this much room."""
        cdef mu_Context* c = self.ptr
        if c.id_stack.idx + ids > MU_IDSTACK_SIZE:
            raise RuntimeError(f"ID stack full ({MU_IDSTACK_SIZE} nested scopes)")
        if c.clip_stack.idx + clips > MU_CLIPSTACK_SIZE:
            raise RuntimeError(f"clip stack full ({MU_CLIPSTACK_SIZE} nested clips)")
        if c.layout_stack.idx + layouts > MU_LAYOUTSTACK_SIZE:
            raise RuntimeError(f"layout stack full ({MU_LAYOUTSTACK_SIZE} nested layouts)")
        if c.container_stack.idx + containers > MU_CONTAINERSTACK_SIZE:
            raise RuntimeError(f"container stack full ({MU_CONTAINERSTACK_SIZE} nested containers)")
        if c.root_list.idx + roots > MU_ROOTLIST_SIZE:
            raise RuntimeError(f"too many windows in one frame (max {MU_ROOTLIST_SIZE})")
        if c.command_list.idx + _CMD_MARGIN + cmd >= MU_COMMANDLIST_SIZE:
            raise RuntimeError(f"command buffer full ({MU_COMMANDLIST_SIZE} bytes per frame)")
        return 0

    cdef int _require_pool_slot(self, mu_PoolItem* items, int n, mu_Id wid, str what) except -1:
        """Raise unless `wid` is pooled or a slot is free; mu_pool_init aborts otherwise."""
        cdef int i
        if mu_pool_get(self.ptr, items, n, wid) >= 0:
            return 0
        for i in range(n):
            if items[i].last_update < self.ptr.frame:
                return 0
        raise RuntimeError(f"more than {n} {what} in use in one frame")

    cdef int _claim(self, mu_Id wid, str what) except -1:
        """Record `wid` for this frame; a repeat means two widgets share state."""
        if wid in self._frame_ids:
            raise DuplicateIDError(
                f"{what} has the same ID as an earlier widget this frame; "
                "pass key= or wrap it in id_scope()")
        self._frame_ids.add(wid)
        return 0

    cdef int _claim_container(self, mu_Id wid, str what) except -1:
        """As _claim, for containers. A repeated begin overwrites the
        container's head jump, silently dropping the first instance's commands."""
        key = ("container", wid)
        if key in self._frame_ids:
            raise DuplicateIDError(f"{what} was already begun this frame")
        self._frame_ids.add(key)
        return 0

    cdef void _open(self, str tag):
        self._scopes.append(tag)

    cdef int _close(self, str tag) except -1:
        if not self._scopes or self._scopes[-1] != tag:
            top = self._scopes[-1] if self._scopes else "nothing"
            raise RuntimeError(f"closing {tag}, but the innermost open scope is {top}")
        self._scopes.pop()
        return 0

    cdef mu_Id _hash(self, bytes data):
        return mu_get_id(self.ptr, <const char*>data, len(data))

    cdef bytes _widget_key(self, object key):
        """Return `key` as bytes, or a key from the caller's code location.

        The default key is (code object, bytecode offset, occurrence), so it
        changes only when the same call site runs more than once in a scope,
        e.g. in a loop.
        """
        cdef mu_Id scope
        if key is not None:
            return _to_bytes(key)
        frame = sys._getframe(0)  # nearest Python frame: the caller
        scope = self.ptr.id_stack.items[self.ptr.id_stack.idx - 1] if self.ptr.id_stack.idx else 0
        site = (scope, id(frame.f_code), frame.f_lasti)
        n = self._auto_ids.get(site, 0)
        self._auto_ids[site] = n + 1
        return b"#%x:%x:%d" % (id(frame.f_code), frame.f_lasti, n)

    cdef void _flush_text(self):
        """Move pending input into microui's buffer, cutting on a UTF-8 boundary."""
        cdef Py_ssize_t used = strlen(self.ptr.input_text)
        cdef Py_ssize_t room = <Py_ssize_t>sizeof(self.ptr.input_text) - 1 - used
        cdef Py_ssize_t cut = _utf8_cut(self._pending_text, max(room, 0))
        cdef bytes chunk
        if cut <= 0:
            return
        chunk = self._pending_text[:cut]
        memcpy(self.ptr.input_text + used, <const char*>chunk, cut)
        self.ptr.input_text[used + cut] = 0
        self._pending_text = self._pending_text[cut:]

    cdef int _finish_copy(self, int op, bytes before) except -1:
        """If the textbox just called served copy/cut request `op`, put the
        selected bytes of its input text `before` on the clipboard."""
        cdef mu_Context* c = self.ptr
        if op and c.text_op == 0 and c.clip_end > c.clip_start:
            set_clipboard_text(before[c.clip_start:c.clip_end].decode('utf-8', 'replace'))
        return 0

    # ------------------------------------------------------------------
    # Frame lifecycle

    def begin(self):
        """Start a frame. Pair with end(), or use `with ctx:`.

        Raises:
            RuntimeError: If a frame is already in progress.
        """
        if self._in_frame:
            raise RuntimeError("begin() called twice without end()")
        mu_begin(self.ptr)
        self._in_frame = True
        self.current_command = NULL
        self._auto_ids.clear()
        self._frame_ids.clear()
        self._focus_order = []
        self._frame_images = []
        self._flush_text()

    def end(self):
        """Finish the frame and prepare its command list.

        Raises:
            RuntimeError: If no frame is in progress, or scopes are still open.
                In the second case the frame is discarded.
        """
        cdef mu_Context* c = self.ptr
        if not self._in_frame:
            raise RuntimeError("end() called without begin()")
        if self._scopes or c.container_stack.idx or c.clip_stack.idx or c.id_stack.idx or c.layout_stack.idx:
            names = ", ".join(self._scopes) or "microui stacks"
            self.abort_frame()
            raise RuntimeError(f"end() with unclosed scopes: {names}")
        cdef bint tab = c.key_pressed & MU_KEY_TAB
        cdef bint back = c.key_down & MU_KEY_SHIFT
        cdef mu_Id focus = c.focus
        mu_end(self.ptr)
        self._in_frame = False
        self.ptr.text_op = 0
        order = self._focus_order
        if tab and order:
            if focus in order:
                i = (order.index(focus) + (-1 if back else 1)) % len(order)
            else:
                i = len(order) - 1 if back else 0
            mu_set_focus(c, order[i])

    def abort_frame(self):
        """Discard the current frame instead of calling end().

        Resets the stacks, drops the frame's commands, and clears per-frame
        input as end() would. mu_end() cannot be used here: it aborts on
        non-empty stacks and patches root containers that never finished.
        """
        self.ptr.container_stack.idx = 0
        self.ptr.clip_stack.idx = 0
        self.ptr.id_stack.idx = 0
        self.ptr.layout_stack.idx = 0
        self.ptr.command_list.idx = 0
        self.ptr.root_list.idx = 0
        self.ptr.updated_focus = 0
        self.ptr.key_pressed = 0
        self.ptr.input_text[0] = 0
        self.ptr.mouse_pressed = 0
        self.ptr.scroll_delta = mu_vec2(0, 0)
        self.ptr.last_mouse_pos = self.ptr.mouse_pos
        self.current_command = NULL
        self._scopes.clear()
        self._in_frame = False
        self.ptr.text_op = 0

    def __enter__(self):
        """`with ctx:` calls begin()."""
        self.begin()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Call end(), or abort_frame() if the body raised."""
        if exc_type is None:
            self.end()
        elif self._in_frame:
            self.abort_frame()
        return None

    @property
    def in_frame(self) -> bool:
        """True between begin() and end()."""
        return self._in_frame

    # ------------------------------------------------------------------
    # IDs and clipping

    def set_focus(self, unsigned int id):
        """Give keyboard focus to control `id`."""
        mu_set_focus(self.ptr, id)

    def get_id(self, data) -> int:
        """Hash `data` (str, bytes, or str()-able) with the current ID scope."""
        return self._hash(_to_bytes(data))

    def push_id(self, data):
        """Push an ID scope. Prefer `with ctx.id_scope(data):`."""
        cdef bytes bdata = _to_bytes(data)
        self._reserve(1)
        mu_push_id(self.ptr, <const char*>bdata, len(bdata))
        self._open("id")

    def pop_id(self):
        """Pop the scope opened by push_id()."""
        self._close("id")
        mu_pop_id(self.ptr)

    def push_clip_rect(self, Rect rect):
        """Intersect the clip rect with `rect` until pop_clip_rect()."""
        self._require_clip()
        self._reserve(0, 1)
        mu_push_clip_rect(self.ptr, rect.to_c())
        self._open("clip")

    def pop_clip_rect(self):
        """Pop the clip rect pushed by push_clip_rect()."""
        self._close("clip")
        mu_pop_clip_rect(self.ptr)

    def get_clip_rect(self) -> Rect:
        """Current clip rect."""
        self._require_clip()
        return Rect.from_c(mu_get_clip_rect(self.ptr))

    def check_clip(self, Rect rect) -> int:
        """0 if `rect` is visible, else `Clip.PART` or `Clip.ALL`."""
        self._require_clip()
        return mu_check_clip(self.ptr, rect.to_c())

    # ------------------------------------------------------------------
    # Input

    def input_mousemove(self, int x, int y):
        mu_input_mousemove(self.ptr, x, y)

    def input_mousedown(self, int x, int y, int btn):
        mu_input_mousedown(self.ptr, x, y, btn)

    def input_mouseup(self, int x, int y, int btn):
        mu_input_mouseup(self.ptr, x, y, btn)

    def input_scroll(self, int x, int y):
        mu_input_scroll(self.ptr, x, y)

    def input_keydown(self, int key):
        mu_input_keydown(self.ptr, key)

    def input_keyup(self, int key):
        mu_input_keyup(self.ptr, key)

    def input_text(self, str text):
        """Queue typed text.

        microui holds 31 bytes per frame and aborts beyond that. Excess is
        carried into following frames; at most 64 KB is kept pending.
        """
        cdef bytes btext = text.encode('utf-8').split(b"\0", 1)[0]
        if len(self._pending_text) + len(btext) > _MAX_PENDING_TEXT:
            raise ValueError("too much pending text input")
        self._pending_text += btext
        self._flush_text()

    def input_copy(self):
        """Copy the focused textbox's selection to the clipboard during the next frame."""
        self.ptr.text_op |= MU_TEXTOP_COPY

    def input_cut(self):
        """As input_copy(), then delete the selection."""
        self.ptr.text_op |= MU_TEXTOP_CUT

    def input_select_all(self):
        """Select all text of the focused textbox during the next frame."""
        self.ptr.text_op |= MU_TEXTOP_SELECTALL

    def input_paste(self):
        """Type the clipboard text into the focused textbox."""
        self.input_text(get_clipboard_text())

    # ------------------------------------------------------------------
    # Layout

    def layout_row(self, widths, int height):
        """Start a row of `len(widths)` cells; None means one cell per call.

        Widths: positive is pixels, 0 is the default width, negative is
        relative to the right edge.

        Raises:
            ValueError: If more than 16 widths are given, or one is not an int.
        """
        cdef int c_widths[MU_MAX_WIDTHS]
        cdef int* wptr = NULL
        cdef int items = 0
        cdef int i
        self._require_layout()
        if widths is not None:
            items = len(widths)
            if items > MU_MAX_WIDTHS:
                raise ValueError(f"Too many width entries (max {MU_MAX_WIDTHS})")
            for i in range(items):
                try:
                    c_widths[i] = widths[i]
                except (TypeError, OverflowError):
                    raise ValueError(f"Invalid width value at index {i}: {widths[i]!r}")
            wptr = c_widths
        mu_layout_row(self.ptr, items, wptr, height)

    def layout_width(self, int width):
        self._require_layout()
        mu_layout_width(self.ptr, width)

    def layout_height(self, int height):
        self._require_layout()
        mu_layout_height(self.ptr, height)

    def layout_begin_column(self):
        """Start a nested column in the next cell. Prefer `with ctx.column():`."""
        self._require_layout()
        self._reserve(0, 0, 1)
        mu_layout_begin_column(self.ptr)
        self._open("column")

    def layout_end_column(self):
        self._close("column")
        mu_layout_end_column(self.ptr)

    def layout_set_next(self, Rect rect, int relative):
        """Place the next widget at `rect`: window-relative if `relative`, else absolute."""
        self._require_layout()
        mu_layout_set_next(self.ptr, rect.to_c(), relative)

    def layout_next(self) -> Rect:
        """Consume and return the next cell."""
        self._require_layout()
        return Rect.from_c(mu_layout_next(self.ptr))

    # ------------------------------------------------------------------
    # Widgets

    def text(self, str text):
        """Draw word-wrapped text across the row width."""
        cdef bytes btext = text.encode('utf-8')
        # One text command (plus two clip commands) per wrapped line; a line
        # break needs a space or newline.
        cdef Py_ssize_t lines = btext.count(b" ") + btext.count(b"\n") + 1
        self._require_layout()
        self._reserve(0, 0, 1, 0, 0, len(btext) + lines * _TEXT_LINE_COST)
        mu_text(self.ptr, btext)

    def label(self, str text):
        cdef bytes btext = text.encode('utf-8')
        self._require_layout()
        self._reserve(0, 1, 0, 0, 0, len(btext))
        mu_label(self.ptr, btext)

    def button(self, str label, int icon=0, int opt=0, key=None) -> int:
        """Return nonzero (`Result.SUBMIT`) on click.

        Args:
            key (optional): ID key. Defaults to `label`, or `icon` if `label` is empty.
        """
        cdef bytes blabel = label.encode('utf-8')
        cdef bytes bkey
        cdef const char* clabel = <const char*>blabel if blabel else NULL
        cdef int result
        self._require_layout()
        self._reserve(1, 1, 0, 0, 0, len(blabel))
        if key is None:
            if clabel != NULL:
                self._claim(self._hash(blabel), f"button {label!r}")
            else:
                self._claim(mu_get_id(self.ptr, &icon, sizeof(icon)), f"icon button {icon}")
            return mu_button_ex(self.ptr, clabel, icon, opt)
        bkey = _to_bytes(key)
        self._claim(self._hash(bkey), f"button key {key!r}")
        mu_push_id(self.ptr, <const char*>bkey, len(bkey))
        result = mu_button_ex(self.ptr, clabel, icon, opt)
        mu_pop_id(self.ptr)
        return result

    def checkbox(self, str label, state, key=None) -> tuple:
        """Return (result, new_state).

        Args:
            key (optional): ID key. Defaults to `label`.
        """
        cdef bytes blabel = label.encode('utf-8')
        cdef bytes bkey = _to_bytes(label if key is None else key)
        cdef int result
        self._require_layout()
        self._reserve(1, 1, 0, 0, 0, len(blabel))
        self._claim(self._hash(bkey), f"checkbox {label!r}")
        self._int_slot = 1 if state else 0
        mu_push_id(self.ptr, <const char*>bkey, len(bkey))
        result = mu_checkbox(self.ptr, blabel, &self._int_slot)
        mu_pop_id(self.ptr)
        return (result, self._int_slot)

    def textbox(self, str buf, int bufsz=256, int opt=0, key=None) -> tuple:
        """Alias of textbox_ex()."""
        return self.textbox_ex(buf, bufsz, opt, key)

    def textbox_ex(self, str buf, int bufsz=256, int opt=0, key=None) -> tuple:
        """Return (result, new_text). Pass the text back in each frame.

        Args:
            buf (str): Current text
            bufsz (int): Buffer size in bytes, including the terminator (2..1MB).
                Longer text is cut at the last whole character that fits.
            opt (int, optional): Option flags
            key (optional): ID key. Defaults to the caller's code location.

        Raises:
            ValueError: If bufsz is out of range
            MemoryError: If allocation fails
        """
        if bufsz < 2:
            raise ValueError("Buffer too small (minimum 2 bytes)")
        if bufsz > 1024 * 1024:
            raise ValueError("Buffer size too large (max 1MB)")
        cdef bytes b_buf = buf.encode('utf-8')
        cdef bytes bkey = self._widget_key(key)
        cdef int copy_len = _utf8_cut(b_buf, bufsz - 1)
        cdef int result
        cdef int op = self.ptr.text_op & (MU_TEXTOP_COPY | MU_TEXTOP_CUT)
        cdef mu_Id wid
        cdef char* c_buf
        self._require_layout()
        self._reserve(0, 1, 0, 0, 0, bufsz)
        wid = self._hash(bkey)
        self._claim(wid, "textbox")
        c_buf = <char*>malloc(bufsz)
        if c_buf == NULL:
            raise MemoryError("Failed to allocate textbox buffer")
        try:
            if copy_len > 0:
                memcpy(c_buf, <const char*>b_buf, copy_len)
            c_buf[copy_len] = 0
            result = mu_textbox_raw(self.ptr, c_buf, bufsz, wid, mu_layout_next(self.ptr), opt)
            text = c_buf.decode('utf-8', errors='replace')
        finally:
            free(c_buf)
        self._focus_order.append(wid)
        self._finish_copy(op, b_buf[:copy_len] if op else None)
        return (result, text)

    def slider(self, float value, float low, float high, float step=0,
               str fmt="%.2f", int opt=0, key=None) -> tuple:
        """Return (result, new_value).

        Args:
            fmt (str): One %f/%e/%g conversion, width <= 99, precision <= 20
            key (optional): ID key. Defaults to the caller's code location.
        """
        cdef bytes bfmt = _check_fmt(fmt)
        cdef bytes bkey = self._widget_key(key)
        cdef int result
        self._require_layout()
        self._reserve(1, 1, 0, 0, 0, MU_MAX_FMT)
        self._claim(self._hash(bkey), "slider")
        self._real_slot = value
        mu_push_id(self.ptr, <const char*>bkey, len(bkey))
        result = mu_slider_ex(self.ptr, &self._real_slot, low, high, step, bfmt, opt)
        mu_pop_id(self.ptr)
        return (result, self._real_slot)

    def number(self, float value, float step, str fmt="%.2f", int opt=0, key=None) -> tuple:
        """Return (result, new_value). Drag to change; shift-click to type.

        Args:
            fmt (str): One %f/%e/%g conversion, width <= 99, precision <= 20
            key (optional): ID key. Defaults to the caller's code location.
        """
        cdef bytes bfmt = _check_fmt(fmt)
        cdef bytes bkey = self._widget_key(key)
        cdef int result
        self._require_layout()
        self._reserve(1, 1, 0, 0, 0, MU_MAX_FMT)
        self._claim(self._hash(bkey), "number")
        self._real_slot = value
        mu_push_id(self.ptr, <const char*>bkey, len(bkey))
        result = mu_number_ex(self.ptr, &self._real_slot, step, bfmt, opt)
        mu_pop_id(self.ptr)
        return (result, self._real_slot)

    cdef int _begin_header(self, bytes blabel, str label, str what) except -1:
        self._require_layout()
        self._reserve(1, 1, 0, 0, 0, len(blabel))
        cdef mu_Id wid = self._hash(blabel)
        self._claim(wid, f"{what} {label!r}")
        self._require_pool_slot(self.ptr.treenode_pool, MU_TREENODEPOOL_SIZE, wid,
                                "expanded headers/tree nodes")
        return 0

    def header(self, str label, int opt=0) -> int:
        """Collapsible header; returns nonzero while expanded. No end call."""
        cdef bytes blabel = label.encode('utf-8')
        self._begin_header(blabel, label, "header")
        return mu_header_ex(self.ptr, blabel, opt)

    def begin_treenode(self, str label, int opt=0) -> int:
        """Returns nonzero while expanded; then call end_treenode()."""
        cdef bytes blabel = label.encode('utf-8')
        self._begin_header(blabel, label, "tree node")
        cdef int res = mu_begin_treenode_ex(self.ptr, blabel, opt)
        if res:
            self._open("treenode")
        return res

    def end_treenode(self):
        self._close("treenode")
        mu_end_treenode(self.ptr)

    # ------------------------------------------------------------------
    # Containers

    cdef int _begin_root(self, bytes bname, str name, int opt, str what) except -1:
        self._require_frame()
        self._reserve(1, 3, 1, 1, 1, len(bname))
        cdef mu_Id wid = self._hash(bname)
        self._claim_container(wid, f"{what} {name!r}")
        if not opt & MU_OPT_CLOSED:
            self._require_pool_slot(self.ptr.container_pool, MU_CONTAINERPOOL_SIZE, wid, "containers")
        return 0

    def begin_window(self, str title, Rect rect, int opt=0) -> int:
        """Returns nonzero if open; then call end_window(). Prefer ctx.window().

        Raises:
            ValueError: If title is empty or rect has negative size
        """
        if not title:
            raise ValueError("Window title cannot be empty")
        if rect.w < 0 or rect.h < 0:
            raise ValueError("Window dimensions cannot be negative")
        cdef bytes btitle = title.encode('utf-8')
        self._begin_root(btitle, title, opt, "window")
        cdef int res = mu_begin_window_ex(self.ptr, btitle, rect.to_c(), opt)
        if res:
            self._open("window")
        return res

    def end_window(self):
        self._close("window")
        mu_end_window(self.ptr)

    def window(self, str title, int x, int y, int w, int h, int opt=0):
        """`with ctx.window(title, x, y, w, h) as win:` -- check `win.is_open`."""
        return Window(self, title, Rect(x, y, w, h), opt)

    def open_popup(self, str name):
        """Open popup `name` at the mouse position."""
        cdef bytes bname = name.encode('utf-8')
        self._require_pool_slot(self.ptr.container_pool, MU_CONTAINERPOOL_SIZE,
                                self._hash(bname), "containers")
        mu_open_popup(self.ptr, bname)

    def begin_popup(self, str name) -> int:
        """Returns nonzero if open; then call end_popup(). Prefer ctx.popup()."""
        cdef bytes bname = name.encode('utf-8')
        self._begin_root(bname, name, MU_OPT_CLOSED, "popup")
        cdef int res = mu_begin_popup(self.ptr, bname)
        if res:
            self._open("popup")
        return res

    def end_popup(self):
        self._close("popup")
        mu_end_popup(self.ptr)

    def begin_panel(self, str name, int opt=0):
        """Scrollable region in the next cell; call end_panel(). Prefer ctx.panel().

        Raises:
            ValueError: If opt includes Option.CLOSED (microui dereferences NULL).
        """
        if opt & MU_OPT_CLOSED:
            raise ValueError("Option.CLOSED is not valid for panels")
        cdef bytes bname = name.encode('utf-8')
        self._require_layout()
        self._reserve(1, 2, 1, 1, 0, len(bname))
        cdef mu_Id wid = self._hash(bname)
        self._claim_container(wid, f"panel {name!r}")
        self._require_pool_slot(self.ptr.container_pool, MU_CONTAINERPOOL_SIZE, wid, "containers")
        mu_begin_panel_ex(self.ptr, bname, opt)
        self._open("panel")

    def end_panel(self):
        self._close("panel")
        mu_end_panel(self.ptr)

    def get_current_container(self):
        """Innermost open window/panel/popup, or None."""
        if self.ptr.container_stack.idx == 0:
            return None
        return ContainerWrapper.from_ptr(mu_get_current_container(self.ptr), self)

    def get_container(self, str name):
        """Container for window `name`, created if absent."""
        cdef bytes bname = name.encode('utf-8')
        self._require_pool_slot(self.ptr.container_pool, MU_CONTAINERPOOL_SIZE,
                                self._hash(bname), "containers")
        return ContainerWrapper.from_ptr(mu_get_container(self.ptr, bname), self)

    def bring_to_front(self, ContainerWrapper container):
        """Raise a window or popup above all others."""
        if container.ptr == NULL:
            raise ValueError("Container is not valid")
        mu_bring_to_front(self.ptr, container.ptr)

    # Context managers. Each closes its scope when the body exits. If the
    # body raised, a failure while closing is dropped so the original
    # exception propagates.
    def treenode(self, str label, int opt=0):
        """`with ctx.treenode(label) as expanded:`"""
        cdef int opened = self.begin_treenode(label, opt)
        return _scoped(bool(opened), self.end_treenode if opened else None)

    def popup(self, str name):
        """`with ctx.popup(name) as is_open:`"""
        cdef int opened = self.begin_popup(name)
        return _scoped(bool(opened), self.end_popup if opened else None)

    def panel(self, str name, int opt=0):
        """`with ctx.panel(name) as container:`"""
        self.begin_panel(name, opt)
        return _scoped(self.get_current_container(), self.end_panel)

    def column(self):
        """`with ctx.column():`"""
        self.layout_begin_column()
        return _scoped(None, self.layout_end_column)

    def id_scope(self, data):
        """`with ctx.id_scope(key):` -- scope every ID in the block."""
        self.push_id(data)
        return _scoped(None, self.pop_id)

    # ------------------------------------------------------------------
    # Drawing (inside a window or panel; queued in the command list)

    def draw_rect(self, Rect rect, Color color):
        self._require_clip()
        self._reserve()
        mu_draw_rect(self.ptr, rect.to_c(), color.to_c())

    def draw_box(self, Rect rect, Color color):
        """Draw a 1-pixel outline."""
        self._require_clip()
        self._reserve()
        mu_draw_box(self.ptr, rect.to_c(), color.to_c())

    def draw_text(self, str text, Vec2 pos, Color color):
        """Draw text at `pos` with the style font."""
        cdef bytes btext = text.encode('utf-8')
        self._require_clip()
        self._reserve(0, 0, 0, 0, 0, len(btext))
        mu_draw_text(self.ptr, self.ptr.style.font, btext, len(btext), pos.to_c(), color.to_c())

    def draw_icon(self, int id, Rect rect, Color color):
        """Draw `Icon` `id` centered in `rect`."""
        if not 0 < id < MU_ICON_MAX:
            raise ValueError("Icon id out of range")
        self._require_clip()
        self._reserve()
        mu_draw_icon(self.ptr, id, rect.to_c(), color.to_c())

    def draw_image(self, Image image, Rect rect, Color color=None):
        """Draw `image` scaled into `rect`, multiplied by `color` (default white)."""
        image._require_valid()
        self._require_clip()
        self._reserve()
        mu_draw_image(self.ptr, image._id, rect.to_c(),
                      mu_color(255, 255, 255, 255) if color is None else color.to_c())
        self._frame_images.append(image)

    def image(self, Image image, Color color=None) -> Rect:
        """Draw `image` filling the next layout cell; return the cell."""
        self._require_layout()
        cdef Rect r = Rect.from_c(mu_layout_next(self.ptr))
        self.draw_image(image, r, color)
        return r

    # Custom widget primitives
    def mouse_over(self, Rect rect) -> int:
        """Nonzero if the mouse is over `rect` within the current clip and window."""
        self._require_clip()
        return mu_mouse_over(self.ptr, rect.to_c())

    def update_control(self, unsigned int id, Rect rect, int opt=0):
        """Update hover/focus state of control `id` occupying `rect`."""
        self._require_clip()
        mu_update_control(self.ptr, id, rect.to_c(), opt)

    def draw_control_frame(self, unsigned int id, Rect rect, int colorid, int opt=0):
        """Draw a control frame; `colorid` shifts to hover/focus variants."""
        if not 0 <= colorid < MU_COLOR_MAX - 2:
            raise IndexError("Color index out of range")
        self._require_clip()
        self._reserve()
        mu_draw_control_frame(self.ptr, id, rect.to_c(), colorid, opt)

    def draw_control_text(self, str text, Rect rect, int colorid, int opt=0):
        """Draw text clipped and aligned within `rect`."""
        if not 0 <= colorid < MU_COLOR_MAX:
            raise IndexError("Color index out of range")
        cdef bytes btext = text.encode('utf-8')
        self._require_clip()
        self._reserve(0, 1, 0, 0, 0, len(btext))
        mu_draw_control_text(self.ptr, btext, rect.to_c(), colorid, opt)

    # ------------------------------------------------------------------
    # Commands (after end())

    def reset_command_iterator(self):
        """Restart next_command() from the first command."""
        self.current_command = NULL

    def next_command(self):
        """Return the next command of the last finished frame, or None.

        Raises:
            RuntimeError: During a frame; jump targets are set by end().
        """
        if self._in_frame:
            raise RuntimeError("commands are available after end()")
        if mu_next_command(self.ptr, &self.current_command) == 0 or self.current_command == NULL:
            return None
        if self.current_command.type == MU_COMMAND_RECT:
            return RectCommand.from_c(self.current_command.rect)
        elif self.current_command.type == MU_COMMAND_TEXT:
            return TextCommand.from_ptr(&self.current_command.text)
        elif self.current_command.type == MU_COMMAND_ICON:
            return IconCommand.from_c(self.current_command.icon)
        elif self.current_command.type == MU_COMMAND_IMAGE:
            return ImageCommand.from_c(self.current_command.image)
        elif self.current_command.type == MU_COMMAND_CLIP:
            return ClipCommand.from_c(self.current_command.clip)
        elif self.current_command.type == MU_COMMAND_JUMP:
            return JumpCommand.from_c(self.current_command.jump)
        return BaseCommand.from_c(self.current_command.base)

    # Utility constructors
    @staticmethod
    def vec2(int x, int y) -> Vec2:
        return Vec2.from_c(mu_vec2(x, y))

    @staticmethod
    def rect(int x, int y, int w, int h) -> Rect:
        return Rect.from_c(mu_rect(x, y, w, h))

    @staticmethod
    def color(int r, int g, int b, int a=255) -> Color:
        return Color(r, g, b, a)

    # ------------------------------------------------------------------
    # Read-only state

    @property
    def hover(self) -> int:
        """ID of the hovered control, or 0."""
        return self.ptr.hover

    @property
    def focus(self) -> int:
        """ID of the focused control, or 0."""
        return self.ptr.focus

    @property
    def last_id(self) -> int:
        """ID most recently produced by get_id() or a widget."""
        return self.ptr.last_id

    @property
    def mouse_pos(self) -> Vec2:
        return Vec2.from_c(self.ptr.mouse_pos)

    @property
    def mouse_delta(self) -> Vec2:
        return Vec2.from_c(self.ptr.mouse_delta)

    @property
    def mouse_down(self) -> int:
        """Bitmask of `Mouse` buttons held."""
        return self.ptr.mouse_down

    @property
    def mouse_pressed(self) -> int:
        """Bitmask of `Mouse` buttons pressed this frame."""
        return self.ptr.mouse_pressed

    @property
    def key_down(self) -> int:
        """Bitmask of `Key` modifiers held."""
        return self.ptr.key_down

    @property
    def key_pressed(self) -> int:
        """Bitmask of `Key` keys pressed this frame."""
        return self.ptr.key_pressed


# Window context manager class
cdef class Window:
    """Context manager for microui windows.

    This class provides automatic window management using Python's context manager
    protocol. When entering the context, it calls begin_window(), and when exiting,
    it calls end_window().

    Attributes:
        is_open (bool): True if the window is open and should be processed
    """
    cdef Context ctx
    cdef str _title
    cdef Rect _rect
    cdef int _opt
    cdef public bint is_open

    def __cinit__(self, Context ctx, str title, Rect rect, int opt=0):
        """Initialize window context manager.

        Args:
            ctx (Context): The microui context
            title (str): Window title
            rect (Rect): Window rectangle (position and size)
            opt (int): Window options flags
        """
        self.ctx = ctx
        self._title = title
        self._rect = rect
        self._opt = opt
        self.is_open = False

    @property
    def title(self) -> str:
        """Get the window title."""
        return self._title

    @property
    def rect(self) -> Rect:
        """Get the window rectangle."""
        return self._rect

    @property
    def opt(self) -> int:
        """Get the window options."""
        return self._opt

    def __enter__(self):
        """Enter the window context - calls begin_window().

        Returns:
            Window: Returns self to allow access to is_open property
        """
        self.is_open = bool(self.ctx.begin_window(self._title, self._rect, self._opt))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the window context - calls end_window().

        This ensures end_window() is called even if an exception occurs.

        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)

        Returns:
            None: Does not suppress exceptions
        """
        if not self.is_open:
            return None
        self.is_open = False
        if exc_type is None:
            self.ctx.end_window()
        else:
            try:
                self.ctx.end_window()
            except RuntimeError:
                pass  # keep the original exception
        return None


# Container wrapper class
cdef class ContainerWrapper:
    """View of a microui container (window, panel, popup).

    Field reads return copies; assign a whole value to write through,
    e.g. `win.rect = Rect(...)`, not `win.rect.w = ...`.
    """
    cdef mu_Container* ptr
    cdef object _ref  # keeps the owning Context alive

    def __cinit__(self):
        self.ptr = NULL

    @staticmethod
    cdef ContainerWrapper from_ptr(mu_Container* ptr, object ref=None):
        cdef ContainerWrapper wrapper = ContainerWrapper.__new__(ContainerWrapper)
        wrapper.ptr = ptr
        wrapper._ref = ref
        return wrapper

    @property
    def rect(self) -> Rect:
        if self.ptr == NULL:
            return Rect(0, 0, 0, 0)
        return Rect.from_c(self.ptr.rect)

    @rect.setter
    def rect(self, Rect value):
        if self.ptr != NULL:
            self.ptr.rect = value.to_c()

    @property
    def body(self) -> Rect:
        if self.ptr == NULL:
            return Rect(0, 0, 0, 0)
        return Rect.from_c(self.ptr.body)

    @property
    def content_size(self) -> Vec2:
        if self.ptr == NULL:
            return Vec2(0, 0)
        return Vec2.from_c(self.ptr.content_size)

    @property
    def scroll(self) -> Vec2:
        if self.ptr == NULL:
            return Vec2(0, 0)
        return Vec2.from_c(self.ptr.scroll)

    @scroll.setter
    def scroll(self, Vec2 value):
        if self.ptr != NULL:
            self.ptr.scroll = value.to_c()

    @property
    def zindex(self) -> int:
        if self.ptr == NULL:
            return 0
        return self.ptr.zindex

    @property
    def open(self) -> int:
        if self.ptr == NULL:
            return 0
        return self.ptr.open

    @open.setter
    def open(self, value):
        if self.ptr != NULL:
            self.ptr.open = 1 if value else 0


# Command wrapper classes
cdef class BaseCommand:
    cdef mu_BaseCommand _cmd

    @staticmethod
    cdef BaseCommand from_c(mu_BaseCommand cmd):
        cdef BaseCommand result = BaseCommand.__new__(BaseCommand)
        result._cmd = cmd
        return result

    @property
    def type(self) -> int:
        return self._cmd.type

    @property
    def size(self) -> int:
        return self._cmd.size


cdef class RectCommand:
    cdef mu_RectCommand _cmd

    @staticmethod
    cdef RectCommand from_c(mu_RectCommand cmd):
        cdef RectCommand result = RectCommand.__new__(RectCommand)
        result._cmd = cmd
        return result

    @property
    def type(self) -> int:
        return self._cmd.base.type

    @property
    def rect(self) -> Rect:
        return Rect.from_c(self._cmd.rect)

    @property
    def color(self) -> Color:
        return Color.from_c(self._cmd.color)


cdef class TextCommand:
    # Copied on creation: the command buffer is overwritten next frame.
    cdef int _type
    cdef mu_Vec2 _pos
    cdef mu_Color _color
    cdef str _text

    @staticmethod
    cdef TextCommand from_ptr(mu_TextCommand* cmd):
        cdef TextCommand result = TextCommand.__new__(TextCommand)
        result._type = cmd.base.type
        result._pos = cmd.pos
        result._color = cmd.color
        result._text = (<const char*>cmd.str).decode('utf-8', errors='replace')
        return result

    @property
    def type(self) -> int:
        return self._type

    @property
    def font(self):
        """Always None: the bundled renderer has one font."""
        return None

    @property
    def pos(self) -> Vec2:
        return Vec2.from_c(self._pos)

    @property
    def color(self) -> Color:
        return Color.from_c(self._color)

    @property
    def text(self) -> str:
        return self._text


cdef class IconCommand:
    cdef mu_IconCommand _cmd

    @staticmethod
    cdef IconCommand from_c(mu_IconCommand cmd):
        cdef IconCommand result = IconCommand.__new__(IconCommand)
        result._cmd = cmd
        return result

    @property
    def type(self) -> int:
        return self._cmd.base.type

    @property
    def rect(self) -> Rect:
        return Rect.from_c(self._cmd.rect)

    @property
    def icon_id(self) -> int:
        return self._cmd.id

    @property
    def color(self) -> Color:
        return Color.from_c(self._cmd.color)


cdef class ImageCommand:
    cdef mu_ImageCommand _cmd

    @staticmethod
    cdef ImageCommand from_c(mu_ImageCommand cmd):
        cdef ImageCommand result = ImageCommand.__new__(ImageCommand)
        result._cmd = cmd
        return result

    @property
    def type(self) -> int:
        return self._cmd.base.type

    @property
    def rect(self) -> Rect:
        return Rect.from_c(self._cmd.rect)

    @property
    def image_id(self) -> int:
        return self._cmd.id

    @property
    def color(self) -> Color:
        return Color.from_c(self._cmd.color)


cdef class ClipCommand:
    cdef mu_ClipCommand _cmd

    @staticmethod
    cdef ClipCommand from_c(mu_ClipCommand cmd):
        cdef ClipCommand result = ClipCommand.__new__(ClipCommand)
        result._cmd = cmd
        return result

    @property
    def type(self) -> int:
        return self._cmd.base.type

    @property
    def rect(self) -> Rect:
        return Rect.from_c(self._cmd.rect)


cdef class JumpCommand:
    cdef mu_JumpCommand _cmd

    @staticmethod
    cdef JumpCommand from_c(mu_JumpCommand cmd):
        cdef JumpCommand result = JumpCommand.__new__(JumpCommand)
        result._cmd = cmd
        return result

    @property
    def type(self) -> int:
        return self._cmd.base.type


# Constants for easy access
class Clip:
    PART = MU_CLIP_PART
    ALL = MU_CLIP_ALL

class Command:
    JUMP = MU_COMMAND_JUMP
    CLIP = MU_COMMAND_CLIP
    RECT = MU_COMMAND_RECT
    TEXT = MU_COMMAND_TEXT
    ICON = MU_COMMAND_ICON
    IMAGE = MU_COMMAND_IMAGE
    MAX = MU_COMMAND_MAX

class ColorIndex:
    TEXT = MU_COLOR_TEXT
    BORDER = MU_COLOR_BORDER
    WINDOWBG = MU_COLOR_WINDOWBG
    TITLEBG = MU_COLOR_TITLEBG
    TITLETEXT = MU_COLOR_TITLETEXT
    PANELBG = MU_COLOR_PANELBG
    BUTTON = MU_COLOR_BUTTON
    BUTTONHOVER = MU_COLOR_BUTTONHOVER
    BUTTONFOCUS = MU_COLOR_BUTTONFOCUS
    BASE = MU_COLOR_BASE
    BASEHOVER = MU_COLOR_BASEHOVER
    BASEFOCUS = MU_COLOR_BASEFOCUS
    SCROLLBASE = MU_COLOR_SCROLLBASE
    SCROLLTHUMB = MU_COLOR_SCROLLTHUMB
    MAX = MU_COLOR_MAX

class Icon:
    CLOSE = MU_ICON_CLOSE
    CHECK = MU_ICON_CHECK
    COLLAPSED = MU_ICON_COLLAPSED
    EXPANDED = MU_ICON_EXPANDED
    MAX = MU_ICON_MAX

class Result:
    ACTIVE = MU_RES_ACTIVE
    SUBMIT = MU_RES_SUBMIT
    CHANGE = MU_RES_CHANGE

class Option:
    ALIGNCENTER = MU_OPT_ALIGNCENTER
    ALIGNRIGHT = MU_OPT_ALIGNRIGHT
    NOINTERACT = MU_OPT_NOINTERACT
    NOFRAME = MU_OPT_NOFRAME
    NORESIZE = MU_OPT_NORESIZE
    NOSCROLL = MU_OPT_NOSCROLL
    NOCLOSE = MU_OPT_NOCLOSE
    NOTITLE = MU_OPT_NOTITLE
    HOLDFOCUS = MU_OPT_HOLDFOCUS
    AUTOSIZE = MU_OPT_AUTOSIZE
    POPUP = MU_OPT_POPUP
    CLOSED = MU_OPT_CLOSED
    EXPANDED = MU_OPT_EXPANDED

class Mouse:
    LEFT = MU_MOUSE_LEFT
    RIGHT = MU_MOUSE_RIGHT
    MIDDLE = MU_MOUSE_MIDDLE

class Key:
    SHIFT = MU_KEY_SHIFT
    CTRL = MU_KEY_CTRL
    ALT = MU_KEY_ALT
    BACKSPACE = MU_KEY_BACKSPACE
    RETURN = MU_KEY_RETURN
    ESCAPE = MU_KEY_ESCAPE
    DELETE = MU_KEY_DELETE
    LEFT = MU_KEY_LEFT
    RIGHT = MU_KEY_RIGHT
    UP = MU_KEY_UP
    DOWN = MU_KEY_DOWN
    HOME = MU_KEY_HOME
    END = MU_KEY_END
    TAB = MU_KEY_TAB


# Textbox class for persistent state
cdef class Textbox:
    """A persistent textbox widget with automatic memory management.

    This class provides a textbox that maintains its state between frames,
    including cursor position and selection. It handles memory allocation
    and cleanup automatically.

    Args:
        buffer_size (int, optional): Size of the internal buffer in bytes. Defaults to 128.
                                   Must be between 2 and 65536 bytes.

    Raises:
        ValueError: If buffer_size is invalid
        MemoryError: If memory allocation fails

    Example:
        >>> textbox = Textbox(256)
        >>> textbox.text = "Hello, World!"
        >>> result, new_text = textbox.update(ctx)
    """
    cdef char* buffer
    cdef int buffer_size
    cdef str current_text

    def __cinit__(self, buffer_size=128):
        """Initialize the textbox with the specified buffer size.

        Args:
            buffer_size (int, optional): Buffer size in bytes. Defaults to 128.

        Raises:
            ValueError: If buffer_size is invalid
            MemoryError: If memory allocation fails
        """
        buffer_size = operator.index(buffer_size)
        if buffer_size < 2:
            raise ValueError("Buffer size must be at least 2 bytes")
        if buffer_size > 65536:  # 64KB limit
            raise ValueError("Buffer size too large (max 64KB)")

        self.buffer_size = buffer_size
        self.buffer = <char*>malloc(buffer_size)
        if self.buffer == NULL:
            raise MemoryError("Failed to allocate textbox buffer")
        self.buffer[0] = 0  # null terminate
        self.current_text = ""

    def __dealloc__(self):
        if self.buffer != NULL:
            free(self.buffer)
            self.buffer = NULL

    def update(self, Context ctx, int opt=0) -> tuple:
        """Update the textbox and return (result, new_text).

        Args:
            ctx (Context): The microui context
            opt (int, optional): Textbox options flags. Defaults to 0.

        Returns:
            tuple: (result_flags, current_text)

        Raises:
            ValueError: If ctx is None
            RuntimeError: If buffer is corrupted
        """
        if ctx is None:
            raise ValueError("Context cannot be None")
        if self.buffer == NULL:
            raise RuntimeError("Textbox buffer is corrupted")

        ctx._require_layout()
        ctx._reserve(0, 1, 0, 0, 0, self.buffer_size)
        # Same ID mu_textbox_ex derives: the buffer address, unique per Textbox.
        cdef mu_Id wid = mu_get_id(ctx.ptr, &self.buffer, sizeof(self.buffer))
        ctx._claim(wid, "Textbox")
        cdef int op = ctx.ptr.text_op & (MU_TEXTOP_COPY | MU_TEXTOP_CUT)
        cdef bytes before = self.buffer[:strlen(self.buffer)] if op else None
        cdef int result = mu_textbox_ex(ctx.ptr, self.buffer, self.buffer_size, opt)
        self.current_text = self.buffer.decode('utf-8', errors='replace')
        ctx._focus_order.append(wid)
        ctx._finish_copy(op, before)

        return (result, self.current_text)

    @property
    def text(self) -> str:
        return self.current_text

    @text.setter
    def text(self, str value):
        """Set the textbox content, cut at the last whole character that fits."""
        if value is None:
            value = ""

        cdef bytes b_value = value.encode('utf-8')
        cdef int encoded_len = len(b_value)
        cdef int copy_len

        # Validate buffer has space for at least null terminator
        if self.buffer_size < 1:
            raise ValueError("Buffer too small")

        # Calculate safe copy length with explicit bounds check
        copy_len = _utf8_cut(b_value, max(self.buffer_size - 1, 0))
        if copy_len < 0:
            copy_len = 0

        # Only copy if we have valid data and space
        if copy_len > 0 and encoded_len > 0 and self.buffer != NULL:
            memcpy(self.buffer, <const char*>b_value, copy_len)

        # Always null terminate within buffer bounds
        if self.buffer != NULL and copy_len < self.buffer_size:
            self.buffer[copy_len] = 0

        # Update current text (potentially truncated)
        if copy_len < encoded_len:
            self.current_text = self.buffer[:copy_len].decode('utf-8')
        else:
            self.current_text = value


cdef class Image:
    """An RGBA texture for `Context.draw_image()` and `Context.image()`.

    Needs an open renderer window. Closing the window invalidates every
    Image; drawing or updating one afterwards raises.

    Args:
        width, height: Size in pixels.
        pixels: `width * height * 4` bytes of RGBA, top row first.
            Defaults to transparent black. From Pillow:
            `img.convert("RGBA").tobytes()`.

    Raises:
        RuntimeError: Without a window, or if the GPU rejects the texture.
        ValueError: If the size or pixel data length is wrong.
    """
    cdef unsigned _id
    cdef int _gen
    cdef readonly int width, height

    def __cinit__(self, int width, int height, pixels=None):
        self._id = 0
        if width <= 0 or height <= 0:
            raise ValueError("image dimensions must be positive")
        _require_window()
        cdef bytes data = self._check(width, height, pixels)
        self.width = width
        self.height = height
        self._id = r_image_create(<const unsigned char*>data, width, height)
        if self._id == 0:
            raise RuntimeError(f"cannot create a {width}x{height} texture")
        self._gen = r_generation()

    cdef bytes _check(self, int width, int height, pixels):
        cdef Py_ssize_t n = <Py_ssize_t>width * height * 4
        if pixels is None:
            return bytes(n)
        data = bytes(pixels)
        if len(data) != n:
            raise ValueError(f"expected {n} bytes of RGBA, got {len(data)}")
        return data

    cdef bint _valid(self):
        return self._id != 0 and self._gen == r_generation()

    cdef int _require_valid(self) except -1:
        if not self._valid():
            raise RuntimeError("image is closed, or its window was closed")
        return 0

    def update(self, pixels):
        """Replace the pixels; the size stays the same."""
        self._require_valid()
        cdef bytes data = self._check(self.width, self.height, pixels)
        if r_image_update(self._id, <const unsigned char*>data, self.width, self.height) != 0:
            raise RuntimeError("texture update failed")

    def close(self):
        """Free the texture now instead of at garbage collection."""
        if self._valid():
            r_image_destroy(self._id)
        self._id = 0

    @property
    def closed(self) -> bool:
        return not self._valid()

    def __dealloc__(self):
        if self._valid():
            r_image_destroy(self._id)

    def __repr__(self):
        return f"Image({self.width}x{self.height}{', closed' if self.closed else ''})"


def get_clipboard_text() -> str:
    """System clipboard text, or a process-local one while no window is open."""
    cdef char* s
    if not SDL_WasInit(SDL_INIT_VIDEO):
        return _clipboard
    s = SDL_GetClipboardText()
    if s == NULL:
        return ""
    try:
        return s[:strlen(s)].decode('utf-8', 'replace')
    finally:
        SDL_free(s)


def set_clipboard_text(str text):
    """Set the system clipboard, or a process-local one while no window is open."""
    global _clipboard
    cdef bytes b = text.encode('utf-8').split(b"\0", 1)[0]
    if not SDL_WasInit(SDL_INIT_VIDEO):
        _clipboard = b.decode('utf-8')
        return
    if SDL_SetClipboardText(b) != 0:
        raise RuntimeError(f"SDL_SetClipboardText failed: {SDL_GetError().decode('utf-8', 'replace')}")


class Cursor:
    ARROW = SDL_SYSTEM_CURSOR_ARROW
    IBEAM = SDL_SYSTEM_CURSOR_IBEAM
    WAIT = SDL_SYSTEM_CURSOR_WAIT
    CROSSHAIR = SDL_SYSTEM_CURSOR_CROSSHAIR
    SIZENWSE = SDL_SYSTEM_CURSOR_SIZENWSE
    SIZENESW = SDL_SYSTEM_CURSOR_SIZENESW
    SIZEWE = SDL_SYSTEM_CURSOR_SIZEWE
    SIZENS = SDL_SYSTEM_CURSOR_SIZENS
    SIZEALL = SDL_SYSTEM_CURSOR_SIZEALL
    NO = SDL_SYSTEM_CURSOR_NO
    HAND = SDL_SYSTEM_CURSOR_HAND


def set_cursor(int cursor):
    """Set the mouse cursor to a `Cursor` shape.

    Raises:
        ValueError: If `cursor` is not a `Cursor` value.
        RuntimeError: Without a window.
    """
    if not 0 <= cursor < SDL_NUM_SYSTEM_CURSORS:
        raise ValueError(f"unknown cursor {cursor}")
    _require_window()
    if _cursors[cursor] == NULL:
        _cursors[cursor] = SDL_CreateSystemCursor(cursor)
        if _cursors[cursor] == NULL:
            raise RuntimeError(f"cursor {cursor} unavailable: {SDL_GetError().decode('utf-8', 'replace')}")
    SDL_SetCursor(_cursors[cursor])


def renderer_get_scale() -> float:
    """Device pixels per logical pixel: 2.0 on most HiDPI displays, 1.0 without a window."""
    return r_get_scale()


# Renderer functions exposed as module-level functions
def renderer_init():
    """Initialize the renderer with an 800x600 untitled window."""
    renderer_init_window("", 800, 600, False)

def renderer_init_window(str title="pymui", int width=800, int height=600, bint resizable=True):
    """Initialize SDL video and create the renderer window and GL context.

    Does nothing if the window is already open.

    Raises:
        RuntimeError: If the window or GL context cannot be created.
    """
    global _window_open
    if width <= 0 or height <= 0:
        raise ValueError("Window dimensions must be positive")
    if _window_open:
        return
    cdef bytes btitle = title.encode('utf-8')
    if SDL_InitSubSystem(SDL_INIT_VIDEO) != 0:
        raise RuntimeError(f"SDL_Init failed: {SDL_GetError().decode('utf-8', 'replace')}")
    if r_init_window(btitle, width, height, resizable) != 0:
        SDL_Quit()
        raise RuntimeError("Failed to create renderer window")
    _window_open = True

def renderer_resize(int width, int height):
    """Update the viewport after the window is resized."""
    r_resize(width, height)

def renderer_shutdown():
    """Destroy the renderer window and GL context, and shut down SDL."""
    global _window_open
    r_shutdown()
    if _window_open:
        SDL_Quit()  # also frees the cursors
    memset(_cursors, 0, sizeof(_cursors))
    _window_open = False


cdef enum:
    _EV_QUIT = 1
    _EV_MOUSEMOTION
    _EV_MOUSEDOWN
    _EV_MOUSEUP
    _EV_MOUSEWHEEL
    _EV_KEYDOWN
    _EV_KEYUP
    _EV_TEXT
    _EV_RESIZE
    _EV_DROPFILE
    _EV_FOCUS_GAINED
    _EV_FOCUS_LOST

class EventType:
    QUIT = _EV_QUIT
    MOUSEMOTION = _EV_MOUSEMOTION
    MOUSEDOWN = _EV_MOUSEDOWN
    MOUSEUP = _EV_MOUSEUP
    MOUSEWHEEL = _EV_MOUSEWHEEL
    KEYDOWN = _EV_KEYDOWN
    KEYUP = _EV_KEYUP
    TEXT = _EV_TEXT
    RESIZE = _EV_RESIZE
    DROPFILE = _EV_DROPFILE
    FOCUS_GAINED = _EV_FOCUS_GAINED
    FOCUS_LOST = _EV_FOCUS_LOST


class Mod:
    """Modifier bits of `Event.mod`. GUI is Cmd on macOS, the Windows key elsewhere."""
    SHIFT = KMOD_SHIFT
    CTRL = KMOD_CTRL
    ALT = KMOD_ALT
    GUI = KMOD_GUI


cdef class Event:
    """A window event, translated from SDL by `poll_event()`.

    `x, y` is the pointer position for mouse button and motion events, the
    scroll amount for MOUSEWHEEL (positive: right and away from the user),
    and the new window size for RESIZE.
    `button` is a `Mouse` value and `key` a `Key` value, 0 if unmapped.
    `keycode` is the SDL keycode, which equals the ASCII code for printable keys.
    `mod` holds the `Mod` bits of a key event; `clicks` is 2 for a double click.
    `text` is the typed text for TEXT and the file path for DROPFILE.
    """
    cdef readonly int type, x, y, button, key, keycode, clicks, mod
    cdef readonly str text

    def __init__(self, int type, int x=0, int y=0, int button=0, int key=0,
                 int keycode=0, str text="", int clicks=0, int mod=0):
        self.type = type
        self.x = x
        self.y = y
        self.button = button
        self.key = key
        self.keycode = keycode
        self.text = text
        self.clicks = clicks
        self.mod = mod

    def __repr__(self):
        return (f"Event(type={self.type}, x={self.x}, y={self.y}, button={self.button}, "
                f"key={self.key}, keycode={self.keycode}, text={self.text!r}, "
                f"clicks={self.clicks}, mod={self.mod})")


cdef int _map_button(Uint8 b):
    if b == SDL_BUTTON_LEFT: return MU_MOUSE_LEFT
    if b == SDL_BUTTON_RIGHT: return MU_MOUSE_RIGHT
    if b == SDL_BUTTON_MIDDLE: return MU_MOUSE_MIDDLE
    return 0


cdef int _map_key(SDL_Keycode k):
    if k == SDLK_LSHIFT or k == SDLK_RSHIFT: return MU_KEY_SHIFT
    if k == SDLK_LCTRL or k == SDLK_RCTRL: return MU_KEY_CTRL
    if k == SDLK_LALT or k == SDLK_RALT: return MU_KEY_ALT
    if k == SDLK_RETURN or k == SDLK_KP_ENTER: return MU_KEY_RETURN
    if k == SDLK_BACKSPACE: return MU_KEY_BACKSPACE
    if k == SDLK_ESCAPE: return MU_KEY_ESCAPE
    if k == SDLK_DELETE: return MU_KEY_DELETE
    if k == SDLK_LEFT: return MU_KEY_LEFT
    if k == SDLK_RIGHT: return MU_KEY_RIGHT
    if k == SDLK_UP: return MU_KEY_UP
    if k == SDLK_DOWN: return MU_KEY_DOWN
    if k == SDLK_HOME: return MU_KEY_HOME
    if k == SDLK_END: return MU_KEY_END
    if k == SDLK_TAB: return MU_KEY_TAB
    return 0


cdef Event _translate(SDL_Event* e):
    cdef Uint32 t = e.type
    cdef const char* s
    if t == SDL_QUIT:
        return Event(_EV_QUIT)
    if t == SDL_MOUSEMOTION:
        return Event(_EV_MOUSEMOTION, e.motion.x, e.motion.y)
    if t == SDL_MOUSEBUTTONDOWN or t == SDL_MOUSEBUTTONUP:
        return Event(_EV_MOUSEDOWN if t == SDL_MOUSEBUTTONDOWN else _EV_MOUSEUP,
                     e.button.x, e.button.y, _map_button(e.button.button),
                     clicks=e.button.clicks)
    if t == SDL_MOUSEWHEEL:
        if e.wheel.direction == SDL_MOUSEWHEEL_FLIPPED:
            return Event(_EV_MOUSEWHEEL, -e.wheel.x, -e.wheel.y)
        return Event(_EV_MOUSEWHEEL, e.wheel.x, e.wheel.y)
    if t == SDL_KEYDOWN or t == SDL_KEYUP:
        return Event(_EV_KEYDOWN if t == SDL_KEYDOWN else _EV_KEYUP,
                     key=_map_key(e.key.keysym.sym), keycode=e.key.keysym.sym,
                     mod=e.key.keysym.mod)
    if t == SDL_TEXTINPUT:
        s = e.text.text
        return Event(_EV_TEXT, text=s[:strlen(s)].decode('utf-8', 'replace'))
    if t == SDL_DROPFILE and e.drop.file != NULL:
        s = e.drop.file
        return Event(_EV_DROPFILE, text=s[:strlen(s)].decode('utf-8', 'replace'))
    if t == SDL_WINDOWEVENT:
        if e.window.event == SDL_WINDOWEVENT_SIZE_CHANGED:
            return Event(_EV_RESIZE, e.window.data1, e.window.data2)
        if e.window.event == SDL_WINDOWEVENT_FOCUS_GAINED:
            return Event(_EV_FOCUS_GAINED)
        if e.window.event == SDL_WINDOWEVENT_FOCUS_LOST:
            return Event(_EV_FOCUS_LOST)
    return None


cdef Event _translate_owned(SDL_Event* e):
    """_translate(), then free what SDL allocated for the event."""
    cdef Event ev = _translate(e)
    if e.type == SDL_DROPFILE and e.drop.file != NULL:
        SDL_free(e.drop.file)
    return ev


def poll_event():
    """Return the next pending window event, or None if the queue is empty.

    SDL events with no `EventType` are skipped.
    """
    cdef SDL_Event e
    cdef Event ev
    while SDL_PollEvent(&e):
        ev = _translate_owned(&e)
        if ev is not None:
            return ev
    return None


def wait_event(timeout=None):
    """Block until an event arrives or `timeout` seconds pass; return it or None.

    Raises:
        RuntimeError: If no renderer window exists.
    """
    cdef SDL_Event e
    cdef Event ev
    cdef int ms
    _require_window()
    deadline = None if timeout is None else time.monotonic() + max(timeout, 0)
    while True:
        if deadline is None:
            ms = -1
        else:
            ms = max(0, min(int((deadline - time.monotonic()) * 1000 + 0.5), 0x7FFFFFFF))
        if not SDL_WaitEventTimeout(&e, ms):
            return None
        ev = _translate_owned(&e)
        if ev is not None:
            return ev
        if deadline is not None and time.monotonic() >= deadline:
            return None


def _translate_sdl_event(str kind, int a=0, int b=0, int c=0, bytes text=b"", int d=0):
    """Build a raw SDL event and translate it as `poll_event()` does.

    Public as `pymui.testing.sdl_event`, which documents the arguments.
    Bypasses the SDL queue: sdl2-compat 2.32 crashes in SDL_PushEvent on text events.
    """
    cdef SDL_Event e
    memset(&e, 0, sizeof(e))
    if kind == "quit":
        e.type = SDL_QUIT
    elif kind == "motion":
        e.type = SDL_MOUSEMOTION
        e.motion.x, e.motion.y = a, b
    elif kind == "down" or kind == "up":
        e.type = SDL_MOUSEBUTTONDOWN if kind == "down" else SDL_MOUSEBUTTONUP
        e.button.button, e.button.x, e.button.y, e.button.clicks = a, b, c, d
    elif kind == "wheel":
        e.type = SDL_MOUSEWHEEL
        e.wheel.y, e.wheel.x, e.wheel.direction = a, b, c
    elif kind == "keydown" or kind == "keyup":
        e.type = SDL_KEYDOWN if kind == "keydown" else SDL_KEYUP
        e.key.keysym.sym, e.key.keysym.mod = a, b
    elif kind == "drop":
        e.type = SDL_DROPFILE
        e.drop.file = <char*>text  # borrowed from `text`; _translate does not free it
    elif kind == "text":
        e.type = SDL_TEXTINPUT
        memcpy(e.text.text, <const char*>text, min(len(text), sizeof(e.text.text) - 1))
    elif kind == "window":
        e.type = SDL_WINDOWEVENT
        e.window.event, e.window.data1, e.window.data2 = a, b, c
    else:
        raise ValueError(kind)
    return _translate(&e)


def render(Context ctx, Color bg=None):
    """Clear to `bg` (if given), draw `ctx`'s command list, and present.

    Iterates commands in C, so no per-command Python objects are created.

    Raises:
        RuntimeError: If no renderer window exists.
    """
    _require_window()
    if ctx._in_frame:
        raise RuntimeError("render() must follow end()")
    cdef mu_Command* cmd = NULL
    if bg is not None:
        r_clear(bg.to_c())
    while mu_next_command(ctx.ptr, &cmd):
        if cmd.type == MU_COMMAND_TEXT:
            r_draw_text(cmd.text.str, cmd.text.pos, cmd.text.color)
        elif cmd.type == MU_COMMAND_RECT:
            r_draw_rect(cmd.rect.rect, cmd.rect.color)
        elif cmd.type == MU_COMMAND_ICON:
            r_draw_icon(cmd.icon.id, cmd.icon.rect, cmd.icon.color)
        elif cmd.type == MU_COMMAND_IMAGE:
            r_draw_image(cmd.image.id, cmd.image.rect, cmd.image.color)
        elif cmd.type == MU_COMMAND_CLIP:
            r_set_clip_rect(cmd.clip.rect)
    r_present()

def renderer_draw_rect(Rect rect, Color color):
    """Queue a filled rectangle."""
    _require_window()
    r_draw_rect(rect.to_c(), color.to_c())

def renderer_draw_text(str text, Vec2 pos, Color color):
    """Queue text with the current font."""
    _require_window()
    r_draw_text(text.encode('utf-8'), pos.to_c(), color.to_c())

def renderer_draw_icon(int icon_id, Rect rect, Color color):
    """Queue `Icon` `icon_id` centered in `rect`."""
    if not 0 < icon_id < MU_ICON_MAX:
        raise ValueError("Icon id out of range")
    _require_window()
    r_draw_icon(icon_id, rect.to_c(), color.to_c())

def renderer_get_text_width(str text, int length=-1) -> int:
    """Width in pixels of `text`, or of its first `length` UTF-8 bytes."""
    return r_get_text_width(text.encode('utf-8'), length)

def renderer_get_text_height() -> int:
    """Line height in pixels of the current font."""
    return r_get_text_height()

def renderer_set_clip_rect(Rect rect):
    _require_window()
    r_set_clip_rect(rect.to_c())

def renderer_clear(Color color):
    _require_window()
    r_clear(color.to_c())

def renderer_present():
    _require_window()
    r_present()

def load_font(source, float size=16.0):
    """Render and measure all text with a TrueType/OpenType font.

    Applies to every Context and works without a window. The bundled
    bitmap font covers ASCII only; a loaded font covers whatever its file
    does, and draws its own missing-glyph box for the rest.

    Only load trusted files. stb_truetype checks the table directory but
    not the tables, so a crafted file can make it read out of bounds.

    Args:
        source: Path (str or os.PathLike), or the font file's bytes.
        size: Pixel height, 6 to 96.

    Raises:
        ValueError: If the data is not a usable font or size is out of range.
        OSError: If the file cannot be read.
    """
    if not 6 <= size <= 96:
        raise ValueError("font size must be 6..96 pixels")
    if isinstance(source, (bytes, bytearray, memoryview)):
        data = bytes(source)
    else:
        with open(os.fspath(source), "rb") as f:
            data = f.read(_MAX_FONT_BYTES + 1)
    if len(data) > _MAX_FONT_BYTES:
        raise ValueError("font file too large (max 64 MB)")
    cdef const unsigned char* buf = data
    if r_load_font(buf, len(data), size) != 0:
        raise ValueError("not a usable TrueType/OpenType font")

def reset_font():
    """Return to the bundled ASCII bitmap font."""
    r_unload_font()

def font_loaded() -> bool:
    """True if load_font() is in effect."""
    return bool(r_font_loaded())
