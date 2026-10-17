# Detailed development and validation guide

> Public edition: six upstream files are intentionally omitted. Historical
> full-local-snapshot descriptions below do not imply those files are included.
> See [publication exclusions](../PUBLICATION_NOTES.md).

Commands below run from the repository root. This guide retains the milestone
build instructions and historical validation details. For the current overview,
see [README](../README.md).

# EmbedLang

A university project for an Embedded Systems Programming course: a small,
statically typed language with a compiler frontend written in Kotlin and ANTLR4.
Milestone 1 parses source, builds an AST, resolves names, and checks types.
Milestone 2 adds typed IR lowering and a textual IR printer. Milestone 3 emits
GNU Thumb-2 assembly text for STM32F407VGT6 (ARM Cortex-M4, ARMv7E-M).
Milestone 4A adds a separate STM32 runtime and verified RAM firmware build for
the SDK-1.1M board and ITMO.cLAB. Manual hardware tests have confirmed the
recovered cLAB F407 probe/Blink and the local F427 finite Blink; see the
[physical validation record](HARDWARE_VALIDATION.md).

## Prerequisites

- JDK 17, with `JAVA_HOME` pointing to the JDK and its `bin` directory on `PATH`.
- Internet access on the first build for the Gradle wrapper and Maven dependencies.
- Gradle is provided by the checked-in wrapper; no global installation is needed.

Pinned build: Kotlin 2.2.21, ANTLR tool/runtime 4.13.2, Gradle 8.14.3.

If this working copy has a portable JDK in the ignored `.tools/jdk/` folder,
you can use it from PowerShell without a system installation:

```powershell
$env:JAVA_HOME = (Get-ChildItem .tools/jdk -Directory | Select-Object -First 1).FullName
$env:GRADLE_USER_HOME = "$PWD/.tools/gradle-user-home"
```

## Build and test

Windows PowerShell, from the repository root:

```powershell
.\gradlew.bat build
.\gradlew.bat :compiler:test
.\gradlew.bat :compiler:run --args="examples/basic.emb"
.\gradlew.bat :compiler:run --args="examples/blink.emb"
.\gradlew.bat :compiler:run --args="--emit-ir examples/basic.emb"
.\gradlew.bat :compiler:run --args="--emit-ir examples/blink.emb"
.\gradlew.bat :compiler:run --args="--emit-asm examples/basic.emb"
.\gradlew.bat :compiler:run --args="--emit-asm examples/blink.emb"
```

Linux/macOS:

```sh
chmod +x gradlew
./gradlew build
./gradlew :compiler:test
./gradlew :compiler:run --args="examples/basic.emb"
./gradlew :compiler:run --args="examples/blink.emb"
./gradlew :compiler:run --args="--emit-ir examples/basic.emb"
./gradlew :compiler:run --args="--emit-ir examples/blink.emb"
./gradlew :compiler:run --args="--emit-asm examples/basic.emb"
./gradlew :compiler:run --args="--emit-asm examples/blink.emb"
```

`build` regenerates the ANTLR lexer/parser/visitor and runs the tests. Generated
Java is compiled together with the Kotlin frontend; generated sources stay under
`compiler/build/`. Test reports are under `compiler/build/reports/tests/test/`.
Milestone 3 verification: 76 passing JUnit tests, including all 57 previous tests.
Both assembly examples were accepted by GNU ARM assembler. An additional optional
ARM execution harness passed 15 checks using Unicorn Cortex-M4 emulation.

## Run the installed compiler

```powershell
.\gradlew.bat :compiler:installDist
.\compiler\build\install\embedlang\bin\embedlang.bat examples\blink.emb
.\compiler\build\install\embedlang\bin\embedlang.bat --emit-ir examples\blink.emb
.\compiler\build\install\embedlang\bin\embedlang.bat --emit-asm examples\blink.emb
```

On Linux/macOS, run `./gradlew :compiler:installDist`, then
`./compiler/build/install/embedlang/bin/embedlang examples/blink.emb`.
The installed executable is named `embedlang`. With its `bin` directory on `PATH`,
run `embedlang --emit-ir program.emb` to print typed IR to stdout.
Run `embedlang --emit-asm program.emb` to print GNU ARM assembly text to stdout.
Use `--help` for usage. Normal validation prints `OK` for valid input and diagnostics such as
`source.emb:2:14: semantic error [UNDEFINED_VARIABLE]: Undefined variable 'missing'`.
Exit codes: 0 success, 1 frontend errors, 2 usage or file-reading errors. The CLI
checks source and optionally emits IR or assembly text; it does not execute
programs or produce machine code. Neither emission mode prints partial output
when parsing or semantics fail.

## Compiler pipeline

```text
Source → ANTLR parse tree → AST → semantic analysis → typed IR → ARM assembly text
```

The existing parse/analyze APIs remain available. `Frontend.lower(source, file)`
returns typed IR after successful semantic analysis. IR preserves structured
control flow, typed expressions, bound local identities, and source locations.
The ARM backend consumes this IR without modifying it. See
[IR design and format](IR.md) and [ARM backend](ARM_BACKEND.md) for
register/stack conventions and explicitly documented execution policies.
Pin/mode constants remain external runtime data objects.

