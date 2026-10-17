# ITMO.cLAB preparation

This integration follows [SDK_cLAB at the pinned revision](https://github.com/lmtspbru/SDK_cLAB/tree/430df587cbb7630efd763579576f5545e31756fb).
The user subsequently confirmed successful direct upload and execution of the
pristine local reference BIN, with LED1/LED3/PRINT waveforms. The earlier
EmbedLang Blink BIN timed out on that same path. New integration candidates
are locally verified only: see [CLAB_DIAGNOSTICS.md](CLAB_DIAGNOSTICS.md).
No agent upload or credential access was performed. The initial public-site
timeout describes an earlier local investigation, not the current status of
the user's working upload interface.

## Loader contract verified in source

| Item | Official source / value retained |
| --- | --- |
| SRAM vector relocation | `Core/Src/system_stm32f4xx.c`: VECT_TAB_SRAM, VECT_TAB_OFFSET=0xD000; SystemInit writes VTOR=0x2000D000 |
| Application RAM | `STM32F407VGTX_RAM.ld`: origin 0x2000D000, length 76 KiB, end 0x20020000 |
| Initial stack | `_estack=0x20020000`; first vector word |
| Reset/vector table | `Core/Startup/startup_stm32f407vgtx.s`, .isr_vector first in binary |
| Tick | `Core/Src/stm32f4xx_it.c`: SysTick_Handler calls HAL_IncTick |
| Trace CRC | `Core/Inc/trace.h`: 0x10000000 |
| Trace metadata | 0x10000004, includes task_id (initialization preserves it) |
| Trace events | 0x10000014 up to print area at 0x10005000 |
| Print / dump | 0x10005000 / 0x1000A000 |
| Upload artifact | Official README requests binary conversion, `objcopy -O binary` |
| Execution budget | Official README says approximately eight seconds |

The full 64 KiB CCM region is left for official trace use. No application
sections are placed there. Lower SRAM `[0x20000000,0x2000D000)` is left untouched
by application allocation. The template also declares Flash, but all application
sections are linked into RAM. No bootloader/startup address is guessed from a
generic STM32 Flash example.

The pinned `.cproject` Debug C linker selects the RAM script; its Release C
configuration still selects Flash. The Python build explicitly uses the RAM
script in every build. Both configurations specify Cortex-M4 hard-float ABI;
our flags use `-mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard`.
Do not import Release defaults unchanged.

## Trace lifecycle and finite test

The C wrapper preserves HAL, clock, GPIO and IWDG initialization from the official
project. It starts trace recording before EmbedLang main and calls SDK_TRACE_Stop
after it returns. Stop calculates the official CRC and requests a reset. The
runtime never changes task_id, uses the original LED event IDs and bounds its
timestamp calls before they reach the print buffer. It does not reimplement the
trace format or allocate into trace regions.

The official CRC routine complements the running value after each byte. It is
not interchangeable with a standard CRC32 library call. Its original code is
retained and tested against an independent bitwise calculation.

`examples/remote_blink.emb` initializes the green LED low, toggles it ten times
with 250 ms delays, sets it low and returns. Expected trace: initial low, ten
alternating high/low states, final low (12 events, 96 event bytes). HAL delay
rounding and initialization add overhead to the nominal 2.5 seconds. This leaves
margin within the documented approximate eight-second window. The existing
`examples/blink.emb` remains infinite and is unsuitable for this finite test:
it never reaches normal trace finalization. The watchdog is preserved, not used
as a substitute for orderly completion.

The ordinary unmarked build does not use SDK_TRACE_Print/SDK_TRACE_Dump;
unreferenced sections may be removed by the linker. Recovered diagnostic modes
add bounded official PRINT/P0 markers as well as LED timestamps. The user's
manual hardware test, separately from those markers' local tests, establishes
the recorded physical result.

## Manual reproduction (after review)

The recovered generated arithmetic probe has since been manually verified on
physical hardware by the user. See [the recorded result and raw timestamp
units](HARDWARE_VALIDATION.md). The ordinary Blink path below predates the
opt-in PLL recovery; use the recovered build for the confirmed warm-PLL loader
condition, following its specific instructions.

**Hardware-verified finite demonstration:** [recovered Blink](CLAB_BLINK.md), built from
`examples/remote_blink.emb` with `--diagnostic blink-recovered`. Use
`firmware/build/diagnostic_blink_recovered/firmware.bin` to reproduce the manual
demonstration. The user reported five LED pulses and successful completion on
2026-10-15; see [the preserved hardware report](HARDWARE_VALIDATION.md).
It retains the exact recovered probe guards and emits PRINT/P0
markers and every LED1 transition. Read the linked acceptance
sequence and timestamp caveats before interpreting displayed times.

1. Run the build/test commands in [STM32_RUNTIME.md](STM32_RUNTIME.md), using
   `examples/remote_blink.emb` with `--diagnostic blink-recovered`. Require a
   successful `verification.json` from the
   same build, and review its RAM bounds, vectors, unresolved-symbol list and hash.
2. Use `firmware/build/diagnostic_blink_recovered/firmware.bin`. Keep its matching ELF/map/report
   for diagnostics. Upload the raw BIN, not ELF, source or an archive. Do not
   rebase it to Flash or prepend another header/vector table.
3. Once the public service is reachable, open [ITMO.cLAB](https://sdk.ifmo.ru)
   yourself, sign in through its normal flow, and select the authorized SDK-1.1M
   task/session. Do not put credentials or session configuration in this repo.
4. Confirm the task expects this documented RAM firmware contract. Use its
   firmware upload control to select that BIN. Exact current control labels and
   task-specific requirements must be checked in the live UI; they were not
   available during local verification.
5. Start one remote run only after review/authorization. Save the returned trace
   and status. Compare LED1 transitions and approximately 250 ms spacing with
   the finite test's expected sequence; confirm trace finalization and reset.
6. Report the actual remote outcome separately. A successful local build, link
   or emulator run does not establish that the loader or physical board worked.
