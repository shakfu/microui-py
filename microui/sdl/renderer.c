#include <SDL2/SDL.h>
#include <SDL2/SDL_opengl.h>
#include "renderer.h"
#include "atlas.inl"

#define STB_TRUETYPE_IMPLEMENTATION
#define STBTT_STATIC
#if defined(__GNUC__)
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-function"
#endif
#include "stb_truetype.h"
#if defined(__GNUC__)
#pragma GCC diagnostic pop
#endif

#define BUFFER_SIZE 16384

/* One alpha texture: the built-in atlas (icons, ASCII font) in the top-left
** 128x128, glyphs of a loaded font packed in rows below it. */
#define TEX_W 512
#define TEX_H 512
#define GLYPH_SLOTS 2048            /* hash table size, power of two */
#define BOX_GLYPH 127               /* built-in "missing glyph" box */
#define BUILTIN_LINE_HEIGHT 18

typedef struct {
  unsigned cp;                      /* 0: empty slot */
  short x, y, w, h;                 /* texture rect */
  short xoff, yoff;                 /* bitmap offset from pen and baseline */
} Glyph;

static unsigned char tex_pixels[TEX_W * TEX_H];
static int tex_ready;               /* tex_pixels holds the built-in atlas */
static int tex_dirty;               /* tex_pixels differs from the GL texture */
static GLuint tex_id;

static GLuint cur_tex;              /* texture the queued quads sample */

static unsigned char *font_data;    /* owned copy; stb_truetype keeps pointers */
static stbtt_fontinfo font;
static float font_scale;            /* font units to logical pixels */
static float font_ascent;           /* in font units */
static int font_baseline;           /* ascent in device pixels */
static int font_line_height;        /* logical pixels */

static Glyph glyphs[GLYPH_SLOTS];
static int glyph_count;
static int pack_x, pack_y, pack_row_h;

static GLfloat   tex_buf[BUFFER_SIZE *  8];
static GLfloat  vert_buf[BUFFER_SIZE *  8];
static GLubyte color_buf[BUFFER_SIZE * 16];
static GLuint  index_buf[BUFFER_SIZE *  6];

/* Logical window size. On HiDPI displays the drawable has `dpi` device
** pixels per logical pixel; layout and input stay in logical pixels. */
static int width  = 800;
static int height = 600;
static int fb_w   = 800;
static int fb_h   = 600;
static float dpi  = 1;
static int generation;              /* bumped per window; image ids die with it */
static int buf_idx;

static SDL_Window *window;
static SDL_GLContext gl_context;

static void flush(void);


static void tex_prepare(void) {
  int y;
  if (tex_ready) { return; }
  memset(tex_pixels, 0, sizeof(tex_pixels));
  for (y = 0; y < ATLAS_HEIGHT; y++) {
    memcpy(tex_pixels + y * TEX_W, atlas_texture + y * ATLAS_WIDTH, ATLAS_WIDTH);
  }
  tex_ready = 1;
  tex_dirty = 1;
}


/* Drop every cached glyph and clear their texture area. */
static void glyph_cache_reset(void) {
  flush();  /* queued quads still reference the old glyphs */
  tex_prepare();
  memset(tex_pixels + ATLAS_HEIGHT * TEX_W, 0, (TEX_H - ATLAS_HEIGHT) * TEX_W);
  memset(glyphs, 0, sizeof(glyphs));
  glyph_count = 0;
  pack_x = 0;
  pack_y = ATLAS_HEIGHT;
  pack_row_h = 0;
  tex_dirty = 1;
}


/* Decode one UTF-8 sequence from at most `avail` bytes (negative: until NUL).
** Returns the bytes consumed (>= 1, never past a NUL); malformed or
** overlong input yields U+FFFD. */
static int utf8_decode(const char *s, int avail, unsigned *cp) {
  const unsigned char *p = (const unsigned char *) s;
  unsigned c = p[0];
  int n, i;
  if (c < 0x80) { *cp = c; return 1; }
  if (c >= 0xC2 && c <= 0xDF) { n = 1; c &= 0x1F; }
  else if (c >= 0xE0 && c <= 0xEF) { n = 2; c &= 0x0F; }
  else if (c >= 0xF0 && c <= 0xF4) { n = 3; c &= 0x07; }
  else { *cp = 0xFFFD; return 1; }
  for (i = 1; i <= n; i++) {
    if ((avail >= 0 && i >= avail) || (p[i] & 0xC0) != 0x80) {
      *cp = 0xFFFD;
      return i;
    }
    c = (c << 6) | (p[i] & 0x3F);
  }
  if (c > 0x10FFFF || (c >= 0xD800 && c <= 0xDFFF) ||
      (n == 2 && c < 0x800) || (n == 3 && c < 0x10000)) {
    c = 0xFFFD;
  }
  *cp = c;
  return n + 1;
}


