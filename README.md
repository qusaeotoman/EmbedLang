# EmbedLang

**A small, statically typed language for embedded systems, built with Kotlin and ANTLR4.**

EmbedLang is a university Embedded Systems Programming project that takes a
program from source through type checking and typed intermediate representation
to GNU ARM Thumb-2 assembly. A separate firmware layer links generated code with
STM32 startup, HAL and board runtime support.

The project has executed generated code on physical SDK-1.1M hardware:

- **ITMO.cLAB / STM32F407:** a generated arithmetic probe returned 42, followed by
  a successful finite Blink demonstration.
- **Local SDK-1.1M / STM32F427VIT6:** five green LED pulses followed by OFF.
- **Local F427 OLED:** the user confirmed that **THE BEST GROUP** appears clearly
  on the built-in display; confirmation recorded on **2026-10-17**.

See [hardware validation](docs/HARDWARE_VALIDATION.md) for the observations,
firmware hashes, dates and limits of these results. Local emulation and physical
hardware evidence are recorded separately.

> **Public source edition:** six upstream files without confirmed redistribution
> permission are excluded. Compiler, cLAB and local Blink sources are included;
> rebuilding the historical OLED demonstration requires separately permitted
> OLED driver/font files. See [publication notes](PUBLICATION_NOTES.md).

## Features

- Kotlin frontend with an ANTLR4 lexer/parser, source-located diagnostics and a
  sealed-interface AST.
- Static types: `i32`, `u32`, `u8`, `bool` and `void`.
- Variables, assignments, arithmetic, comparisons, short-circuit boolean
  expressions, functions, calls, returns, `if`/`else` and `while`.
- Typed IR, readable IR output and GNU Thumb-2 assembly emission for Cortex-M4.
- Runtime APIs for GPIO, delays and time; an opt-in local F427 OLED text API.
- Separate local Flash and ITMO.cLAB SRAM firmware build profiles with ELF/BIN
  verification and pinned, checksummed upstream sources.

```text
Source в†’ ANTLR parse tree в†’ AST в†’ semantic analysis в†’ typed IR в†’ ARM assembly
                                                             в†“
                             startup + runtime + linker в†’ ELF в†’ BIN
```

This is an educational compiler with a deliberately small scope. Strings,
floating point, pointers, heap allocation, classes, modules and threads are not
implemented. OLED text uses printable ASCII character codes. GDB and editor
integrations remain future milestones.

## Example

```text
fn add(a: i32, b: i32) -> i32 {
    return a + b
}

fn main() -> void {
    gpio_mode(LED_GREEN, OUTPUT)
    let count: u32 = 0
    while count < 10 {
        gpio_toggle(LED_GREEN)
        delay_ms(250)
        count = count + 1
    }
    gpio_write(LED_GREEN, LOW)
}
```

Programs require `fn main() -> void`. Variables have explicit types and initial
values. A newline or semicolon ends a simple statement. See the
[language specification](docs/LANGUAGE_SPEC.md), [examples](examples/), and the
[actual OLED program](examples/oled_group.emb).

## Build, test and run

Requirements: **JDK 17** with `JAVA_HOME` configured. The checked-in Gradle wrapper
handles Gradle installation; first use requires access to Maven dependencies.
Pinned versions: Kotlin 2.2.21, ANTLR4 4.13.2 and Gradle 8.14.3.

From the repository root on Windows PowerShell:

```powershell
.\gradlew.bat build
.\gradlew.bat :compiler:test
.\gradlew.bat :compiler:installDist
.\compiler\build\install\embedlang\bin\embedlang.bat examples\basic.emb
.\compiler\build\install\embedlang\bin\embedlang.bat --emit-ir examples\basic.emb
.\compiler\build\install\embedlang\bin\embedlang.bat --emit-asm examples\blink.emb
```

On Linux/macOS:

```sh
sh ./gradlew build
sh ./gradlew :compiler:test :compiler:installDist
./compiler/build/install/embedlang/bin/embedlang examples/basic.emb
./compiler/build/install/embedlang/bin/embedlang --emit-ir examples/basic.emb
./compiler/build/install/embedlang/bin/embedlang --emit-asm examples/blink.emb
```

The compiler validates input and optionally prints IR or assembly; invoking it
never flashes a board. Generated parser code, distributions and reports stay in
ignored build directories. The portable compiler suite contains **82 JUnit tests**.

## STM32 firmware

Firmware builds additionally require ARM GNU Toolchain 13.3.Rel1, Python 3.10+
and the packages in `firmware/requirements-tests.txt`. Set `$armBin` to your ARM
toolchain's `bin` directory, then build the local F427 Blink demonstration:

```powershell
python -m pip install -r firmware/requirements-tests.txt
python firmware/build_local.py examples/remote_blink.emb --mcu stm32f427vit6 --toolchain-bin $armBin
```

The builder uses the installed compiler distribution from the preceding step.
ELF/BIN output is under `firmware/build/local_blink_f427/`. OLED and
cLAB profiles use separate outputs. The public OLED build is unavailable until
the excluded driver/font files have been supplied with appropriate permission. Build/test commands do not upload firmware.

| Target | Firmware layout | Guide |
| --- | --- | --- |
| Local STM32F427VIT6 SDK-1.1M | Flash at 0x08000000; 2 MiB Flash, 192 KiB main SRAM + 64 KiB CCM | [Local F427](docs/LOCAL_F427.md) |
| Local F427 OLED | Same Flash profile, I2C1 PB8/PB9, 128Г—64 panel | [OLED runtime and validation](docs/LOCAL_OLED.md) |
| ITMO.cLAB STM32F407 | Official SRAM loader layout; separate runtime and trace lifecycle | [ITMO.cLAB](docs/ITMO_CLAB.md) |

The last complete local verification passed **160 checks**: 82 compiler, 15 ARM
execution, 43 cLAB/runtime, 13 local Flash and 7 OLED checks. Optional emulation
suites require their corresponding built images; historical preservation tests
also require local reference fixtures, which are not distributed with the
repository. These counts describe the recorded validation, not an automated
GitHub CI result. See the [development guide](docs/DEVELOPMENT_GUIDE.md) and
[STM32 runtime guide](docs/STM32_RUNTIME.md) for the full setup and individual suites.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [requirements](docs/REQUIREMENTS.md)
- [Language specification](docs/LANGUAGE_SPEC.md) and [IR format](docs/IR.md)
- [ARM backend](docs/ARM_BACKEND.md)
- [Hardware validation](docs/HARDWARE_VALIDATION.md)
- [Detailed development and milestone build guide](docs/DEVELOPMENT_GUIDE.md)
- [Third-party provenance and licenses](firmware/THIRD_PARTY.md)
- [Publication preparation and exclusions](docs/PUBLISHING.md)

`compiler/` contains the Kotlin/ANTLR compiler, `examples/` contains programs,
`tests/` contains compiler and integration tests, and `firmware/` contains the
board runtime, builders, verifier and required upstream snapshots.

## Licensing and attribution

Third-party components retain their original notices, including ST BSD notices,
CMSIS Apache-2.0 material and GPL-3.0 cLAB components. Upstream OLED/font
files and two board/project reference files without confirmed redistribution
permission are excluded; see [publication notes](PUBLICATION_NOTES.md) and
[THIRD_PARTY.md](firmware/THIRD_PARTY.md).

No project-wide license has been selected for the original EmbedLang code.
Do not assume that all files share one license or replace upstream notices when
sharing the project. Repository visibility alone does not assign reuse terms.
