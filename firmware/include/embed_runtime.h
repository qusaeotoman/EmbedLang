#ifndef EMBED_RUNTIME_H
#define EMBED_RUNTIME_H
#include <stdint.h>

/* Opaque board handles, not STM32 pin masks or memory addresses. */
extern const uint32_t embed_const_LED_GREEN, embed_const_LED_YELLOW;
extern const uint32_t embed_const_LED_RED, embed_const_BUTTON_1;
extern const uint32_t embed_const_INPUT, embed_const_OUTPUT;
extern const uint32_t embed_const_HIGH, embed_const_LOW;
void embed_gpio_mode(uint32_t pin, uint32_t mode);
void embed_gpio_write(uint32_t pin, uint32_t value);
uint32_t embed_gpio_read(uint32_t pin);
void embed_gpio_toggle(uint32_t pin);
void embed_delay_ms(uint32_t ms);
uint32_t embed_millis(void);
#endif
