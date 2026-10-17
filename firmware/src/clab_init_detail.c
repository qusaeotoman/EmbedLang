/* RAM-only initialization recorder. No trace API is called until report(). */
#include "clab_init_detail.h"
#include "clab_diagnostics.h"
#include <stdio.h>
#include <string.h>

#define RECORDS 4
static const char *source_basename(const char *file);
typedef struct {
    uint32_t cr, cfgr, pll, csr, flash, iwdg, reload, primask, hclk;
} snapshot_t;
typedef struct {
    const char *function, *file, *return_function, *return_file;
    uint32_t line, status, return_line, return_status, handlers, effective_status;
    snapshot_t before, after;
} init_record_t;
static init_record_t records[RECORDS];
static uint32_t record_count;
static uint32_t recorder_overflow;
static int active_record = -1;
#ifdef EMBED_PLL_RECOVERY
static uint32_t pll_recovery_candidate;
static RCC_OscInitTypeDef requested_osc;

static uint32_t board_request_matches(const RCC_OscInitTypeDef *c)
{
    return c->OscillatorType == (RCC_OSCILLATORTYPE_HSE | RCC_OSCILLATORTYPE_LSI)
        && c->HSEState == RCC_HSE_ON && c->LSIState == RCC_LSI_ON
        && c->PLL.PLLState == RCC_PLL_ON && c->PLL.PLLSource == RCC_PLLSOURCE_HSE
        && c->PLL.PLLM == 25 && c->PLL.PLLN == 336
        && c->PLL.PLLP == RCC_PLLP_DIV2 && c->PLL.PLLQ == 4;
}

static uint32_t active_pll_matches(const snapshot_t *s)
{
    const RCC_PLLInitTypeDef *p = &requested_osc.PLL;
    return (s->cr & (RCC_CR_PLLON | RCC_CR_PLLRDY | RCC_CR_HSEON | RCC_CR_HSERDY))
               == (RCC_CR_PLLON | RCC_CR_PLLRDY | RCC_CR_HSEON | RCC_CR_HSERDY)
        && (s->cr & RCC_CR_HSEBYP) == 0
        && (s->cfgr & RCC_CFGR_SWS) == RCC_CFGR_SWS_PLL
        && (s->cfgr & RCC_CFGR_SW) == RCC_SYSCLKSOURCE_PLLCLK
        && (s->pll & RCC_PLLCFGR_PLLSRC) == p->PLLSource
        && (s->pll & RCC_PLLCFGR_PLLM) == p->PLLM
        && ((s->pll & RCC_PLLCFGR_PLLN) >> RCC_PLLCFGR_PLLN_Pos) == p->PLLN
        && ((((s->pll & RCC_PLLCFGR_PLLP) >> RCC_PLLCFGR_PLLP_Pos) + 1U) * 2U) == p->PLLP
        && ((s->pll & RCC_PLLCFGR_PLLQ) >> RCC_PLLCFGR_PLLQ_Pos) == p->PLLQ;
}

static uint32_t oscillators_ready(const snapshot_t *s)
{
    return active_pll_matches(s)
        && (s->csr & (RCC_CSR_LSION | RCC_CSR_LSIRDY)) == (RCC_CSR_LSION | RCC_CSR_LSIRDY);
}
#endif

static snapshot_t snapshot(void)
{
    snapshot_t value;
    value.cr = RCC->CR;
    value.cfgr = RCC->CFGR;
    value.pll = RCC->PLLCFGR;
    value.csr = RCC->CSR;
    value.flash = FLASH->ACR;
    value.iwdg = IWDG->SR;
    /* CTRL is deliberately NOT read: reading it clears COUNTFLAG. */
    value.reload = SysTick->LOAD;
    value.primask = __get_PRIMASK();
    value.hclk = SystemCoreClock;
    return value;
}

static void begin(const char *function, const char *file, uint32_t line)
{
    if (record_count == RECORDS) { recorder_overflow = 1; active_record = -1; return; }
    active_record = (int)record_count++;
    init_record_t *record = &records[active_record];
    record->function = function;
    record->file = file;
    record->line = line;
    record->before = snapshot();
}

