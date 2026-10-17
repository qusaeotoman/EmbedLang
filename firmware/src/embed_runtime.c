#include "embed_runtime.h"
#include "stm32f4xx_hal.h"
#include "trace.h"

/* SDK_EXTI/Core/Inc/main.h: LED1/2/3 = PD13/14/15, BTN = PC15.
 * SDK_cLAB/Core/Inc/trace.h: LED1 green, LED2 yellow, LED3 red.
 * Handles and modes below are the EmbedLang board ABI, not physical pin numbers.
 */
const uint32_t embed_const_LED_GREEN = 1, embed_const_LED_YELLOW = 2;
const uint32_t embed_const_LED_RED = 3, embed_const_BUTTON_1 = 4;
const uint32_t embed_const_INPUT = 0, embed_const_OUTPUT = 1;
const uint32_t embed_const_HIGH = 1, embed_const_LOW = 0;

static uint16_t led_pin(uint32_t pin)
{
    switch (pin) {
    case 1: return GPIO_PIN_13;
    case 2: return GPIO_PIN_14;
    case 3: return GPIO_PIN_15;
    default: return 0;
    }
}

static void trace_led(uint32_t pin, uint16_t mask)
{
    const traceinfo_t *info = (const traceinfo_t *)TRACEINFO_ADDR;
    /* The official timestamp routine does not check its buffer capacity. */
    if (info->tracelog_size <= PRINTDATA_ADDR - TRACELOG_ADDR - sizeof(tracelog_t)) {
        uint8_t event = pin == 1 ? LED1 : pin == 2 ? LED2 : LED3;
        SDK_TRACE_Timestamp(event, HAL_GPIO_ReadPin(GPIOD, mask) == GPIO_PIN_SET);
    }
}

void embed_gpio_mode(uint32_t pin, uint32_t mode)
{
    GPIO_InitTypeDef config = {0};
    uint16_t mask = led_pin(pin);
    if (mode > 1) return;
    config.Pull = GPIO_NOPULL;
    config.Speed = GPIO_SPEED_FREQ_HIGH; /* official cLAB LED setup */
    if (mask) {
        __HAL_RCC_GPIOD_CLK_ENABLE();
        config.Pin = mask;
        config.Mode = mode ? GPIO_MODE_OUTPUT_PP : GPIO_MODE_INPUT;
        HAL_GPIO_Init(GPIOD, &config);
    } else if (pin == 4 && mode == 0) {
        /* Poll the standalone BTN. Do not install an EXTI interrupt. */
        __HAL_RCC_GPIOC_CLK_ENABLE();
        config.Pin = GPIO_PIN_15;
        config.Mode = GPIO_MODE_INPUT;
        HAL_GPIO_Init(GPIOC, &config);
    }
}

void embed_gpio_write(uint32_t pin, uint32_t value)
{
    uint16_t mask = led_pin(pin);
    if (!mask) return;
    HAL_GPIO_WritePin(GPIOD, mask, value ? GPIO_PIN_SET : GPIO_PIN_RESET);
    trace_led(pin, mask);
}

uint32_t embed_gpio_read(uint32_t pin)
{
    uint16_t mask = led_pin(pin);
    if (mask) return HAL_GPIO_ReadPin(GPIOD, mask) == GPIO_PIN_SET;
    if (pin == 4) return HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_15) == GPIO_PIN_SET;
    return 0;
}

void embed_gpio_toggle(uint32_t pin)
{
    uint16_t mask = led_pin(pin);
    if (!mask) return;
    HAL_GPIO_TogglePin(GPIOD, mask);
    trace_led(pin, mask);
}

void embed_delay_ms(uint32_t ms) { HAL_Delay(ms); }
uint32_t embed_millis(void) { return HAL_GetTick(); }
