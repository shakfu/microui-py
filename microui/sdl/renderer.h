#ifndef RENDERER_H
#define RENDERER_H

#include "microui.h"

void r_init(void);
 int r_init_window(const char *title, int w, int h, int resizable);
void r_resize(int w, int h);
void r_shutdown(void);
 int r_load_font(const unsigned char *data, int size, float px);
void r_unload_font(void);
 int r_font_loaded(void);
void r_draw_rect(mu_Rect rect, mu_Color color);
void r_draw_text(const char *text, mu_Vec2 pos, mu_Color color);
void r_draw_icon(int id, mu_Rect rect, mu_Color color);
 int r_get_text_width(const char *text, int len);
 int r_get_text_height(void);
void r_set_clip_rect(mu_Rect rect);
void r_clear(mu_Color color);
void r_present(void);
float r_get_scale(void);
 int r_generation(void);
unsigned r_image_create(const unsigned char *rgba, int w, int h);
 int r_image_update(unsigned id, const unsigned char *rgba, int w, int h);
void r_image_destroy(unsigned id);
void r_draw_image(unsigned id, mu_Rect rect, mu_Color color);

#endif

