#ifndef EMBED_OLED_H
#define EMBED_OLED_H
#include <stdint.h>

/* Existing scalar ABI: bool results are normalized uint32_t, no pointers exposed. */
uint32_t embed_oled_init(void);
void embed_oled_clear(void);
uint32_t embed_oled_cursor(uint32_t x, uint32_t y);
uint32_t embed_oled_write_char(uint32_t ascii);
uint32_t embed_oled_update(void);
extern volatile uint32_t embed_oled_status, embed_oled_hal_status, embed_oled_hal_error;
#endif
