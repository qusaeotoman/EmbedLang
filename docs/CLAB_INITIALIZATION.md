# Initialization error investigation

Update: the user subsequently confirmed HAL_RCC_OscConfig's error at line 549,
matching active PLL parameters, successful clock/watchdog initialization and
168 MHz SystemCoreClock on hardware. The investigation below is preserved as
the record of how that cause was isolated. The new opt-in guarded recovery is
documented in [CLAB_PLL_RECOVERY.md](CLAB_PLL_RECOVERY.md); the initialization-only
BIN and successful reference remain unchanged.

## What the hardware result establishes

The user observed this from the previously built diagnostic_probe BIN:

```text
0.012: INIT_ERRORS=1
0.031: SKIP_INIT_ERROR
SDK-1.1M Trace stop
```

The wrapper reached trace initialization, recorded exactly one Error_Handler
call, deliberately skipped generated code and finalized the official trace.
This result establishes no failure inside generated EmbedLang code: none ran.
The previous counter does not identify the failing call or HAL return status.

## Exact counter and call paths

`firmware/src/clab_diagnostics.c` defines an application-BSS volatile uint32
counter, initially zero after startup. Only embed_diagnostic_init_error()
increments it. Diagnostic Error_Handler in `firmware/src/board_main.c` calls that
function once per invocation, then returns. There are three original call sites:

| HAL call | HAL call location | Error_Handler location |
| --- | --- | --- |
| HAL_RCC_OscConfig | board_main.c:151 | board_main.c:153 |
| HAL_RCC_ClockConfig | board_main.c:164 | board_main.c:166 |
| HAL_IWDG_Init | original Core/Src/iwdg.c:36 | iwdg.c:38 |

HAL_Init is called at board_main.c:79; its return is ignored by the original
application and does not increment this counter. GPIO initialization returns
void and has no Error_Handler call. SystemInit and trace initialization do not
call this handler. The pinned HAL_Init also ignores HAL_InitTick's status and
returns HAL_OK; the detailed recorder captures nested failure-return locations
so this case need not be mistaken for complete success.

The original official main uses the same HAL/clock/GPIO/watchdog/trace sequence,
parameters, and three handler call sites. Its Error_Handler is empty and returns.
Our initial Milestone 4A version instead disabled interrupts and looped there,
which could prevent all trace reporting when a HAL error occurred. The later
diagnostic returned but conservatively skipped user code after any recorded error.
These differing policies explain how a reference can run while EmbedLang stalls
or skips, even if both encounter the same initialization status.

## Concrete bug found in the pinned HAL

Pinned revision: `430df587cbb7630efd763579576f5545e31756fb`.
In `stm32f4xx_hal_rcc.c:535–549`, when PLL already supplies SYSCLK,
HAL_RCC_OscConfig attempts to allow an identical PLL request. Its comparisons
at lines 545–547 compare masked register bits directly to decoded parameters:

| Field for requested HSE/M=25/N=336/P=2/Q=4 | Masked register value | HAL parameter |
| --- | --- | --- |
| PLLN | 0x00005400 | 336 (0x150) |
| PLLP | 0 | 2 |
| PLLQ | 0x04000000 | 4 |

READ_BIT masks without decoding/normalizing. These values therefore compare
unequal despite an identical configuration, and line 549 returns HAL_ERROR.
The correct encodings are demonstrated by the same source file's PLL write
formula at lines 494–498 and the device header's field positions. No HAL code
has been patched to suppress that return.

SystemInit in this repository configures FPU/VTOR but does not reset RCC. Thus an
already-configured clock inherited from a RAM loader is possible. The actual
cLAB handoff register values remain unmeasured; this is the leading explanation,
not yet confirmation that line 549 caused this particular hardware error.
Other possibilities remain an oscillator timeout, clock switching error, or
watchdog update timeout. The detailed image distinguishes them.

## Reproduction with actual ARM HAL code

Local Cortex-M4 execution used a **synthetic** warm register state derived from
the official parameters: PLLCFGR=0x04405419, CFGR=0x0000940A, HSE/PLL ready,
LSI on/ready. HAL_RCC_OscConfig returned HAL_ERROR at the original line 549;
the requested and decoded PLL configurations were identical and unchanged.
HAL_RCC_ClockConfig then succeeded, SystemCoreClock became 168000000,
SysTick LOAD became 167999, and HAL_IWDG_Init succeeded.

The pristine successful reference ELF was also executed with this same modeled
state and the actual HAL initialization routines: Error_Handler was entered
once, returned, and the original example completed with its LED/print/dump trace,
CRC and reset request. This demonstrates that the reference **can** experience
the same error and still finish. It does not claim to measure its real-board
error count or confirm the loader's real register state.

Additional modeled cases distinguish a real PLL mismatch, LSI timeout
(HAL_TIMEOUT at rcc.c:368), and IWDG update timeout
(HAL_TIMEOUT at hal_iwdg.c:181). GPIO/delays are intercepted and readiness flags
are synthetic; these tests do not simulate oscillator physics or real watchdog
timing. Their purpose is to exercise actual HAL branches and diagnostic paths.

## Is continuing safe?

Do not blanket-ignore INIT_ERRORS=1. An already-active, identical, ready PLL
rejected solely by the broken comparison can be a recoverable false error:
there is no requested PLL change to perform. A genuine configuration mismatch,
oscillator timeout, failed switch or watchdog timeout is not automatically safe.

