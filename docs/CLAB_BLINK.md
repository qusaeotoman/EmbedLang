# Recovery-enabled finite EmbedLang Blink

The user has verified both the recovered arithmetic probe and this finite Blink
image on physical ITMO.cLAB hardware. The Blink report, recorded on 2026-10-15,
includes five LED pulses and successful entry, exit and completion markers:
[hardware evidence and preserved trace](HARDWARE_VALIDATION.md). No automatic
upload or laboratory access was performed by the development agent.

## Integration and safety policy

`--diagnostic blink-recovered` selects the exact same initialization capture,
two recovery gates, C wrapper, startup, RAM linker script, trace library and
`clab-reference` flags as the hardware-tested `probe-recovered` mode. It omits
only the probe-selection macro, so the existing wrapper calls
`embed_program_main()` instead of `diagnostic_probe(6,7)`. The build rejects the
experimental size profile for both recovered modes.

There is no change to the language, frontend, AST, semantic analysis, IR, ARM
backend, runtime C implementation, vendor files or PLL recovery implementation.
The new mode only selects existing firmware integration code. Unapproved clock,
oscillator or watchdog failures still skip the application and finalize trace.
See [the precise recovery policy](CLAB_PLL_RECOVERY.md).

The compiler translates the existing `examples/remote_blink.emb` to `program.s`:

```text
fn main() -> void {
    gpio_mode(LED_GREEN, OUTPUT)
    gpio_write(LED_GREEN, LOW)
    let count: u32 = 0
    while count < 10 {
        gpio_toggle(LED_GREEN)
        delay_ms(250)
        count = count + 1
    }
    gpio_write(LED_GREEN, LOW)
}
```

The loop, counter, GPIO calls and ten delay calls are generated ARM assembly;
the C wrapper supplies only diagnostics and its existing final 250 ms interval.
The build renames the generated object symbol `main` to `embed_program_main`;
there is one C startup entry point. The ordinary infinite `blink.emb` is not used.

Green `LED_GREEN` is board ABI handle 1, SDK LED1, **PD13**. Provenance is the
pinned SDK-1.1M `SDK_EXTI/Core/Inc/main.h` pin definition and SDK_cLAB
`Core/Inc/trace.h` color/event definition, described in `firmware/THIRD_PARTY.md`.
`OUTPUT=1`, and LOW/HIGH are boolean false/true. The runtime configures the
verified port/mask and uses the official LED1 timestamp event after each write
or toggle. This includes every requested transition and the initial/final LOW
assignments; initialization happens before trace starts, as in the reference.

The full final initialization gate checks 168 MHz, matching live PLL/HSE/LSI,
bus divisors, SysTick reload/global interrupt mask, voltage scale/latency and IWDG
readback. The official watchdog remains enabled, prescaler 64, reload 4095;
the original HAL initializes and reloads it once. There is no application
watchdog refresh loop or disable. Nominal programmed delays total 2,750 ms
(ten times 250 ms plus the final interval), leaving margin against the
approximate eight-second lab window. Initialization, printing, HAL tick
rounding and execution overhead are additional. Reported hardware timestamps
and their conditional timing interpretation are recorded separately in
`HARDWARE_VALIDATION.md`.
The watchdog uses LSI, whose physical rate is not measured by local tests.

## Build and verify locally

Use the JDK, Python dependencies and ARM GNU setup in
[STM32_RUNTIME.md](STM32_RUNTIME.md), then:

```powershell
.\gradlew.bat --no-daemon :compiler:test :compiler:installDist --rerun-tasks
$armBin = '.tools/arm-gnu/arm-gnu-toolchain-13.3.rel1-mingw-w64-i686-arm-none-eabi/bin'
python firmware/build.py examples/remote_blink.emb --diagnostic blink-recovered --toolchain-bin $armBin
python tests/clab_blink_checks.py -v
```

The integration suite also requires the previously built reference, ordinary
Blink, diagnostic and recovered probe images. Those images are deliberately
preserved, rather than rebuilt over the binaries used for hardware comparisons.
Their setup and existing test commands are in `CLAB_DIAGNOSTICS.md`,
`CLAB_INITIALIZATION.md` and `CLAB_PLL_RECOVERY.md`.

Generated artifacts, all ignored by Git:

- BIN: `firmware/build/diagnostic_blink_recovered/firmware.bin`
- ELF: same directory, `firmware.elf`.
- Matching assembly, map, symbols, disassembly, verification JSON and C stack
  usage files are adjacent. Build log: `.tools/blink-recovered-build.log`.

Verified ARM GNU 13.3.Rel1 build:

| Property | Result |
| --- | --- |
| BIN bytes | 16,184 |
| BIN SHA-256 | `cc1875ee45bd5eed052b75dfbd8c98bc5b8f55f23fb6690e6bb1d964fd4c3fb5` |
| Vectors | 0x2000D000 |
| Initial SP | 0x20020000 |
| Reset vector | 0x2000D401 (Thumb) |
| BSS end | 0x200113B4 |
| Minimum heap / stack | 512 / 1,024 bytes |
| RAM free after linker reservations | 58,952 bytes |
| Unresolved symbols | None |