/* Return the cached glyph for `cp`, rasterizing it on first use. A font
** without `cp` yields its own missing-glyph (index 0). */
static const Glyph *glyph_get(unsigned cp) {
  unsigned h = (cp * 2654435761u) & (GLYPH_SLOTS - 1);
  int index, x0, y0, x1, y1, w, h2, attempt;
  Glyph *g;
  if (cp == 0) { cp = 0xFFFD; }
  for (;;) {
    g = &glyphs[h];
    if (g->cp == cp) { return g; }
    if (g->cp == 0) { break; }
    h = (h + 1) & (GLYPH_SLOTS - 1);
  }
  if (glyph_count >= GLYPH_SLOTS / 2) {
    glyph_cache_reset();
    return glyph_get(cp);
  }
  index = stbtt_FindGlyphIndex(&font, (int) cp);
  stbtt_GetGlyphBitmapBox(&font, index, font_scale * dpi, font_scale * dpi, &x0, &y0, &x1, &y1);
  w = x1 - x0;
  h2 = y1 - y0;
  if (w < 0 || h2 < 0 || w > TEX_W || h2 > TEX_H - ATLAS_HEIGHT) { w = h2 = 0; }
  for (attempt = 0; attempt < 2; attempt++) {
    if (pack_x + w > TEX_W) {
      pack_x = 0;
      pack_y += pack_row_h + 1;
      pack_row_h = 0;
    }
    if (pack_y + h2 <= TEX_H) { break; }
    glyph_cache_reset();  /* texture full: start over */
    g = &glyphs[(cp * 2654435761u) & (GLYPH_SLOTS - 1)];
  }
  if (w > 0 && h2 > 0) {
    stbtt_MakeGlyphBitmap(&font, tex_pixels + pack_y * TEX_W + pack_x,
                          w, h2, TEX_W, font_scale * dpi, font_scale * dpi, index);
    tex_dirty = 1;
  }
  g->cp = cp;
  g->x = pack_x; g->y = pack_y; g->w = w; g->h = h2;
  g->xoff = x0; g->yoff = y0;
  glyph_count++;
  pack_x += w + 1;
  if (h2 > pack_row_h) { pack_row_h = h2; }
  return g;
}


static float glyph_advance(unsigned cp) {
  int adv, lsb;
  stbtt_GetGlyphHMetrics(&font, stbtt_FindGlyphIndex(&font, (int) cp), &adv, &lsb);
  return adv * font_scale;
}


static unsigned be16(const unsigned char *p) { return (p[0] << 8) | p[1]; }
static unsigned long be32(const unsigned char *p) {
  return ((unsigned long) p[0] << 24) | ((unsigned long) p[1] << 16) | (p[2] << 8) | p[3];
}


/* stb_truetype takes no length and trusts table offsets. Reject files whose
** table directory points past the end, e.g. truncated downloads. This does
** not make malicious font files safe. */
static int font_tables_in_bounds(const unsigned char *data, int size) {
  int off = stbtt_GetFontOffsetForIndex(data, 0);
  unsigned i, n;
  if (off < 0 || (long) off + 12 > size) { return 0; }
  n = be16(data + off + 4);
  if ((long) off + 12 + 16L * n > size) { return 0; }
  for (i = 0; i < n; i++) {
    const unsigned char *rec = data + off + 12 + 16 * i;
    unsigned long t_off = be32(rec + 8), t_len = be32(rec + 12);
    if (t_off > (unsigned long) size || t_len > (unsigned long) size - t_off) { return 0; }
  }
  return 1;
}


