/* Diagnostics only: official trace API, no alternate trace format or memory map. */
#include "clab_diagnostics.h"
#include "trace.h"
#ifdef EMBED_DIAGNOSTIC_INIT
#include "clab_init_detail.h"
#endif

extern void embed_program_main(void);
#ifdef EMBED_DIAGNOSTIC_PROBE
extern uint32_t embed_fn_diagnostic_probe(uint32_t a, uint32_t b);
#endif

static volatile uint32_t init_errors;

void embed_diagnostic_init_error(void)
{
    /* Error_Handler can run before trace initialization. Do not trace here. */
    init_errors++;
#ifdef EMBED_DIAGNOSTIC_INIT
    embed_init_note_handler();
#endif
}

static int room_for_marker(void)
{
    const volatile traceinfo_t *info = (const volatile traceinfo_t *)TRACEINFO_ADDR;
    /* Two timestamp records; a print record has 4-byte time + 1-byte length.
       All formats below produce at most 63 characters, including uint32 values. */
    return info->tracelog_size <= PRINTDATA_ADDR - TRACELOG_ADDR - 2 * sizeof(tracelog_t)
        && info->printlog_size <= DUMPBUF_ADDR - PRINTDATA_ADDR - (5 + 63);
}

static void marker(const char *text)
{
    if (!room_for_marker()) return;
    SDK_TRACE_Timestamp(PRINT, 1);
    SDK_TRACE_Print("%s", text);
    SDK_TRACE_Timestamp(PRINT, 0);
}

static void number_marker(const char *format, uint32_t value)
{
    if (!room_for_marker()) return;
    SDK_TRACE_Timestamp(PRINT, 1);
    SDK_TRACE_Print((char *)format, (unsigned long)value);
    SDK_TRACE_Timestamp(PRINT, 0);
}

static void event(uint8_t id, uint8_t value)
{
    const volatile traceinfo_t *info = (const volatile traceinfo_t *)TRACEINFO_ADDR;
    if (info->tracelog_size <= PRINTDATA_ADDR - TRACELOG_ADDR - sizeof(tracelog_t))
        SDK_TRACE_Timestamp(id, value);
}

#ifdef EMBED_DIAGNOSTIC_INIT
void embed_diagnostic_init_text(const char *text) { marker(text); }
void embed_diagnostic_init_value(const char *format, uint32_t value) { number_marker(format, value); }
#endif

void embed_diagnostic_run(void)
{
    number_marker("INIT_ERRORS=%lu", init_errors);
#ifdef EMBED_DIAGNOSTIC_INIT
    embed_init_report();
#ifdef EMBED_PLL_RECOVERY
    if (init_errors || !embed_init_application_allowed()) {
        event(P1, 1);
        marker("SKIP_INIT_ERROR");
        event(P1, 0);
        return; /* all unapproved failures remain fatal to application execution */
    }
    if (embed_init_pll_recovered()) marker("PLL_MATCH_RECOVERED");
#else
    marker("INIT_REPORT_ONLY");
    return; /* report only, even if initialization succeeded */
#endif
#endif
    if (init_errors) {
        event(P1, 1);
        marker("SKIP_INIT_ERROR");
        event(P1, 0);
        return; /* caller finalizes the official CRC and reset */
    }
    marker("BEFORE_GENERATED");
    event(P0, 1);
#ifdef EMBED_DIAGNOSTIC_PROBE
    uint32_t result = embed_fn_diagnostic_probe(6, 7);
    number_marker("PROBE_RESULT=%lu", result);
    if (result != 42) {
        event(P1, 1);
        marker("PROBE_MISMATCH");
        event(P1, 0);
    }
#else
    embed_program_main();
#endif
    event(P0, 0);
    marker("AFTER_GENERATED");
    /* A visible final trace interval, not a loader protocol requirement.
       Probe: ~250 ms total. Finite Blink: ~2750 ms plus initialization. */
    HAL_Delay(250);
    marker("TRACE_COMPLETE");
}