Before considering a narrowly scoped recovery, obtain the new hardware report.
It should identify rcc.c:549 with PRE_SYSCLK_PLL=1 and PRE_PLL_MATCH=1, and show
unchanged PLL registers, HSE/PLL/LSI ready flags, successful clock/watchdog calls,
FLASH latency 5, final HCLK_VAR=168000000, SYSTICK_LOAD=167999 and PRIMASK=0.
Even these values do not by themselves measure clock accuracy or prove tick
interrupt delivery; a later bounded probe can check behavior after the cause is
understood. Unexpected values need investigation instead of automatic recovery.

The new firmware always emits RECOVERY_NOT_ASSUMED and INIT_REPORT_ONLY, then
finalizes tracing. It never invokes the generated probe, regardless of status.
No PLL reconfiguration, peripheral reset, watchdog disable/refresh, error
suppression or compiler change was introduced.

## New initialization-only firmware

```powershell
python firmware/build.py examples/diagnostic_probe.emb --diagnostic init --toolchain-bin $armBin
```

Absolute BIN path:

`firmware/build/diagnostic_init/firmware.bin`

Build: successful. BIN size: **14,728 bytes**. SHA-256:
`bcbaacbd9f3417e2e2305ab14e8e4e4f98a59c6a89e54476b4f4af0d487713ef`.

The startup/vector table and original clock/GPIO/watchdog configurations are
retained. Diagnostic-only wrappers record each of the four HAL calls in ordinary
application BSS, with before/after register snapshots and original call-site
file/line. The build generates instrumented copies of three HAL sources that
add a RAM-only recorder immediately before failure returns. Original file/line
are preserved via #line. Vendored files and their hashes/licenses remain intact;
the original status and control flow are preserved. These generated copies are
under ignored build output and their hashes are in verification.json.

No trace formatting/emission occurs in the early recorder or handler. Reporting
occurs only after MX_TRACE_Init and SDK_TRACE_Start, using the existing bounded
PRINT markers. Source names are bounded to 32 characters and messages to 63.
SysTick CTRL is not sampled because reading it clears COUNTFLAG. Other sampled
registers are read without configuring hardware. The recorder reports:

- STAGE, numeric HAL_STATUS, HANDLER_CALLS, and CALL=file:line.
- First nested RETURN_FN, RETURN_STATUS and RETURN=file:line on a failure return.
- RCC CR/CFGR/PLLCFGR before/after; RCC CSR, FLASH ACR, IWDG SR, SysTick LOAD,
  PRIMASK and the SystemCoreClock variable after each call.
- PRE_PLL_MATCH and PRE_SYSCLK_PLL for oscillator configuration.
- HAL_FAILURES, RECOVERY_NOT_ASSUMED, INIT_REPORT_ONLY.

HAL status codes: 0=HAL_OK, 1=HAL_ERROR, 2=HAL_BUSY, 3=HAL_TIMEOUT.
HAL_FAILURES counts top-level non-OK or recorded nested failures, while
INIT_ERRORS retains its original meaning of Error_Handler invocations.

For the reproduced PLL bug, the important part of the report is:

```text
INIT_ERRORS=1
STAGE=HAL_RCC_OscConfig
HAL_STATUS=1
HANDLER_CALLS=1
CALL=board_main.c:151
RETURN_FN=HAL_RCC_OscConfig
RETURN_STATUS=1
RETURN=stm32f4xx_hal_rcc.c:549
PRE_PLL_MATCH=1
PRE_SYSCLK_PLL=1
```

This is an example from synthetic local execution, not a predicted hardware
result. Retain the complete hardware PRINT report, especially the following
clock and watchdog stages, rather than only this excerpt. Trace is still
delivered on finalization, not streamed live. An actual initialization hang can
prevent the report from reaching the laboratory interface.

## Preservation and verification

The successful official reference and all four existing diagnostic/normal
BIN/ELF/report sets were preserved without overwriting them. Copies plus hashes
are in `.tools/preserved-init-diagnostics/manifest.json`; the original paths
remain unchanged. Only the new `diagnostic_init` output directory was built.

All local checks passed:

- 76 compiler JUnit tests, 0 failures/errors.
- 15 existing ARM execution checks.
- 13 runtime/firmware integration tests.
- 6 existing marked-diagnostic tests.
- 6 new initialization tests, including actual HAL and pristine-reference
  warm-PLL reproduction, distinct timeout sources, ELF validation and preserved
  artifact hashes. Trace-order assertions reject PRINT/Timestamp before init/start.

Commands: `python tests/firmware_checks.py -v`,
`python tests/clab_diagnostics.py -v`, `python tests/clab_init_checks.py -v`, plus
the Gradle and ARM execution commands in CLAB_DIAGNOSTICS.md. The pristine
reference comparison is optional when that earlier ELF is not present; it was
present and passed during this investigation, with no skipped tests.

ELF/BIN verification passed: vectors 0x2000D000, initial SP 0x20020000,
76 KiB application RAM limit, no unresolved symbols, no reserved-memory
allocations, minimum heap 512 bytes and stack 1,024 bytes. Free RAM after
reservations is 60,480 bytes. Observed synthetic warm-path stack use was
672 bytes; this excludes real interrupts and is not a general hardware bound.
No new build warning beyond the existing upstream/compiler-library warnings
was found. No compiler, AST, IR, backend, language rule or vendor source was changed.

No automatic upload or laboratory access was performed. Manually test only this
new initialization report next, then use its exact stage/status/register data
to decide whether the error is the demonstrated benign repeated-PLL comparison
or a different, potentially fatal initialization problem.
