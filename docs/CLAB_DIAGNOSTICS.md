# cLAB integration diagnostics after successful reference upload

Update: the probe has now been tested on hardware and reported INIT_ERRORS=1,
SKIP_INIT_ERROR, followed by normal trace stop. Generated code was skipped.
The next image to test is the initialization-only diagnostic described in
[CLAB_INITIALIZATION.md](CLAB_INITIALIZATION.md); defer Blink until its report
identifies the error. The earlier candidate hashes below remain preserved.

## Hardware evidence and current hypothesis

The user confirmed that the pristine local official reference BIN successfully
ran through the direct-upload interface, producing LED1, LED3 and PRINT traces.
Its SHA-256 is
`2a15d95cad06330a5109133316a1012448b796dc50e7782df700688f4f34e607`.
The earlier EmbedLang remote_blink BIN, SHA-256
`4f759e3b0c34322f89ea4737f14801c76abc0145cd64a73a62f1d897d4abe57c`,
repeatedly produced LoaderGeneric.waitInfo() Timeout on that same path.
The direct-upload path can therefore load the official reference successfully;
the earlier generic upload-path suspicion is no longer the leading explanation.

The strongest identifiable suspects are the integration's pre-trace fail-stop
Error_Handler and its different C build profile. A real HAL clock/watchdog error
would have disabled interrupts and looped before trace initialization. The
official reference returns from Error_Handler instead. No real HAL error has
been observed yet; this is a concrete behavioral difference and a hypothesis,
not a proven root cause. The -Os profile is another variable, not a demonstrated
compiler defect. The timeout message alone still does not establish where
execution stopped. No language/backend bug was demonstrated.

## Differences and changes

| Item | Old failing integration vs successful reference | Current candidate |
| --- | --- | --- |
| Startup/reset | Same official startup, data/BSS/libc/SystemInit sequence | Unchanged |
| CPU | Both Cortex-M4, ARMv7E-M, Thumb-2, hard-float ABI | Unchanged |
| C flags | EmbedLang -Os without DEBUG; reference -O0 with DEBUG | Default clab-reference profile: -O0, DEBUG |
| Link flags | Both nano/nosys and original RAM script; reference explicitly uses -static and grouped -lc/-lm | Explicit static/library group restored |
| Clock config | Same HSE/LSI and PLL/clock-divider source | Unchanged |
| GPIO config | Same PD13/14/15 initial levels/config and clocks | Unchanged |
| Watchdog | Same prescaler 64/reload 4095 | Unchanged; no refresh or disable |
| Error_Handler | EmbedLang disabled interrupts and never returned; reference returns | Official returning behavior; diagnostic counter only |
| Trace | Same original init/start/CRC/stop source; original example also printed/dumped | Bounded diagnostic PRINT/P0 markers; original trace implementation unchanged |
| Application entry | C main called renamed generated main | Same for Blink; probe calls a generated two-argument function directly |
| RAM/vectors | Same official RAM contract, no demonstrated violation | Unchanged and verified for each ELF/BIN |

`firmware/build.py` now defaults to `--profile clab-reference`. The optional
`--profile size` retains -Os solely as a controlled comparison. Diagnostic
images use the same C wrapper under a compile-time diagnostic switch. There are
no changes to grammar, AST, semantic analysis, IR, ARM emission, or language rules.
The unused driver sources omitted from the vendor snapshot do not participate
in the reference's retained linked application code.

GNU object section comparisons found identical bytes **before relocation** for
SystemClock_Config, HAL_Init, HAL_RCC_OscConfig, HAL_RCC_ClockConfig, MX_GPIO_Init,
MX_IWDG_Init, MX_TRACE_Init, SDK_TRACE_Start, SDK_TRACE_Stop and SysTick_Handler
between the new -O0 candidate and the successful reference build. This does not
mean the complete binaries or relocated function addresses are identical.
The local comparison evidence is `firmware/build/diagnostic_comparison.json`.

