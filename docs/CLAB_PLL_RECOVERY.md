# Confirmed active-PLL comparison recovery

## Evidence and scope

The user confirmed on physical ITMO.cLAB hardware:

- HAL_Init=HAL_OK.
- HAL_RCC_OscConfig=HAL_ERROR, originating at pinned stm32f4xx_hal_rcc.c:549.
- PRE_PLL_MATCH=1 and PRE_SYSCLK_PLL=1.
- HAL_RCC_ClockConfig=HAL_OK, HAL_IWDG_Init=HAL_OK, SystemCoreClock=168 MHz.

That confirms the previously isolated encoded-field comparison defect under the
laboratory's active-PLL handoff. This change adds an opt-in firmware-only recovery
for the generated arithmetic probe. It does not patch vendor files, relax the
language, or change the parser, AST, semantics, IR or ARM backend. Existing build
modes are not silently switched to recovery.

## Exact decoding and request

The official board wrapper requests HSE crystal mode, LSI on, PLL on, HSE as PLL
source, M=25, N=336, P=2 and Q=4. The encoded PLL word for these fields is
0x04405419. The checker uses the pinned device header's masks/positions:

| Field | Decode | Expected |
| --- | --- | ---: |
| PLLSRC | mask PLLSRC (already encoded source enum) | HSE |
| PLLM | mask PLLM | 25 |
| PLLN | (register & PLLN mask) >> PLLN position | 336 |
| PLLP | (((register & PLLP mask) >> PLLP position) + 1) * 2 | 2 |
| PLLQ | (register & PLLQ mask) >> PLLQ position | 4 |

These match the original HAL's PLL write formula and the actual request, unlike
the buggy comparisons of encoded N/P/Q bits with unencoded values.

## Two gates, with raw error evidence retained

The wrapper still calls the original HAL_RCC_OscConfig exactly once. It does not
skip oscillator initialization, disable/restart PLL, or write new RCC values.

The oscillator call's error is provisionally normalized to HAL_OK only when:

1. It is the expected second recorded initialization call with a non-null request.
2. The request exactly matches the official HSE/LSI/PLL settings above; additional
   oscillator selections, bypass requests, different dividers/sources and PLL-off
   requests are not eligible.
3. The raw return and captured first failure are HAL_ERROR, specifically from
   HAL_RCC_OscConfig in stm32f4xx_hal_rcc.c at original line 549. Timeout, busy,
   another return site or missing provenance is rejected. Vendor checksums pin
   the source to the examined revision before compilation.
4. Before the call, PLL is enabled and ready, HSE is enabled and ready without
   bypass, PLL supplies SYSCLK, the requested SYSCLK selector is also PLL, and
   all decoded PLL fields match the request.
5. After the call those conditions still hold, the full PLL register is unchanged,
   and required LSI enable/ready bits are both set. LSI need not have been ready
   before the HAL call if that call successfully enabled it; the pinned failure
   site is reached only after oscillator processing and the post-state is checked.

Raw HAL_STATUS=1 and its source/line remain in the report. EFFECTIVE_STATUS=0
shows only the narrow shim result; PLL_RECOVERY_CANDIDATE=1 is provisional.
The accepted false error does not call Error_Handler, so INIT_ERRORS=0 is expected.
HAL_FAILURES=1 may remain as a truthful count of raw HAL failures.

Immediately before any generated code is allowed, a second gate requires:

- Exactly four recorded calls in order: HAL_Init, HAL_RCC_OscConfig,
  HAL_RCC_ClockConfig, HAL_IWDG_Init; no recorder overflow or handler calls.
- HAL_OK for every effective result. No raw/nested failure is allowed except
  the single approved oscillator comparison. In particular, a HAL_InitTick
  failure ignored by the original HAL_Init/ClockConfig still blocks execution.
- Live PLL/HSE/LSI readiness and the exact decoded configuration again.
- SYSCLK/HCLK/APB divisors matching the official /1, /4 and /2 configuration,
  SystemCoreClock=168000000, SysTick LOAD=167999, and PRIMASK=0.
- FLASH latency 5 and voltage scale 1.
- Successful watchdog initialization, zero pending IWDG updates, prescaler 64
  and reload 4095 read back from its registers.
- No separate initialization Error_Handler count.

Only then does the wrapper emit **PLL_MATCH_RECOVERED**, BEFORE_GENERATED, and
call embed_fn_diagnostic_probe(6,7). It expects PROBE_RESULT=42, then
AFTER_GENERATED and TRACE_COMPLETE. If HAL initialization genuinely succeeds
without needing this exception, the same final gate permits the probe and no
PLL_MATCH_RECOVERED marker is printed.