static HAL_StatusTypeDef end(HAL_StatusTypeDef status)
{
    if (active_record >= 0) {
        records[active_record].status = (uint32_t)status;
        records[active_record].effective_status = (uint32_t)status;
        records[active_record].after = snapshot();
    }
    active_record = -1;
    return status; /* preserve the original HAL status and caller behavior */
}

HAL_StatusTypeDef embed_init_hal(const char *file, uint32_t line)
{
    begin("HAL_Init", file, line);
    return end(HAL_Init());
}
HAL_StatusTypeDef embed_init_osc(RCC_OscInitTypeDef *config, const char *file, uint32_t line)
{
    begin("HAL_RCC_OscConfig", file, line);
#ifdef EMBED_PLL_RECOVERY
    int index = active_record;
    pll_recovery_candidate = 0;
    if (config) requested_osc = *config;
#endif
    HAL_StatusTypeDef status = end(HAL_RCC_OscConfig(config));
#ifdef EMBED_PLL_RECOVERY
    /* The immutable vendor manifest pins the exact buggy branch/line. Only its
       HAL_ERROR is eligible, never a timeout, busy status or another return. */
    if (index == 1 && config && board_request_matches(&requested_osc)) {
        init_record_t *r = &records[index];
        if (status == HAL_ERROR && r->return_status == HAL_ERROR && r->return_line == 549
            && r->return_function && !strcmp(r->return_function, "HAL_RCC_OscConfig")
            && r->return_file && !strcmp(source_basename(r->return_file), "stm32f4xx_hal_rcc.c")
            && active_pll_matches(&r->before) && oscillators_ready(&r->after)
            && r->before.pll == r->after.pll) {
            pll_recovery_candidate = 1;
            r->effective_status = HAL_OK;
            return HAL_OK; /* original raw status/provenance remain in the log */
        }
    }
#endif
    return status;
}
HAL_StatusTypeDef embed_init_clock(RCC_ClkInitTypeDef *config, uint32_t latency,
                                   const char *file, uint32_t line)
{
    begin("HAL_RCC_ClockConfig", file, line);
    return end(HAL_RCC_ClockConfig(config, latency));
}
HAL_StatusTypeDef embed_init_iwdg(IWDG_HandleTypeDef *handle, const char *file, uint32_t line)
{
    begin("HAL_IWDG_Init", file, line);
    return end(HAL_IWDG_Init(handle));
}

void embed_init_note_return(const char *function, const char *file, uint32_t line,
                            HAL_StatusTypeDef status)
{
    if (active_record < 0) return;
    init_record_t *record = &records[active_record];
    if (record->return_line) return; /* preserve the first nested failure */
    record->return_function = function;
    record->return_file = file;
    record->return_line = line;
    record->return_status = (uint32_t)status;
}

void embed_init_note_handler(void)
{
    /* The three original handler calls immediately follow a HAL call. */
    if (record_count) records[record_count - 1].handlers++;
}

static const char *source_basename(const char *file)
{
    const char *name = file;
    for (const char *p = file; *p; p++)
        if (*p == '/' || *p == '\\') name = p + 1;
    return name;
}

#ifdef EMBED_PLL_RECOVERY
uint32_t embed_init_pll_recovered(void) { return pll_recovery_candidate; }

uint32_t embed_init_application_allowed(void)
{
    static const char *names[RECORDS] = {
        "HAL_Init", "HAL_RCC_OscConfig", "HAL_RCC_ClockConfig", "HAL_IWDG_Init"
    };
    if (record_count != RECORDS || recorder_overflow || !board_request_matches(&requested_osc)) return 0;
    for (uint32_t i = 0; i < RECORDS; i++) {
        const init_record_t *r = &records[i];
        if (strcmp(r->function, names[i]) || r->handlers || r->effective_status != HAL_OK) return 0;
        /* HAL_Init/ClockConfig ignore HAL_InitTick's status: reject a captured
           nested failure even if the top-level return misleadingly says OK. */
        if ((r->status != HAL_OK || r->return_line) && !(i == 1 && pll_recovery_candidate)) return 0;
    }
    snapshot_t now = snapshot();
    return oscillators_ready(&now)
        && (now.cfgr & (RCC_CFGR_HPRE | RCC_CFGR_PPRE1 | RCC_CFGR_PPRE2))
               == (RCC_SYSCLK_DIV1 | RCC_HCLK_DIV4 | (RCC_HCLK_DIV2 << 3U))
        && now.hclk == 168000000U && now.reload == 167999U && now.primask == 0
        && (now.flash & FLASH_ACR_LATENCY) == FLASH_LATENCY_5
        && (PWR->CR & PWR_CR_VOS) == PWR_REGULATOR_VOLTAGE_SCALE1
        && now.iwdg == 0 && IWDG->PR == IWDG_PRESCALER_64 && IWDG->RLR == 4095U;
}
#endif

