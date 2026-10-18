# EmbedLang

**A small, statically typed language for embedded systems, built with Kotlin and ANTLR4.**

**Public source edition:** includes the compiler, VS Code and Zed source,
DWARF/GDB debugging tools, tests and Russian report templates. See
[publication notes](PUBLICATION_NOTES.md) for this edition's verified tests,
dependencies and licensing exclusions. OLED driver/font files, generated
firmware/WASM/VSIX files, private fixtures and machine configuration are excluded.
The public update passed **253 applicable checks** with zero failures; one
optional reference comparison was skipped. See the notes for the three historical
preservation exclusions and seven unavailable OLED firmware checks.

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
Source → ANTLR parse tree → AST → semantic analysis → typed IR → ARM assembly
                                                             ↓
                             startup + runtime + linker → ELF → BIN
```

This is an educational compiler with a deliberately small scope. Strings,
floating point, pointers, heap allocation, classes, modules and threads are not
implemented. OLED text uses printable ASCII character codes. Local VS Code
GDB source debugging and a separate Zed editing prototype are available;
Zed 1.24.2 local source debugging has now been exercised in the real Windows
editor, using Eclipse CDT, ARM GDB and a localhost Unicorn target.

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
toolchain's `bin` directory, then build the local F427 OLED demonstration:

```powershell
python -m pip install -r firmware/requirements-tests.txt
python firmware/build_local.py examples/oled_group.emb --mcu stm32f427vit6 --oled --toolchain-bin $armBin
python tests/local_oled_checks.py -v
```

The builder uses the installed compiler distribution from the preceding step.
ELF/BIN output is under `firmware/build/local_oled_f427/`. Existing Blink and
cLAB profiles use separate outputs. Build/test commands do not upload firmware.

| Target | Firmware layout | Guide |
| --- | --- | --- |
| Local STM32F427VIT6 SDK-1.1M | Flash at 0x08000000; 2 MiB Flash, 192 KiB main SRAM + 64 KiB CCM | [Local F427](docs/LOCAL_F427.md) |
| Local F427 OLED | Same Flash profile, I2C1 PB8/PB9, 128×64 panel | [OLED runtime and validation](docs/LOCAL_OLED.md) |
| ITMO.cLAB STM32F407 | Official SRAM loader layout; separate runtime and trace lifecycle | [ITMO.cLAB](docs/ITMO_CLAB.md) |

The latest local regression passed **264 checks**: the original 160 (82 compiler,
15 ARM execution, 43 cLAB/runtime, 13 local Flash and 7 OLED), 37 VS Code checks,
24 Zed parser/task checks, 8 GDB/RSP checks, 7 new compiler/CLI source-mapping checks
and 5 source-debug integration checks, plus 3 local-debug unit checks, 1 interactive
RSP check and 8 actual VS Code/Cortex-Debug scenarios, then 7 Zed DAP/configuration,
2 Rust and 2 component-WASM checks. Actual Zed 1.24.2 UI observations are recorded
separately from automated tests; see the
[verification journal](docs/report/VERIFICATION.md). Optional emulation
suites require their corresponding built images; historical preservation tests
also require local reference fixtures, which are not distributed with the
repository. These counts describe the recorded validation, not an automated
GitHub CI result. See the [development guide](docs/DEVELOPMENT_GUIDE.md) and
[STM32 runtime guide](docs/STM32_RUNTIME.md) for the full setup and individual suites.

## Documentation

### Milestone 6: local VS Code extension and living report

[`extensions/vscode`](extensions/vscode/) provides `.emb` recognition, TextMate
highlighting, language configuration, source-located Problems and commands to
validate or emit typed IR / ARM assembly through the existing CLI. Build the
compiler distribution first; no STM32 hardware is required. See the
[extension setup, tests and local VSIX instructions](extensions/vscode/README.md).
The extension is not published to the Marketplace, and these milestone changes
have not been pushed to GitHub.

The [incremental Russian report](docs/report/REPORT.md) leaves the title page,
technical requirements, architectural explanation and real AI-prompt history for
personal student authorship. Verified source-based supporting material is in
[technical appendices](docs/report/APPENDICES.md); actual local test results are
recorded in the [verification journal](docs/report/VERIFICATION.md). The official
ITMO assignment is now identified; the [source-based requirements matrix](docs/report/ASSIGNMENT_MAPPING.md)
distinguishes implemented features from outstanding editor acceptance and GDB/TCP-IP work.
Update the report after each subsequent milestone using its
[maintenance rules](docs/report/README.md).

### Local Zed support

[`extensions/zed`](extensions/zed/README.md) provides an editor-only Tree-sitter
grammar, `.emb` configuration, highlighting, bracket/indent and outline queries.
The repository's [Zed tasks](.zed/tasks.json) build the compiler, validate saved
files and emit IR/ARM assembly using the existing CLI. Diagnostics retain source
locations in the terminal; there is no Zed Problems/LSP integration yet.

See the guide for reproducible grammar compilation, local unpacked installation
and its limitations. Zed 1.24.2 displayed highlighting and matched braces, and
successfully ran Validate in an isolated profile. No
board or publication was involved. The editor/report work was preserved locally
as `40fa242`; subsequent GDB investigation is described below.

### Milestone 7: local GDB/TCP connection proof

An isolated [Unicorn RSP target](tools/debug/unicorn_rsp.py) executes actual
compiler-generated ARM code over loopback TCP with ARM GDB. Verified: symbol
breakpoint, instruction step, registers/stack memory and arithmetic result 42.
The [investigation and reproduction guide](docs/GDB_DEBUGGING.md) records ELF
symbols/DWARF findings and the plan for VS Code/Zed adapters. Existing firmware
and runtime behavior remain unchanged. The subsequent optional mode
`embedlang --emit-asm --debug-lines program.emb` adds actual `.emb` line mappings.
[Source-debug tests](docs/SOURCE_DEBUGGING.md) demonstrate a file/line breakpoint
and GDB `step` through lines 2–6 with result 42 over localhost TCP. Typed locals,
comprehensive unwinding and physical debugging are **not** demonstrated.
Default assembly output remains unchanged. Source mapping is preserved locally
as `87807cefcb7eb96445ab79cb8f5c162a53ef5681`.

### VS Code: local source debugging

The [local debugging guide](docs/VSCODE_DEBUGGING.md) describes the optional
Cortex-Debug → ARM GDB/MI2 → localhost Unicorn workflow. Actual VS Code tests
verified `.emb` breakpoints, source Step Into, Continue/Pause, a useful top frame,
registers/disassembly and result 42. The command builds a pure CPU ELF, not STM32
firmware. Typed locals and complete unwinding remain incomplete.
This VS Code milestone is preserved as `b4bd308d56685035d35267241c5fbc2fb41aba33`
and has not been published.

### Zed: local source debugging

The separate [Zed debugger guide](docs/ZED_DEBUGGING.md) provides installation,
machine-local debug configuration and the exact manual acceptance checklist.
Rust/WASI compilation against official Zed API 0.7.0 succeeded. Actual standalone
CDT 1.10.0/GDB/TCP tests verified `.emb` breakpoints, stepping, Pause/resume,
registers/disassembly and result 42. Following approved installation, actual
**Zed 1.24.2** testing confirmed both extensions load, `.emb:2` breakpoint,
source steps 3–6, Continue/Pause/resume, registers, useful stack entries,
result 42 and cleanup. Instruction inspection worked through the GDB console;
a dedicated disassembly pane was not demonstrated. UI testing found and fixed
the extension package target: **wasm32-wasip2** components are required by this
Zed version. The earlier build/protocol milestone remains preserved as `cca8b36`;
the packaging fix and actual UI verification are preserved in the subsequent
local Zed UI milestone. This public source update exports those verified changes
without publishing the original local Git history. Compile extensions locally;
no binary extension release is bundled.

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
CMSIS Apache-2.0 material and GPL-3.0 cLAB components. Some upstream OLED/font
files have no explicit license notice in the inspected snapshot; that status is
recorded in [THIRD_PARTY.md](firmware/THIRD_PARTY.md).

No project-wide license has been selected for the original EmbedLang code.
Do not assume that all files share one license or replace upstream notices when
sharing the project. Repository visibility alone does not assign reuse terms.