## Diagnostic behavior

`examples/diagnostic_probe.emb` defines `diagnostic_probe(a: u32, b: u32) -> u32`
which multiplies its arguments. It also has the required ordinary EmbedLang main.
The diagnostic C wrapper calls `embed_fn_diagnostic_probe(6, 7)` directly and
records its return. This tests C-to-generated argument/return ABI without any
GPIO/timing runtime call from generated code. The generated main symbol is still
renamed/retained as embed_program_main; only the probe entry is executed here.

The Blink diagnostic calls the actual `examples/remote_blink.emb` main through
embed_program_main. Its source is unchanged. It toggles the green LED ten times,
250 ms apart, ends low and returns. The diagnostic then waits an additional
250 ms as a visible final trace interval, for nominal total 2.75 seconds plus
initialization. The probe has only this final 250 ms delay. Both fit the SDK's
approximately eight-second budget. The extra interval is not claimed to be a
loader protocol requirement.

Expected PRINT records:

| Probe | Blink |
| --- | --- |
| INIT_ERRORS=0 | INIT_ERRORS=0 |
| BEFORE_GENERATED | BEFORE_GENERATED |
| PROBE_RESULT=42 | |
| AFTER_GENERATED | AFTER_GENERATED |
| TRACE_COMPLETE | TRACE_COMPLETE |

P0 is high around the generated call and low after it returns; PRINT events
bracket each message. P1 pulses on a reported initialization error or a wrong
probe result. PROBE_MISMATCH accompanies an unexpected result. TRACE_COMPLETE
means the wrapper reached normal trace finalization; it is not a hardware pass
assertion. These event IDs come from the original trace.h.

INIT_ERRORS counts Error_Handler calls during initialization, not every possible
hardware failure. It is stored in ordinary application BSS before trace startup.
The handler does not access trace registers/buffers before MX_TRACE_Init. On a
nonzero count, the wrapper records INIT_ERRORS and SKIP_INIT_ERROR, skips generated
code and returns to SDK_TRACE_Stop. It cannot detect an initialization routine
that hangs without returning/calling the handler.

Markers use only fixed formats and short messages (at most 63 characters);
capacity checks reserve both PRINT timestamp events and the print record before
calling the original API. The event and print areas cannot be overrun by these
markers. The wrapper does not change task_id, reserved SRAM or CCM allocation.

Important interpretation: cLAB delivers a finalized trace. If user code hangs or
faults before SDK_TRACE_Stop, earlier in-memory markers may not be returned.
An absent waveform after a timeout does not prove that BEFORE_GENERATED was
never executed. These candidates isolate stages across separate bounded runs;
they do not introduce a streaming debug channel or a new fault/watchdog handler.

## Reproduce locally

With JDK 17, installed Python requirements, and `$armBin` set as documented in
STM32_RUNTIME.md:

```powershell
.\gradlew.bat --no-daemon :compiler:test :compiler:installDist
python firmware/build.py examples/diagnostic_probe.emb --diagnostic probe --toolchain-bin $armBin
python firmware/build.py examples/remote_blink.emb --diagnostic blink --toolchain-bin $armBin
python firmware/build.py examples/remote_blink.emb --diagnostic blink --profile size --toolchain-bin $armBin
python firmware/build.py examples/remote_blink.emb --toolchain-bin $armBin
python tests/firmware_checks.py -v
python tests/clab_diagnostics.py -v
python tests/arm_execution.py --assembler "$armBin/arm-none-eabi-as.exe" --linker "$armBin/arm-none-eabi-ld.exe"
```

Each image directory contains firmware.elf, firmware.bin, map, disassembly,
symbols, stack-usage reports and verification.json. New reports include the
profile, diagnostic mode, C flags and hashes of integration source files.

## Executed local results

- 76 compiler JUnit tests passed, 0 failures/errors.
- 15 existing ARM execution checks passed.
- 13 firmware integration tests passed, including returning Error_Handler with
  interrupts still enabled.