Any unapproved error, mismatch, lost readiness or later initialization failure
is fatal **to application execution**: the probe is skipped and SKIP_INIT_ERROR
is reported, followed by normal trace CRC/reset completion. It does not hang in
an error loop or globally ignore HAL failures. All early checks/logging use
application RAM only; trace emission waits for official initialization/start.

## Build and artifact

```powershell
python firmware/build.py examples/diagnostic_probe.emb --diagnostic probe-recovered --toolchain-bin $armBin
```

Only `--profile clab-reference` is accepted for this candidate. The command uses
the existing official RAM startup/linker/runtime, -O0/DEBUG, nano/nosys specs and
the same failure-return instrumentation as the initialization-only diagnostic.
Original vendor files and license notices remain unmodified.

Absolute BIN path:

`firmware/build/diagnostic_probe_recovered/firmware.bin`

- Build and ELF/BIN verification: passed.
- BIN bytes: **16,164**.
- SHA-256: `fb5ec379f307a3e29477563233df78548e5de0bb16153883611e8b98142f3ea6`.
- Vectors: 0x2000D000, 392 bytes; initial SP: 0x20020000.
- All allocated sections stay in [0x2000D000,0x20020000); none occupy the
  laboratory's lower SRAM or trace CCM regions. No unresolved symbols.
- Minimum heap/stack reservations: 512/1,024 bytes. Free RAM after reservations:
  58,976 bytes. Matching ELF/map/symbols/disassembly/report/.su files are adjacent.
- Nominal application delay: 250 ms, plus initialization/report formatting,
  within the approximate eight-second laboratory budget under normal operation.
  Watchdog settings and refresh policy are unchanged.

## Tests executed

All passed locally:

- 76 compiler JUnit tests, 0 failures/errors.
- 15 existing ARM execution checks.
- 13 existing runtime/firmware tests.
- 6 existing marked-diagnostic tests.
- 6 initialization tests, including the pristine reference's original false error.
- 12 recovery tests, with fault-injection subcases for every PLL field/source,
  changed requests, missing enable/ready flags, bypass, wrong SYSCLK, LSI and IWDG
  timeouts, wrong HAL status or failure provenance, later HAL failures, nested
  tick setup failure, fake watchdog success without configuration, and live
  register drift after initialization. All denied application execution and
  emitted no PLL_MATCH_RECOVERED marker.

The positive path executed actual startup, HAL initialization, recovery guards,
generated ARM multiply function, formatting, trace CRC and reset request under
synthetic MMIO. It retained raw HAL_ERROR, passed the final gate, returned 42,
and finalized tracing. An all-HAL-OK path also passed without a recovery marker.
Observed positive-path stack use with modeled hardware was 680 bytes; this is
not a full real-interrupt/hardware stack bound. Local execution uses synthetic
register readiness and intercepted GPIO/delay/tick calls, not physical cLAB.

Commands after building all prerequisite images:

```powershell
.\gradlew.bat --no-daemon :compiler:test :compiler:installDist --rerun-tasks
python tests/firmware_checks.py -v
python tests/clab_diagnostics.py -v
python tests/clab_init_checks.py -v
python tests/clab_recovery_checks.py -v
python tests/arm_execution.py --assembler "$armBin/arm-none-eabi-as.exe" --linker "$armBin/arm-none-eabi-ld.exe"
```

## Preservation, remaining risks and manual check

All previous reference/diagnostic BINs, ELFs and reports retain their original
hashes. Seventeen artifacts were additionally copied into ignored
`.tools/preserved-pll-recovery/`, with a manifest. This build writes only the new
diagnostic_probe_recovered output directory. The vendor manifest still verifies.

This is pinned to a specific HAL branch and board configuration. An SDK/HAL
upgrade must be reviewed rather than extending this exception blindly. Register
readiness and HAL statuses cannot measure external crystal accuracy, supply
voltage, physical interrupt delivery, or all future hardware faults. The
conservative checks can reject an unexpected loader state; that is intentional.
No stack bound is claimed for arbitrary programs, and no watchdog behavior was
relaxed. Existing upstream/linker warnings remain visible in build logs.

The user has now manually tested this exact probe on physical ITMO.cLAB hardware
and reported PLL_MATCH_RECOVERED, BEFORE_GENERATED, PROBE_RESULT=42,
AFTER_GENERATED and TRACE_COMPLETE. See the [hardware validation record and
timestamp-unit investigation](HARDWARE_VALIDATION.md). No upload, flashing or lab
access was performed automatically. This verifies the arithmetic probe, not
other applications. If a later image reports SKIP_INIT_ERROR, preserve all
raw/effective statuses and register lines instead of weakening the gate.