static void value(const char *format, uint32_t number)
{
    embed_diagnostic_init_value(format, number);
}

static void location(const char *prefix, const char *file, uint32_t line)
{
    char text[64];
    /* Limit file names so output remains within the checked 63-byte marker. */
    (void)snprintf(text, sizeof(text), "%s=%.32s:%lu", prefix, source_basename(file), (unsigned long)line);
    embed_diagnostic_init_text(text);
}

void embed_init_report(void)
{
    uint32_t failures = 0;
    for (uint32_t i = 0; i < record_count; i++) {
        init_record_t *r = &records[i];
        char stage[64];
        (void)snprintf(stage, sizeof(stage), "STAGE=%s", r->function);
        embed_diagnostic_init_text(stage);
        value("HAL_STATUS=%lu", r->status);
#ifdef EMBED_PLL_RECOVERY
        value("EFFECTIVE_STATUS=%lu", r->effective_status);
#endif
        value("HANDLER_CALLS=%lu", r->handlers);
        location("CALL", r->file, r->line);
        if (r->return_line) {
            (void)snprintf(stage, sizeof(stage), "RETURN_FN=%.40s", r->return_function);
            embed_diagnostic_init_text(stage);
            value("RETURN_STATUS=%lu", r->return_status);
            location("RETURN", r->return_file, r->return_line);
        }
        if (r->status != HAL_OK || r->return_line) failures++;
        value("PRE_CR=0x%08lX", r->before.cr);
        value("PRE_CFGR=0x%08lX", r->before.cfgr);
        value("PRE_PLL=0x%08lX", r->before.pll);
        value("POST_CR=0x%08lX", r->after.cr);
        value("POST_CFGR=0x%08lX", r->after.cfgr);
        value("POST_PLL=0x%08lX", r->after.pll);
        value("POST_CSR=0x%08lX", r->after.csr);
        value("FLASH_ACR=0x%08lX", r->after.flash);
        value("IWDG_SR=0x%08lX", r->after.iwdg);
        value("SYSTICK_LOAD=%lu", r->after.reload);
        value("PRIMASK=%lu", r->after.primask);
        value("HCLK_VAR=%lu", r->after.hclk);
        if (i == 1) {
            uint32_t pll = r->before.pll;
            /* Correct decoding; unlike the buggy raw-bit comparisons in HAL. */
            uint32_t match = (pll & RCC_PLLCFGR_PLLSRC) == RCC_PLLSOURCE_HSE
                && (pll & RCC_PLLCFGR_PLLM) == 25
                && ((pll & RCC_PLLCFGR_PLLN) >> RCC_PLLCFGR_PLLN_Pos) == 336
                && ((((pll & RCC_PLLCFGR_PLLP) >> RCC_PLLCFGR_PLLP_Pos) + 1) * 2) == 2
                && ((pll & RCC_PLLCFGR_PLLQ) >> RCC_PLLCFGR_PLLQ_Pos) == 4;
            value("PRE_PLL_MATCH=%lu", match);
            value("PRE_SYSCLK_PLL=%lu", (r->before.cfgr & RCC_CFGR_SWS) == RCC_CFGR_SWS_PLL);
        }
    }
    value("HAL_FAILURES=%lu", failures);
#ifdef EMBED_PLL_RECOVERY
    value("PLL_RECOVERY_CANDIDATE=%lu", pll_recovery_candidate);
#else
    embed_diagnostic_init_text("RECOVERY_NOT_ASSUMED");
#endif
}