int r_load_font(const unsigned char *data, int size, float px) {
  unsigned char *copy;
  stbtt_fontinfo info;
  int ascent, descent, gap;
  /* stbtt_GetFontOffsetForIndex reads up to 16 header bytes unchecked */
  if (!data || size < 16 || px < 6 || px > 96) { return -1; }
  if (!font_tables_in_bounds(data, size)) { return -1; }
  copy = malloc(size);
  if (!copy) { return -1; }
  memcpy(copy, data, size);
  if (!stbtt_InitFont(&info, copy, stbtt_GetFontOffsetForIndex(copy, 0))) {
    free(copy);
    return -1;
  }
  r_unload_font();
  font_data = copy;
  font = info;
  font_scale = stbtt_ScaleForPixelHeight(&font, px);
  stbtt_GetFontVMetrics(&font, &ascent, &descent, &gap);
  font_ascent = ascent;
  font_baseline = (int) (ascent * font_scale * dpi + 0.5f);
  font_line_height = (int) ((ascent - descent + gap) * font_scale + 0.5f);
  glyph_cache_reset();
  return 0;
}


void r_unload_font(void) {
  if (!font_data) { return; }
  glyph_cache_reset();
  free(font_data);
  font_data = NULL;
}


int r_font_loaded(void) {
  return font_data != NULL;
}


/* Re-read the drawable size; glyphs are re-rasterized when the scale changes. */
static void update_scale(void) {
  int win_w = width, win_h = height;
  float s;
  fb_w = width;
  fb_h = height;
  if (window) {
    SDL_GetWindowSize(window, &win_w, &win_h);
    SDL_GL_GetDrawableSize(window, &fb_w, &fb_h);
  }
  s = win_w > 0 && fb_w > 0 ? (float) fb_w / win_w : 1;
  if (s == dpi) { return; }
  dpi = s;
  if (font_data) {
    font_baseline = (int) (font_ascent * font_scale * dpi + 0.5f);
    glyph_cache_reset();
  }
}


void r_init(void) {
  r_init_window(NULL, width, height, 0);
}


int r_init_window(const char *title, int w, int h, int resizable) {
  if (window) { return 0; }
  width = w;
  height = h;
  /* init SDL window */
  window = SDL_CreateWindow(
    title, SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED,
    width, height, SDL_WINDOW_OPENGL | SDL_WINDOW_ALLOW_HIGHDPI |
    (resizable ? SDL_WINDOW_RESIZABLE : 0));
  if (!window) { return -1; }
  gl_context = SDL_GL_CreateContext(window);
  if (!gl_context) {
    SDL_DestroyWindow(window);
    window = NULL;
    return -1;
  }
  /* vsync caps the frame rate; failure is non-fatal */
  SDL_GL_SetSwapInterval(1);

  /* init gl */
  glEnable(GL_BLEND);
  glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
  glDisable(GL_CULL_FACE);
  glDisable(GL_DEPTH_TEST);
  glEnable(GL_SCISSOR_TEST);
  glEnable(GL_TEXTURE_2D);
  glEnableClientState(GL_VERTEX_ARRAY);
  glEnableClientState(GL_TEXTURE_COORD_ARRAY);
  glEnableClientState(GL_COLOR_ARRAY);

  /* init texture */
  tex_prepare();
  glGenTextures(1, &tex_id);
  glBindTexture(GL_TEXTURE_2D, tex_id);
  glTexImage2D(GL_TEXTURE_2D, 0, GL_ALPHA, TEX_W, TEX_H, 0,
    GL_ALPHA, GL_UNSIGNED_BYTE, tex_pixels);
  tex_dirty = 0;
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
  cur_tex = tex_id;
  if (glGetError() != GL_NO_ERROR) { r_shutdown(); return -1; }
  generation++;
  update_scale();
  return 0;
}


void r_resize(int w, int h) {
  flush();
  width = w;
  height = h;
  update_scale();
}


float r_get_scale(void) {
  return dpi;
}


int r_generation(void) {
  return window ? generation : 0;
}


void r_shutdown(void) {
  if (gl_context) { SDL_GL_DeleteContext(gl_context); gl_context = NULL; }
  if (window) { SDL_DestroyWindow(window); window = NULL; }
  buf_idx = 0;
  update_scale();
}