- 6 diagnostic tests passed: ELF/profile checks; real generated argument/return
  and marker order; equal finite Blink behavior in both profiles; injected
  initialization error; injected incorrect probe return; full-buffer guard.
- All four new candidates assembled/linked and passed ELF/BIN verification.
  Vectors are at 0x2000D000, initial SP 0x20020000, all allocated sections stay
  within [0x2000D000,0x20020000), no unresolved symbols, minimum heap 512 bytes,
  minimum stack 1,024 bytes. No application allocations enter trace CCM RAM.
- Local execution ran actual startup, libc initialization, generated code,
  diagnostic formatting, official trace/CRC and reset-request code. Hardware
  initialization/GPIO/delay/frequency calls were intercepted; task_id was
  synthetic. Both candidate profiles reached valid CRC finalization/reset.

| Output under firmware/build | BIN bytes | Free bytes after linker reservations | Observed stack with hardware stubs |
| --- | ---: | ---: | ---: |
| diagnostic_probe/firmware.bin | 11,988 | 63,656 | 472 |
| diagnostic_blink/firmware.bin | 12,008 | 63,640 | 464 |
| diagnostic_blink_size/firmware.bin | 9,308 | 66,336 | 464 |
| remote_blink/firmware.bin (new unmarked -O0 build) | 8,628 | 67,608 | 88 for generated main with HAL/trace stubs |

These stack measurements exclude real hardware callees/interrupts and are not
full hardware stack bounds. Known upstream unused-parameter and GNU linker
RAM-RWX/stack-note warnings remain visible in build logs. No new candidate was
uploaded or executed on physical hardware by the agent.

Candidate SHA-256:

```text
diagnostic_probe       09cb2fefc7a340809cf223962aba7801f5b709fa421895dc9bdb38a54f78660b
diagnostic_blink       b8391625fd7988b818a98bc35f2e487d706d662ebf2f0e6a19163839b6a4fbed
diagnostic_blink_size  68bebd51c86ea0056782de08a570d92b1d2b6f4df331b99c1b6d5c2f611e76da
remote_blink          433207d561f281b0b18d048c91872c0d19910cfd5ab99c41c829d2d8c20d5d26
```

The known-failing old BIN/ELF/report are preserved under the ignored
`.tools/known-failing-remote-blink/` directory before the normal output was
rebuilt. The successful official reference artifact remains unchanged under
`.tools/sdk-clab-reference-build/`.

## Manual hardware test order

No upload command is included. Use the same direct-upload session/profile that
successfully ran the official reference, and compare the uploaded file hash.

1. **diagnostic_probe/firmware.bin**. Require INIT_ERRORS=0, PROBE_RESULT=42,
   BEFORE/AFTER and TRACE_COMPLETE. If it times out, the integration/startup or
   platform handoff is still suspect; do not infer that the pure function failed
   merely because no trace was returned. If it logs an init error, retain that
   trace and stop before testing Blink.
2. **diagnostic_blink/firmware.bin**. Require the same lifecycle markers and ten
   green LED toggles, ending low. Probe success followed by this failure narrows
   the difference to GPIO/runtime/delay execution or its interaction with hardware.
3. **remote_blink/firmware.bin**, the new unmarked -O0 candidate. If marked Blink
   succeeds but this fails, print/marker presence or the resulting binary/layout
   becomes a variable to isolate. This would not by itself prove PRINT mandatory.
4. **diagnostic_blink_size/firmware.bin**, optional, only after the -O0 version
   succeeds. This holds application/markers/error-handler behavior constant while
   comparing -Os without DEBUG against -O0 with DEBUG. A difference would implicate
   that build profile, not automatically identify a particular bad instruction.

Save file hash, loader status, PRINT messages and trace data from each actual
run. Report hardware success only for the exact image actually tested. The
current changes align integration with the known-working baseline and improve
diagnosis; they are not yet a hardware-confirmed resolution of the timeout.
