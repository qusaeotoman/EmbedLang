/* Local-only adapter for the pinned SDK_OLED driver. No application text here. */
#include "embed_oled.h"
#include "oled.h"

I2C_HandleTypeDef hi2c1;
volatile uint32_t embed_oled_status, embed_oled_hal_status, embed_oled_hal_error;
static uint32_t ready;

static void record_error(uint32_t stage, HAL_StatusTypeDef status)
{
    if (status != HAL_OK && !(embed_oled_status & 0x80000000U)) {
        embed_oled_status = 0x80000000U | stage;
        embed_oled_hal_status = status;
        embed_oled_hal_error = hi2c1.ErrorCode;
        ready = 0;
    }
}

/* Only the original oled.c is compiled with HAL_I2C_Mem_Write redirected here.
 * Preserve its command sequence, but stop traffic after the first HAL failure.
 */
HAL_StatusTypeDef embed_oled_mem_write(I2C_HandleTypeDef *handle, uint16_t address,
    uint16_t memory, uint16_t memory_size, uint8_t *data, uint16_t size, uint32_t timeout)
{
    if (embed_oled_status & 0x80000000U) return (HAL_StatusTypeDef)embed_oled_hal_status;
    HAL_StatusTypeDef status = HAL_I2C_Mem_Write(handle, address, memory, memory_size, data, size, timeout);
    record_error(2, status);
    return status;
}

void HAL_I2C_MspInit(I2C_HandleTypeDef *handle)
{
    if (handle->Instance != I2C1) return;
    /* SDK_OLED/i2c.c executable configuration and .ioc: PB8 SCL, PB9 SDA.
     * Its PB6/PB7 comments are stale. F427 supports the same AF4 mapping.
     */
    __HAL_RCC_GPIOB_CLK_ENABLE();
    GPIO_InitTypeDef config = {0};
    config.Pin = GPIO_PIN_8 | GPIO_PIN_9;
    config.Mode = GPIO_MODE_AF_OD;
    config.Pull = GPIO_PULLUP;
    config.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
    config.Alternate = GPIO_AF4_I2C1;
    HAL_GPIO_Init(GPIOB, &config);
    __HAL_RCC_I2C1_CLK_ENABLE();
}

uint32_t embed_oled_init(void)
{
    ready = 0;
    embed_oled_status = embed_oled_hal_status = embed_oled_hal_error = 0;
    hi2c1.Instance = I2C1;
    hi2c1.Init.ClockSpeed = 400000;
    hi2c1.Init.DutyCycle = I2C_DUTYCYCLE_2;
    hi2c1.Init.OwnAddress1 = 0;
    hi2c1.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
    hi2c1.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
    hi2c1.Init.OwnAddress2 = 0;
    hi2c1.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
    hi2c1.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE;
    HAL_StatusTypeDef status = HAL_I2C_Init(&hi2c1);
    record_error(1, status);
    if (status != HAL_OK) return 0;
    oled_Init(); /* Original driver: 100 ms startup delay, commands, blank frame. */
    if (embed_oled_status & 0x80000000U) return 0;
    ready = 1;
    embed_oled_status = 1;
    return 1;
}

void embed_oled_clear(void)
{
    if (ready) { oled_Fill(Black); oled_SetCursor(0, 0); }
}

uint32_t embed_oled_cursor(uint32_t x, uint32_t y)
{
    /* Match the original driver's strict boundary check; test before narrowing. */
    if (!ready || x >= OLED_WIDTH - 7U || y >= OLED_HEIGHT - 10U) return 0;
    oled_SetCursor((uint8_t)x, (uint8_t)y);
    return 1;
}

uint32_t embed_oled_write_char(uint32_t ascii)
{
    /* Avoid indexing before/after the font table. No control codes or wrapping. */
    if (!ready || ascii < 32 || ascii > 126) return 0;
    return oled_WriteChar((char)ascii, Font_7x10, White) == (char)ascii;
}

uint32_t embed_oled_update(void)
{
    if (!ready) return 0;
    oled_UpdateScreen();
    if (!ready) return 0;
    embed_oled_status = 2;
    return 1;
}