Optional host-side execution validation after `:compiler:installDist` requires
GNU `arm-none-eabi-as` / `arm-none-eabi-ld` on PATH, Python, `unicorn`, and
`pyelftools`:

```sh
python tests/arm_execution.py
```

This assembles/links test artifacts under ignored `.tools/arm-execution/` and
checks real ARM return values, nested calls, stack arguments, recursion, loops,
short-circuiting, and restored stack/register state. It creates no linker script
or STM32 runtime and does not run on the board. The standard Gradle test suite
requires none of these optional tools.

## Build STM32 / ITMO.cLAB firmware

Install ARM GNU Toolchain 13.3.Rel1 (GCC, binutils and newlib), Python 3.10+ and
`python -m pip install -r firmware/requirements-tests.txt`. Full portable Windows
installation instructions and Linux guidance: [STM32 runtime](STM32_RUNTIME.md).

```powershell
.\gradlew.bat --no-daemon :compiler:test :compiler:installDist
# Set $armBin to the ARM toolchain's bin directory, or omit --toolchain-bin if on PATH.
python firmware/build.py examples/remote_blink.emb --toolchain-bin $armBin
python firmware/build.py tests/fixtures/runtime_symbols.emb --toolchain-bin $armBin
python tests/firmware_checks.py
```

The output is `firmware/build/remote_blink/firmware.elf` and `firmware.bin`, with
map, disassembly, symbols, stack-usage files and `verification.json`. The builder
checks all external symbols and the official SRAM layout. The finite remote test
runs for about 2.5 seconds before returning to official trace finalization.
Keep the infinite `blink.emb` for compiler examples. No build command uploads or
flashes hardware. Review the [ITMO.cLAB procedure](ITMO_CLAB.md) before any
remote run; current upload UI availability is not established by local tests.

The firmware integration renames the generated object's main symbol and wraps it
with official initialization. Compiler behavior and language rules are unchanged.
Third-party revisions and licenses: [firmware attribution](../firmware/THIRD_PARTY.md).

Initial Milestone 4A validation: **76 JUnit tests + 15 existing ARM execution checks
+ 12 firmware tests passed**. Its original finite Blink BIN was 6,148 bytes;
repeat builds produced identical binary hashes. See the historical
[validation report](MILESTONE_4A_VALIDATION.md) for memory use, warnings and
the original hardware checks.

After the official reference succeeded on hardware and the earlier EmbedLang
BIN timed out, firmware builds were aligned with the reference's `-O0`/`DEBUG`
configuration and returning error handler. New marked diagnostics are available:

```powershell
python firmware/build.py examples/diagnostic_probe.emb --diagnostic probe --toolchain-bin $armBin
python firmware/build.py examples/remote_blink.emb --diagnostic blink --toolchain-bin $armBin
python firmware/build.py examples/remote_blink.emb --diagnostic blink --profile size --toolchain-bin $armBin
python tests/firmware_checks.py
python tests/clab_diagnostics.py
```

Build the ordinary `remote_blink` as above before running these tests. Initial
marked-diagnostic verification: **76 compiler tests, 15 ARM execution checks,
13 runtime tests and 6 diagnostic tests passed**. These were local checks;
subsequent recovered-probe and Blink hardware results are recorded below. See
[diagnostic procedure and results](CLAB_DIAGNOSTICS.md).

The first hardware probe reported `INIT_ERRORS=1` and `SKIP_INIT_ERROR`, then
stopped tracing successfully. The initialization-only investigation used:

```powershell
python firmware/build.py examples/diagnostic_probe.emb --diagnostic init --toolchain-bin $armBin
python tests/clab_init_checks.py -v
```

This creates `firmware/build/diagnostic_init/firmware.bin`, which reports HAL
stages, statuses, original source lines and register snapshots without executing
generated code. See [initialization investigation](CLAB_INITIALIZATION.md).

Hardware has since confirmed the repeated-PLL comparison bug at HAL line 549.
A guarded recovery is available in opt-in probe and Blink images:

```powershell
python firmware/build.py examples/diagnostic_probe.emb --diagnostic probe-recovered --toolchain-bin $armBin
python tests/clab_recovery_checks.py -v
```

It verifies the exact error source, requested configuration, ready oscillators,
and complete final initialization state before emitting PLL_MATCH_RECOVERED and
calling the generated probe. Other failures skip application execution. See
[PLL recovery policy and results](CLAB_PLL_RECOVERY.md). The user has now
confirmed physical execution of this exact recovered probe: PLL_MATCH_RECOVERED,
BEFORE_GENERATED, PROBE_RESULT=42, AFTER_GENERATED, TRACE_COMPLETE. See the
[hardware record and trace timestamp units](HARDWARE_VALIDATION.md).

Prepare the finite Blink demonstration with those identical recovery checks:

```powershell
python firmware/build.py examples/remote_blink.emb --diagnostic blink-recovered --toolchain-bin $armBin
python tests/clab_blink_checks.py -v
```