static void flush(void) {
  if (buf_idx == 0) { return; }
  if (!gl_context) { buf_idx = 0; return; }  /* nothing to draw into */
  if (tex_dirty) {
    glBindTexture(GL_TEXTURE_2D, tex_id);
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, TEX_W, TEX_H,
      GL_ALPHA, GL_UNSIGNED_BYTE, tex_pixels);
    tex_dirty = 0;
  }
  glBindTexture(GL_TEXTURE_2D, cur_tex);

  glViewport(0, 0, fb_w, fb_h);
  glMatrixMode(GL_PROJECTION);
  glPushMatrix();
  glLoadIdentity();
  glOrtho(0.0f, width, height, 0.0f, -1.0f, +1.0f);
  glMatrixMode(GL_MODELVIEW);
  glPushMatrix();
  glLoadIdentity();

  glTexCoordPointer(2, GL_FLOAT, 0, tex_buf);
  glVertexPointer(2, GL_FLOAT, 0, vert_buf);
  glColorPointer(4, GL_UNSIGNED_BYTE, 0, color_buf);
  glDrawElements(GL_TRIANGLES, buf_idx * 6, GL_UNSIGNED_INT, index_buf);

  glMatrixMode(GL_MODELVIEW);
  glPopMatrix();
  glMatrixMode(GL_PROJECTION);
  glPopMatrix();

  buf_idx = 0;
}


/* Queue a quad at logical (x, y, w, h) sampling texture coords u0..u1, v0..v1. */
static void push_quad_uv(float x, float y, float w, float h,
                         float u0, float v0, float u1, float v1, mu_Color color) {
  if (buf_idx == BUFFER_SIZE) { flush(); }

  int texvert_idx = buf_idx *  8;
  int   color_idx = buf_idx * 16;
  int element_idx = buf_idx *  4;
  int   index_idx = buf_idx *  6;
  buf_idx++;

  /* update texture buffer */
  tex_buf[texvert_idx + 0] = u0;
  tex_buf[texvert_idx + 1] = v0;
  tex_buf[texvert_idx + 2] = u1;
  tex_buf[texvert_idx + 3] = v0;
  tex_buf[texvert_idx + 4] = u0;
  tex_buf[texvert_idx + 5] = v1;
  tex_buf[texvert_idx + 6] = u1;
  tex_buf[texvert_idx + 7] = v1;

  /* update vertex buffer */
  vert_buf[texvert_idx + 0] = x;
  vert_buf[texvert_idx + 1] = y;
  vert_buf[texvert_idx + 2] = x + w;
  vert_buf[texvert_idx + 3] = y;
  vert_buf[texvert_idx + 4] = x;
  vert_buf[texvert_idx + 5] = y + h;
  vert_buf[texvert_idx + 6] = x + w;
  vert_buf[texvert_idx + 7] = y + h;

  /* update color buffer */
  memcpy(color_buf + color_idx +  0, &color, 4);
  memcpy(color_buf + color_idx +  4, &color, 4);
  memcpy(color_buf + color_idx +  8, &color, 4);
  memcpy(color_buf + color_idx + 12, &color, 4);

  /* update index buffer */
  index_buf[index_idx + 0] = element_idx + 0;
  index_buf[index_idx + 1] = element_idx + 1;
  index_buf[index_idx + 2] = element_idx + 2;
  index_buf[index_idx + 3] = element_idx + 2;
  index_buf[index_idx + 4] = element_idx + 3;
  index_buf[index_idx + 5] = element_idx + 1;
}


static void use_texture(GLuint id) {
  if (cur_tex != id) { flush(); cur_tex = id; }
}


/* Queue a quad sampling `src` of the atlas texture. */
static void push_quad(float x, float y, float w, float h, mu_Rect src, mu_Color color) {
  use_texture(tex_id);
  push_quad_uv(x, y, w, h,
               src.x / (float) TEX_W, src.y / (float) TEX_H,
               (src.x + src.w) / (float) TEX_W, (src.y + src.h) / (float) TEX_H, color);
}


void r_draw_rect(mu_Rect rect, mu_Color color) {
  push_quad(rect.x, rect.y, rect.w, rect.h, atlas[ATLAS_WHITE], color);
}


static mu_Rect builtin_glyph(unsigned cp) {
  return atlas[ATLAS_FONT + (cp < 128 ? (int) cp : BOX_GLYPH)];
}