All allocated sections and load segments lie in official application SRAM
`[0x2000D000,0x20020000)`; BIN bytes match ELF sections exactly. The laboratory's
lower SRAM and CCM trace buffers are not used for application sections.
Existing upstream unused-parameter and linker executable-stack/RWX warnings
remain visible; the official RAM layout has not been redesigned to suppress them.

## Executed tests and preserved recovery

Verified recovery and the user's hardware result were committed first as
`5d6e81964511539811fb7ce34938dac5b30d74cf`
(`Fix cLAB PLL recovery and record physical probe success`). The working tree
was clean at that point. This Blink build option, tests and documentation are
preserved in a subsequent commit together with the physical Blink test report.

All **134 checks passed**, with no failures:

- 76 compiler JUnit tests; the compiler distribution was rebuilt.
- 15 existing ARM execution checks.
- 13 existing runtime/firmware tests.
- 6 existing marked diagnostic tests.
- 6 existing initialization tests, including the original reference comparison.
- 12 existing PLL recovery tests with fault-injection subcases.
- 6 new recovered Blink tests.

The new suite executes the real generated main, original startup/HAL, recovery
checks and trace code with synthetic MMIO and GPIO/delay/tick hooks. It checks
PD13 configuration, all ten toggles and eleven delay calls, clock/watchdog
failures, clean initialization without recovery, and live-state mismatches.
It verifies the actual HAL IWDG key writes (start/unlock/reload), trace-before-
initialization prohibition, final CRC, preserved task ID, vector relocation and
reset request. Synthetic trace data used 1,392 event bytes and 1,807 print bytes,
well below the official buffers. Observed stack use with hardware hooks was
672 bytes; this excludes a full physical interrupt worst-case analysis.

The Blink/probe integration source hashes and generated instrumented HAL copy
hashes match exactly. Their C flags differ only by the probe-selection macro.
Reference and physically successful probe BIN/ELF hashes were rechecked and
remain unchanged; additional copies are in ignored
`.tools/preserved-hardware-probe/` with a manifest. No compiler or vendor source
was changed. These local results are separate from the user's subsequent
successful physical Blink report.

## Expected trace and manual testing

For the confirmed warm matching-PLL state, PRINT includes full initialization
reports followed by:

```text
PLL_MATCH_RECOVERED
BEFORE_GENERATED
AFTER_GENERATED
TRACE_COMPLETE
```

`HAL_STATUS=1` at the known oscillator return remains visible, with
`EFFECTIVE_STATUS=0`; the other initialization stages succeed and INIT_ERRORS=0.
If the original HAL succeeds without this false error, no recovery marker is
expected. Genuine failures produce SKIP_INIT_ERROR and no generated execution.

P0 is high during generated main. Between BEFORE_GENERATED and AFTER_GENERATED,
LED1 records the following 12 states:

```text
LOW, HIGH, LOW, HIGH, LOW, HIGH, LOW, HIGH, LOW, HIGH, LOW, LOW
```

There are ten actual alternating transitions, separated by nominal 250 ms delay
calls. The initial LOW and first HIGH can be nearly adjacent; the final LOW
assignment repeats the already-low state after the tenth delay. AFTER_GENERATED
is followed by the final 250 ms wrapper delay, TRACE_COMPLETE and official
SDK_TRACE_Stop CRC/reset finalization. SDK_TRACE_Stop is not itself a PRINT
string; the lab may display its own trace-stop notification.

The official raw timestamp units are **microseconds**, verified from its formula
and actual ARM trace execution: synthetic 250 ms delay advances give 250,000 raw
units. The Web IDE decimal display units remain independently unverified;
the hardware report supports milliseconds as an explicitly labeled inference.
Do not equate local emulation with a hardware timing measurement. See
[timestamp details](HARDWARE_VALIDATION.md#trace-timestamp-units).

Manual testing order:

1. Retain the working reference and recovered probe BINs and their hashes as
   controls. Their original files and additional ignored backups remain intact.
2. Review this candidate's hash and verification JSON, then manually upload only
   `diagnostic_blink_recovered/firmware.bin` through the already working direct
   BIN interface in the authorized SDK-1.1M task.
3. Save the complete PRINT and LED1 trace. Require generated-entry/exit and
   completion markers, the expected ten transitions, and orderly trace stop.
4. On failure, preserve the exact trace and status. Re-test the known-good probe
   as a control if needed; do not relax clock guards or modify the compiler
   without evidence of a new failure.

No upload or lab access is performed by the build or tests. Physical Blink has
now passed according to the user's manual test. Independently calibrated elapsed
time, interrupt timing and watchdog expiry remain unverified. Emulator stack
observations are not a complete hardware/interrupt worst-case bound.