The new BIN is `firmware/build/diagnostic_blink_recovered/firmware.bin`. It runs
the compiler-generated finite program, traces every green LED transition on
PD13, and emits BEFORE_GENERATED, AFTER_GENERATED and TRACE_COMPLETE. Its
programmed delays total 2.75 seconds; independently calibrated hardware duration
remains unverified.
See [Blink verification and manual upload procedure](CLAB_BLINK.md).
The user has now confirmed physical Blink execution through ITMO.cLAB: five LED
pulses, INIT_ERRORS=0, PLL_MATCH_RECOVERED and generated-entry/exit/completion
markers. The [hardware record](HARDWARE_VALIDATION.md) preserves the
2026-10-15 report and displayed timestamps, with timing-unit caveats. No automatic
upload was performed.

## Local SDK-1.1M Flash

For a physically connected SDK-1.1M, use the separate
[local Flash build and USB/JTAG procedure](LOCAL_SDK11M.md). Never program
the cLAB SRAM BIN into local Flash.

The attached local module has now been physically identified as **STM32F427VIT6**,
and OpenOCD confirms device ID 0x419 and 2 MiB Flash. Use the explicit F427 build:

```powershell
python firmware/build_local.py examples/remote_blink.emb --mcu stm32f427vit6 --toolchain-bin $armBin
python tests/local_firmware_checks.py -v
python tests/local_f427_checks.py -v
```

These commands only build/test `firmware/build/local_blink_f427/firmware.elf`
and `firmware.bin`; they do not flash or change USB drivers. The earlier F407
local and successful cLAB images remain intact. See [F427 preparation and
programming approval boundary](LOCAL_F427.md).

The user has now observed five green LED pulses and final OFF on the local F427
after approved sector-0 programming. Full Flash readback verified the image and
unchanged unrelated sectors/options. See the
[local physical validation record](HARDWARE_VALIDATION.md#local-stm32f427vit6-programmed-and-physically-observed-blink),
including the explicitly accepted BOOT0 uncertainty and post-run debug warning.

## Local F427 OLED

The separate OLED demonstration renders **THE BEST GROUP** using compiler-
generated EmbedLang calls and the official SDK_OLED 7x10 font driver. The program
supplies printable ASCII codes through five scalar OLED built-ins; strings are
still excluded, and the grammar, IR and ARM backend are unchanged.

```powershell
.\gradlew.bat --no-daemon :compiler:test :compiler:installDist
python firmware/build_local.py examples/oled_group.emb --mcu stm32f427vit6 --oled --toolchain-bin $armBin
python tests/local_oled_checks.py -v
```

Outputs are `firmware/build/local_oled_f427/firmware.elf` and `firmware.bin`.
These build/test commands never access the board. The hardware-tested Blink and
cLAB outputs remain separate. The separately approved OLED programming and
verification succeeded. On 2026-10-17 the user confirmed that THE BEST GROUP
appears clearly on the physical board. See
[official wiring, API, build and test results](LOCAL_OLED.md).

Local OLED preparation verification: **160 passing checks** (all previous 147,
six new compiler tests and seven OLED integration tests). The 13,576-byte OLED
BIN passed F427 ELF/memory verification; physical OLED operation is user-confirmed.

## Example syntax

```text
fn add(a: i32, b: i32) -> i32 {
    return a + b
}

fn main() -> void {
    let total: i32 = add(10, 20)
    gpio_mode(LED_GREEN, OUTPUT)
    if total >= 30 {
        gpio_write(LED_GREEN, HIGH)
    } else {
        gpio_write(LED_GREEN, LOW)
    }
}
```

Types: `i32`, `u32`, `u8`, `bool`, `void`. Simple statements end at a newline,
semicolon, or closing brace. Variables use explicit types and mandatory
initializers. Integer literals are contextually typed; named numeric types never
implicitly convert. Every program requires `fn main() -> void`.

## Layout and documentation

- `compiler/`: Gradle subproject, grammar, AST, frontend, semantic analyzer, IR, CLI,
  and `embedlang.backend.arm` target metadata.
- `examples/`: valid `.emb` programs, also checked by the test suite.
- `examples/basic.s`, `examples/blink.s`: generated GNU assembly text, checked
  against backend output by tests.
- `tests/`: Kotlin JUnit 5 frontend, IR, and CLI tests, wired into `:compiler:test`.
- `firmware/`: pinned cLAB source, runtime, GNU firmware builder and ELF verifier.
- `tests/firmware_checks.py`: optional ARM runtime and firmware integration tests.
- [Language specification](LANGUAGE_SPEC.md)
- [Architecture](ARCHITECTURE.md)
- [Requirements and milestone scope](REQUIREMENTS.md)
- [IR design and format](IR.md)
- [Intended ARM target](ARM_TARGET.md)
- [ARM backend](ARM_BACKEND.md)

Build integration follows the [Kotlin Gradle documentation](https://kotlinlang.org/docs/gradle-configure-project.html)
and [Gradle ANTLR plugin documentation](https://docs.gradle.org/8.14.3/userguide/antlr_plugin.html).
ANTLR's Java target supplies the parser; the AST builder, semantic analysis, and CLI are Kotlin.
