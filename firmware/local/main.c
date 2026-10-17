/* Local Flash wrapper. Clock parameters follow the pinned SDK_EXTI example.
 * No cLAB loader/recovery; no handwritten LED loop; no IWDG is started.
 */
#include "stm32f4xx_hal.h"
#include "trace.h"

extern void embed_program_main(void);
volatile uint32_t local_blink_status;
volatile uint32_t local_hal_error;

__attribute__((noreturn)) static void fail(uint32_t stage, HAL_StatusTypeDef status)
{
    local_hal_error = (uint32_t)status;
    local_blink_status = 0x80000000U | stage;
    __disable_irq();
    for (;;) __WFI();
}

void Error_Handler(void) { fail(4, HAL_ERROR); }

static void local_clock_init(void)
{
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};
    __HAL_RCC_PWR_CLK_ENABLE();
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);
    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    osc.HSEState = RCC_HSE_ON;
    osc.PLL.PLLState = RCC_PLL_ON;
    osc.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    osc.PLL.PLLM = 25;
    osc.PLL.PLLN = 336;
    osc.PLL.PLLP = RCC_PLLP_DIV2;
    osc.PLL.PLLQ = 4;
    HAL_StatusTypeDef status = HAL_RCC_OscConfig(&osc);
    if (status != HAL_OK) fail(2, status);
    clk.ClockType = RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_HCLK
                  | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider = RCC_SYSCLK_DIV1;
    clk.APB1CLKDivider = RCC_HCLK_DIV4;
    clk.APB2CLKDivider = RCC_HCLK_DIV2;
    status = HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_5);
    if (status != HAL_OK) fail(3, status);
    if (SystemCoreClock != 168000000U || SysTick->LOAD != 167999U
        || (SysTick->CTRL & (SysTick_CTRL_ENABLE_Msk | SysTick_CTRL_TICKINT_Msk | SysTick_CTRL_CLKSOURCE_Msk)) != 7U
        || __get_PRIMASK() != 0) fail(3, HAL_ERROR);
}

/* Symbols make completion/failure observable without semihosting or reset. */
__attribute__((noinline, noreturn)) void local_blink_finished(void)
{
    for (;;) __WFI();
}

int main(void)
{
    HAL_StatusTypeDef status = HAL_Init();
    if (status != HAL_OK) fail(1, status);
    local_clock_init();
    /* Retain runtime LED timestamps in on-board CCM for later inspection.
       There is no remote loader; this is application-owned local memory. */
    ((volatile traceinfo_t *)TRACEINFO_ADDR)->task_id = 0;
    MX_TRACE_Init();
    SDK_TRACE_Start();
    local_blink_status = 1;
    embed_program_main();
    DisableCC();
    local_blink_status = 2;
    /* Do not call SDK_TRACE_Stop: its reset would repeat the finite Blink. */
    local_blink_finished();
}