void r_draw_text(const char *text, mu_Vec2 pos, mu_Color color) {
  const char *p = text;
  unsigned cp;
  float pen = pos.x;
  while (*p) {
    p += utf8_decode(p, -1, &cp);
    if (font_data) {
      const Glyph *g = glyph_get(cp);
      if (g->w > 0) {
        /* glyph bitmaps are in device pixels; snap them to the device grid */
        float x = (float) (int) (pen * dpi + 0.5f) + g->xoff;
        float y = (float) (int) (pos.y * dpi + 0.5f) + font_baseline + g->yoff;
        push_quad(x / dpi, y / dpi, g->w / dpi, g->h / dpi,
                  mu_rect(g->x, g->y, g->w, g->h), color);
      }
      pen += glyph_advance(cp);
    } else {
      mu_Rect src = builtin_glyph(cp);
      push_quad((int) pen, pos.y, src.w, src.h, src, color);
      pen += src.w;
    }
  }
}


void r_draw_icon(int id, mu_Rect rect, mu_Color color) {
  mu_Rect src = atlas[id];
  int x = rect.x + (rect.w - src.w) / 2;
  int y = rect.y + (rect.h - src.h) / 2;
  push_quad(x, y, src.w, src.h, src, color);
}


int r_get_text_width(const char *text, int len) {
  const char *p = text;
  unsigned cp;
  float res = 0;
  int n;
  while (len != 0 && *p) {
    n = utf8_decode(p, len, &cp);
    p += n;
    if (len > 0) { len -= n; }
    res += font_data ? glyph_advance(cp) : builtin_glyph(cp).w;
  }
  return (int) (res + 0.5f);
}


int r_get_text_height(void) {
  return font_data ? font_line_height : BUILTIN_LINE_HEIGHT;
}


void r_set_clip_rect(mu_Rect rect) {
  int x0 = (int) (rect.x * dpi + 0.5f), x1 = (int) ((rect.x + rect.w) * dpi + 0.5f);
  int y0 = (int) (rect.y * dpi + 0.5f), y1 = (int) ((rect.y + rect.h) * dpi + 0.5f);
  flush();
  glScissor(x0, fb_h - y1, x1 - x0, y1 - y0);
}


void r_clear(mu_Color clr) {
  flush();
  glClearColor(clr.r / 255., clr.g / 255., clr.b / 255., clr.a / 255.);
  glClear(GL_COLOR_BUFFER_BIT);
}


void r_present(void) {
  flush();
  SDL_GL_SwapWindow(window);
}


unsigned r_image_create(const unsigned char *rgba, int w, int h) {
  GLint max_size = 0;
  GLuint id = 0;
  if (!gl_context || !rgba || w <= 0 || h <= 0) { return 0; }
  glGetIntegerv(GL_MAX_TEXTURE_SIZE, &max_size);
  if (w > max_size || h > max_size) { return 0; }
  flush();
  while (glGetError() != GL_NO_ERROR) {}  /* drop stale errors */
  glGenTextures(1, &id);
  glBindTexture(GL_TEXTURE_2D, id);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
  glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, rgba);
  glBindTexture(GL_TEXTURE_2D, cur_tex);
  if (glGetError() != GL_NO_ERROR) {
    glDeleteTextures(1, &id);
    return 0;
  }
  return id;
}


int r_image_update(unsigned id, const unsigned char *rgba, int w, int h) {
  if (!gl_context || !id || !rgba) { return -1; }
  flush();
  glBindTexture(GL_TEXTURE_2D, id);
  glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, rgba);
  glBindTexture(GL_TEXTURE_2D, cur_tex);
  return glGetError() == GL_NO_ERROR ? 0 : -1;
}


void r_image_destroy(unsigned id) {
  GLuint tex = id;
  if (!gl_context || !id) { return; }
  flush();
  if (cur_tex == tex) { cur_tex = tex_id; }
  glDeleteTextures(1, &tex);
}


void r_draw_image(unsigned id, mu_Rect rect, mu_Color color) {
  if (!id) { return; }
  use_texture(id);
  push_quad_uv(rect.x, rect.y, rect.w, rect.h, 0, 0, 1, 1, color);
}
