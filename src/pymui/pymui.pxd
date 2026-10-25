

cdef extern from "microui.h":
    # Version and constants
    cdef const char* MU_VERSION

    # Size constants
    cdef const int MU_COMMANDLIST_SIZE      = (256 * 1024)
    cdef const int MU_ROOTLIST_SIZE         = 32
    cdef const int MU_CONTAINERSTACK_SIZE   = 32
    cdef const int MU_CLIPSTACK_SIZE        = 32
    cdef const int MU_IDSTACK_SIZE          = 32
    cdef const int MU_LAYOUTSTACK_SIZE      = 16
    cdef const int MU_CONTAINERPOOL_SIZE    = 48
    cdef const int MU_TREENODEPOOL_SIZE     = 48
    cdef const int MU_MAX_WIDTHS            = 16
    cdef const int MU_MAX_FMT               = 127
    cdef const char* MU_REAL_FMT            = "%.3g"
    cdef const char* MU_SLIDER_FMT          = "%.2f"

    # Type definitions
    ctypedef float MU_REAL

    # Enums
    cdef enum:
        MU_TEXTOP_COPY
        MU_TEXTOP_CUT
        MU_TEXTOP_SELECTALL

    cdef enum:
        MU_CLIP_PART = 1
        MU_CLIP_ALL

    cdef enum:
        MU_COMMAND_JUMP = 1
        MU_COMMAND_CLIP
        MU_COMMAND_RECT
        MU_COMMAND_TEXT
        MU_COMMAND_ICON
        MU_COMMAND_IMAGE
        MU_COMMAND_MAX

    cdef enum:
        MU_COLOR_TEXT
        MU_COLOR_BORDER
        MU_COLOR_WINDOWBG
        MU_COLOR_TITLEBG
        MU_COLOR_TITLETEXT
        MU_COLOR_PANELBG
        MU_COLOR_BUTTON
        MU_COLOR_BUTTONHOVER
        MU_COLOR_BUTTONFOCUS
        MU_COLOR_BASE
        MU_COLOR_BASEHOVER
        MU_COLOR_BASEFOCUS
        MU_COLOR_SCROLLBASE
        MU_COLOR_SCROLLTHUMB
        MU_COLOR_MAX

    cdef enum:
        MU_ICON_CLOSE = 1
        MU_ICON_CHECK
        MU_ICON_COLLAPSED
        MU_ICON_EXPANDED
        MU_ICON_MAX

    cdef enum:
        MU_RES_ACTIVE       = (1 << 0)
        MU_RES_SUBMIT       = (1 << 1)
        MU_RES_CHANGE       = (1 << 2)

    cdef enum:
        MU_OPT_ALIGNCENTER  = (1 << 0)
        MU_OPT_ALIGNRIGHT   = (1 << 1)
        MU_OPT_NOINTERACT   = (1 << 2)
        MU_OPT_NOFRAME      = (1 << 3)
        MU_OPT_NORESIZE     = (1 << 4)
        MU_OPT_NOSCROLL     = (1 << 5)
        MU_OPT_NOCLOSE      = (1 << 6)
        MU_OPT_NOTITLE      = (1 << 7)
        MU_OPT_HOLDFOCUS    = (1 << 8)
        MU_OPT_AUTOSIZE     = (1 << 9)
        MU_OPT_POPUP        = (1 << 10)
        MU_OPT_CLOSED       = (1 << 11)
        MU_OPT_EXPANDED     = (1 << 12)

    cdef enum:
        MU_MOUSE_LEFT       = (1 << 0)
        MU_MOUSE_RIGHT      = (1 << 1)
        MU_MOUSE_MIDDLE     = (1 << 2)

    cdef enum:
        MU_KEY_SHIFT        = (1 << 0)
        MU_KEY_CTRL         = (1 << 1)
        MU_KEY_ALT          = (1 << 2)
        MU_KEY_BACKSPACE    = (1 << 3)
        MU_KEY_RETURN       = (1 << 4)
        MU_KEY_ESCAPE       = (1 << 5)
        MU_KEY_DELETE       = (1 << 6)
        MU_KEY_LEFT         = (1 << 7)
        MU_KEY_RIGHT        = (1 << 8)
        MU_KEY_UP           = (1 << 9)
        MU_KEY_DOWN         = (1 << 10)
        MU_KEY_HOME         = (1 << 11)
        MU_KEY_END          = (1 << 12)
        MU_KEY_TAB          = (1 << 13)

    # Forward declarations
    ctypedef struct mu_Context
    ctypedef unsigned mu_Id
    ctypedef MU_REAL mu_Real
    ctypedef void* mu_Font

    # Basic structs
    ctypedef struct mu_Vec2:
        int x
        int y

    ctypedef struct mu_Rect:
        int x
        int y
        int w
        int h

    ctypedef struct mu_Color:
        unsigned char r
        unsigned char g
        unsigned char b
        unsigned char a

    ctypedef struct mu_PoolItem:
        mu_Id id
        int last_update

    # Command structs
    ctypedef struct mu_BaseCommand:
        int type
        int size

    ctypedef struct mu_JumpCommand:
        mu_BaseCommand base
        void* dst

    ctypedef struct mu_ClipCommand:
        mu_BaseCommand base
        mu_Rect rect

    ctypedef struct mu_RectCommand:
        mu_BaseCommand base
        mu_Rect rect
        mu_Color color

    ctypedef struct mu_TextCommand:
        mu_BaseCommand base
        mu_Font font
        mu_Vec2 pos
        mu_Color color
        char str[1]

    ctypedef struct mu_IconCommand:
        mu_BaseCommand base
        mu_Rect rect
        int id
        mu_Color color

    ctypedef struct mu_ImageCommand:
        mu_BaseCommand base
        mu_Rect rect
        int id
        mu_Color color

    # Command union
    ctypedef union mu_Command:
        int type
        mu_BaseCommand base
        mu_JumpCommand jump
        mu_ClipCommand clip
        mu_RectCommand rect
        mu_TextCommand text
        mu_IconCommand icon
        mu_ImageCommand image

    # Layout struct
    ctypedef struct mu_Layout:
        mu_Rect body
        mu_Rect next
        mu_Vec2 position
        mu_Vec2 size
        mu_Vec2 max
        int widths[MU_MAX_WIDTHS]
        int items
        int item_index
        int next_row
        int next_type
        int indent

    # Container struct
    ctypedef struct mu_Container:
        mu_Command* head
        mu_Command* tail
        mu_Rect rect
        mu_Rect body
        mu_Vec2 content_size
        mu_Vec2 scroll
        int zindex
        int open

    # Style struct
    ctypedef struct mu_Style:
        mu_Font font
        mu_Vec2 size
        int padding
        int spacing
        int indent
        int title_height
        int scrollbar_size
        int thumb_size
        mu_Color colors[MU_COLOR_MAX]

    # Stack structs
    ctypedef struct command_list_stack:
        int idx
        char items[MU_COMMANDLIST_SIZE]

    ctypedef struct root_list_stack:
        int idx
        mu_Container* items[MU_ROOTLIST_SIZE]

    ctypedef struct container_list_stack:
        int idx
        mu_Container* items[MU_CONTAINERSTACK_SIZE]

    ctypedef struct clip_list_stack:
        int idx
        mu_Rect items[MU_CLIPSTACK_SIZE]

    ctypedef struct id_list_stack:
        int idx
        mu_Id items[MU_IDSTACK_SIZE]

    ctypedef struct layout_list_stack:
        int idx
        mu_Layout items[MU_LAYOUTSTACK_SIZE]


    # Main Context struct
    ctypedef struct mu_Context:
        # callbacks
        int (*text_width)(mu_Font font, const char* str, int len)
        int (*text_height)(mu_Font font)
        void (*draw_frame)(mu_Context* ctx, mu_Rect rect, int colorid)
        # core state
        mu_Style _style
        mu_Style* style
        mu_Id hover
        mu_Id focus
        mu_Id last_id
        mu_Rect last_rect
        int last_zindex
        int updated_focus
        int frame
        mu_Container* hover_root
        mu_Container* next_hover_root
        mu_Container* scroll_target
        char number_edit_buf[MU_MAX_FMT]
        mu_Id number_edit
        mu_Id caret_id
        int caret
        int anchor
        int text_op
        int clip_start
        int clip_end
        int selecting
        # stacks (using macro-generated structs)
        command_list_stack command_list;
        root_list_stack root_list;
        container_list_stack container_stack;
        clip_list_stack clip_stack;
        id_list_stack id_stack;
        layout_list_stack layout_stack;
        # retained state pools
        mu_PoolItem container_pool[MU_CONTAINERPOOL_SIZE]
        mu_Container containers[MU_CONTAINERPOOL_SIZE]
        mu_PoolItem treenode_pool[MU_TREENODEPOOL_SIZE]
        # input state
        mu_Vec2 mouse_pos
        mu_Vec2 last_mouse_pos
        mu_Vec2 mouse_delta
        mu_Vec2 scroll_delta
        int mouse_down
        int mouse_pressed
        int key_down
        int key_pressed
        char input_text[32]

    # Utility functions
    mu_Vec2 mu_vec2(int x, int y)
    mu_Rect mu_rect(int x, int y, int w, int h)
    mu_Color mu_color(int r, int g, int b, int a)

    # Core functions
    void mu_init(mu_Context* ctx)
    void mu_begin(mu_Context* ctx)
    void mu_end(mu_Context* ctx)
    void mu_set_focus(mu_Context* ctx, mu_Id id)
    mu_Id mu_get_id(mu_Context* ctx, const void* data, int size)
    void mu_push_id(mu_Context* ctx, const void* data, int size)
    void mu_pop_id(mu_Context* ctx)
    void mu_push_clip_rect(mu_Context* ctx, mu_Rect rect)
    void mu_pop_clip_rect(mu_Context* ctx)
    mu_Rect mu_get_clip_rect(mu_Context* ctx)
    int mu_check_clip(mu_Context* ctx, mu_Rect r)
    mu_Container* mu_get_current_container(mu_Context* ctx)
    mu_Container* mu_get_container(mu_Context* ctx, const char* name)
    void mu_bring_to_front(mu_Context* ctx, mu_Container* cnt)

    # Pool functions
    int mu_pool_init(mu_Context* ctx, mu_PoolItem* items, int len, mu_Id id)
    int mu_pool_get(mu_Context* ctx, mu_PoolItem* items, int len, mu_Id id)
    void mu_pool_update(mu_Context* ctx, mu_PoolItem* items, int idx)

    # Input functions
    void mu_input_mousemove(mu_Context* ctx, int x, int y)
    void mu_input_mousedown(mu_Context* ctx, int x, int y, int btn)
    void mu_input_mouseup(mu_Context* ctx, int x, int y, int btn)
    void mu_input_scroll(mu_Context* ctx, int x, int y)
    void mu_input_keydown(mu_Context* ctx, int key)
    void mu_input_keyup(mu_Context* ctx, int key)
    void mu_input_text(mu_Context* ctx, const char* text)

    # Drawing functions
    mu_Command* mu_push_command(mu_Context* ctx, int type, int size)
    int mu_next_command(mu_Context* ctx, mu_Command** cmd)
    void mu_set_clip(mu_Context* ctx, mu_Rect rect)
    void mu_draw_rect(mu_Context* ctx, mu_Rect rect, mu_Color color)
    void mu_draw_box(mu_Context* ctx, mu_Rect rect, mu_Color color)
    void mu_draw_text(mu_Context* ctx, mu_Font font, const char* str, int len, mu_Vec2 pos, mu_Color color)
    void mu_draw_icon(mu_Context* ctx, int id, mu_Rect rect, mu_Color color)
    void mu_draw_image(mu_Context* ctx, int id, mu_Rect rect, mu_Color color)

    # Layout functions
    void mu_layout_row(mu_Context* ctx, int items, const int* widths, int height)
    void mu_layout_width(mu_Context* ctx, int width)
    void mu_layout_height(mu_Context* ctx, int height)
    void mu_layout_begin_column(mu_Context* ctx)
    void mu_layout_end_column(mu_Context* ctx)
    void mu_layout_set_next(mu_Context* ctx, mu_Rect r, int relative)
    mu_Rect mu_layout_next(mu_Context* ctx)

    # Control functions
    void mu_draw_control_frame(mu_Context* ctx, mu_Id id, mu_Rect rect, int colorid, int opt)
    void mu_draw_control_text(mu_Context* ctx, const char* str, mu_Rect rect, int colorid, int opt)
    int mu_mouse_over(mu_Context* ctx, mu_Rect rect)
    void mu_update_control(mu_Context* ctx, mu_Id id, mu_Rect rect, int opt)

    # Macro functions
    int mu_button(mu_Context* ctx, const char* label)
    int mu_textbox(mu_Context* ctx, char* buf, int bufsz)
    int mu_slider(mu_Context* ctx, mu_Real* value, mu_Real lo, mu_Real hi)
    int mu_number(mu_Context* ctx, mu_Real* value, mu_Real step)
    int mu_header(mu_Context* ctx, const char* label)
    void mu_begin_treenode(mu_Context* ctx, const char* label)
    void mu_begin_window(mu_Context* ctx, const char* title, mu_Rect rect)
    void mu_begin_panel(mu_Context* ctx, const char* name)

    # Widget functions
    void mu_text(mu_Context* ctx, const char* text)
    void mu_label(mu_Context* ctx, const char* text)
    int mu_button_ex(mu_Context* ctx, const char* label, int icon, int opt)
    int mu_checkbox(mu_Context* ctx, const char* label, int* state)
    int mu_textbox_raw(mu_Context* ctx, char* buf, int bufsz, mu_Id id, mu_Rect r, int opt)
    int mu_textbox_ex(mu_Context* ctx, char* buf, int bufsz, int opt)
    int mu_slider_ex(mu_Context* ctx, mu_Real* value, mu_Real low, mu_Real high, mu_Real step, const char* fmt, int opt)
    int mu_number_ex(mu_Context* ctx, mu_Real* value, mu_Real step, const char* fmt, int opt)
    int mu_header_ex(mu_Context* ctx, const char* label, int opt)
    int mu_begin_treenode_ex(mu_Context* ctx, const char* label, int opt)
    void mu_end_treenode(mu_Context* ctx)
    int mu_begin_window_ex(mu_Context* ctx, const char* title, mu_Rect rect, int opt)
    void mu_end_window(mu_Context* ctx)
    void mu_open_popup(mu_Context* ctx, const char* name)
    int mu_begin_popup(mu_Context* ctx, const char* name)
    void mu_end_popup(mu_Context* ctx)
    void mu_begin_panel_ex(mu_Context* ctx, const char* name, int opt)
    void mu_end_panel(mu_Context* ctx)

cdef extern from "renderer.h":
    void r_init()
    int  r_init_window(const char *title, int w, int h, int resizable)
    void r_resize(int w, int h)
    void r_shutdown()
    int  r_load_font(const unsigned char *data, int size, float px)
    void r_unload_font()
    int  r_font_loaded()
    void r_draw_rect(mu_Rect rect, mu_Color color)
    void r_draw_text(const char *text, mu_Vec2 pos, mu_Color color)
    void r_draw_icon(int id, mu_Rect rect, mu_Color color)
    int  r_get_text_width(const char *text, int len)
    int  r_get_text_height()
    void r_set_clip_rect(mu_Rect rect)
    void r_clear(mu_Color color)
    void r_present()
    float r_get_scale()
    int  r_generation()
    unsigned r_image_create(const unsigned char *rgba, int w, int h)
    int  r_image_update(unsigned id, const unsigned char *rgba, int w, int h)
    void r_image_destroy(unsigned id)
    void r_draw_image(unsigned id, mu_Rect rect, mu_Color color)

cdef extern from "SDL2/SDL.h":
    ctypedef unsigned int Uint32
    ctypedef unsigned char Uint8
    ctypedef unsigned short Uint16
    ctypedef int Sint32
    ctypedef Sint32 SDL_Keycode

    ctypedef struct SDL_Keysym:
        SDL_Keycode sym
        Uint16 mod
    ctypedef struct SDL_KeyboardEvent:
        SDL_Keysym keysym
    ctypedef struct SDL_MouseMotionEvent:
        Sint32 x
        Sint32 y
    ctypedef struct SDL_MouseButtonEvent:
        Uint8 button
        Uint8 clicks
        Sint32 x
        Sint32 y
    ctypedef struct SDL_MouseWheelEvent:
        Sint32 x
        Sint32 y
        Uint32 direction
    ctypedef struct SDL_TextInputEvent:
        char text[32]
    ctypedef struct SDL_DropEvent:
        char* file
    ctypedef struct SDL_WindowEvent:
        Uint8 event
        Sint32 data1
        Sint32 data2
    ctypedef union SDL_Event:
        Uint32 type
        SDL_KeyboardEvent key
        SDL_MouseMotionEvent motion
        SDL_MouseButtonEvent button
        SDL_MouseWheelEvent wheel
        SDL_TextInputEvent text
        SDL_WindowEvent window
        SDL_DropEvent drop

    int SDL_InitSubSystem(Uint32 flags)
    void SDL_Quit()
    const char* SDL_GetError()
    int SDL_PollEvent(SDL_Event* event)
    int SDL_WaitEventTimeout(SDL_Event* event, int timeout)
    void SDL_free(void* mem)
    char* SDL_GetClipboardText()
    int SDL_SetClipboardText(const char* text)
    ctypedef struct SDL_Cursor
    ctypedef int SDL_SystemCursor
    SDL_Cursor* SDL_CreateSystemCursor(SDL_SystemCursor id)
    void SDL_SetCursor(SDL_Cursor* cursor)
    Uint32 SDL_WasInit(Uint32 flags)
    cdef const SDL_SystemCursor SDL_SYSTEM_CURSOR_ARROW
    cdef const SDL_SystemCursor SDL_SYSTEM_CURSOR_IBEAM
    cdef const SDL_SystemCursor SDL_SYSTEM_CURSOR_WAIT
    cdef const SDL_SystemCursor SDL_SYSTEM_CURSOR_CROSSHAIR
    cdef const SDL_SystemCursor SDL_SYSTEM_CURSOR_SIZENWSE
    cdef const SDL_SystemCursor SDL_SYSTEM_CURSOR_SIZENESW
    cdef const SDL_SystemCursor SDL_SYSTEM_CURSOR_SIZEWE
    cdef const SDL_SystemCursor SDL_SYSTEM_CURSOR_SIZENS
    cdef const SDL_SystemCursor SDL_SYSTEM_CURSOR_SIZEALL
    cdef const SDL_SystemCursor SDL_SYSTEM_CURSOR_NO
    cdef const SDL_SystemCursor SDL_SYSTEM_CURSOR_HAND
    cdef const SDL_SystemCursor SDL_NUM_SYSTEM_CURSORS
    cdef const Uint32 SDL_MOUSEWHEEL_FLIPPED
    cdef const Uint32 SDL_DROPFILE
    cdef const Uint16 KMOD_CTRL
    cdef const Uint16 KMOD_ALT
    cdef const Uint16 KMOD_GUI
    cdef const Uint16 KMOD_SHIFT
    cdef const Uint8 SDL_WINDOWEVENT_FOCUS_GAINED
    cdef const Uint8 SDL_WINDOWEVENT_FOCUS_LOST

    cdef const Uint32 SDL_INIT_VIDEO

    cdef const Uint8 SDL_BUTTON_LEFT
    cdef const Uint8 SDL_BUTTON_RIGHT
    cdef const Uint8 SDL_BUTTON_MIDDLE

    cdef const SDL_Keycode SDLK_LSHIFT
    cdef const SDL_Keycode SDLK_RSHIFT
    cdef const SDL_Keycode SDLK_LCTRL
    cdef const SDL_Keycode SDLK_RCTRL
    cdef const SDL_Keycode SDLK_LALT
    cdef const SDL_Keycode SDLK_RALT
    cdef const SDL_Keycode SDLK_RETURN
    cdef const SDL_Keycode SDLK_KP_ENTER
    cdef const SDL_Keycode SDLK_BACKSPACE
    cdef const SDL_Keycode SDLK_ESCAPE
    cdef const SDL_Keycode SDLK_DELETE
    cdef const SDL_Keycode SDLK_LEFT
    cdef const SDL_Keycode SDLK_RIGHT
    cdef const SDL_Keycode SDLK_UP
    cdef const SDL_Keycode SDLK_DOWN
    cdef const SDL_Keycode SDLK_HOME
    cdef const SDL_Keycode SDLK_END
    cdef const SDL_Keycode SDLK_TAB

    cdef const Uint32 SDL_QUIT
    cdef const Uint32 SDL_MOUSEMOTION
    cdef const Uint32 SDL_MOUSEWHEEL
    cdef const Uint32 SDL_TEXTINPUT
    cdef const Uint32 SDL_MOUSEBUTTONDOWN
    cdef const Uint32 SDL_MOUSEBUTTONUP
    cdef const Uint32 SDL_KEYDOWN
    cdef const Uint32 SDL_KEYUP
    cdef const Uint32 SDL_WINDOWEVENT
    cdef const Uint8 SDL_WINDOWEVENT_SIZE_CHANGED
