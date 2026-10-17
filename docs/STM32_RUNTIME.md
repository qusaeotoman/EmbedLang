# STM32 runtime and local firmware build

Milestone 4A adds a firmware layer for SDK-1.1M, STM32F407VGT6, Cortex-M4,
ARMv7E-M Thumb-2. The Kotlin frontend, AST, semantics, IR and assembly emitter
are unchanged. No hardware execution or upload is performed by these scripts.

## Board ABI

Hardware facts come from the pinned [SDK_EXTI main.h](../firmware/vendor/SDK-1.1M/SDK_EXTI/Core/Inc/main.h)
and [cLAB trace.h](../firmware/vendor/SDK_cLAB/Core/Inc/trace.h).
Full revisions, licenses and snapshot checksums are recorded in
[THIRD_PARTY.md](../firmware/THIRD_PARTY.md).

| EmbedLang constant | Runtime value | Physical mapping / meaning |
| --- | --- | --- |
| LED_GREEN | 1 | LED1, PD13, trace LED1 |
| LED_YELLOW | 2 | LED2, PD14, trace LED2 |
| LED_RED | 3 | LED3, PD15, trace LED3 |
| BUTTON_1 | 4 | Standalone BTN, PC15; not key 1 of the matrix keyboard |
| INPUT | 0 | GPIO input, no internal pull |
| OUTPUT | 1 | Push-pull LED output, no pull, high GPIO speed as in cLAB |
| HIGH / LOW | 1 / 0 | Electrical high / low; existing compiler boolean values |

The numbers 1–4 are **opaque runtime handles chosen by EmbedLang**, not MCU
addresses or pin-mask values. The mapping to physical pins comes from the
official sources. Named constants are aligned 32-bit read-only objects named
`embed_const_*`. HIGH/LOW are already immediate bools in generated assembly;
the runtime also exports their data symbols for completeness.

All runtime arguments and results use 32-bit integer ARM ABI values. The
compiler's bool results are canonical 0/1. C is built with the official project's
hard-float flags, but this interface uses only integer registers:

| Function | Behavior |
| --- | --- |
| embed_gpio_mode(pin, mode) | Configure a named LED as input/output; BTN only as input |
| embed_gpio_write(pin, value) | Set a named LED's output latch; nonzero means high; timestamp observed level |
| embed_gpio_read(pin) | Read named LED or BTN electrical level, return 0/1 |
| embed_gpio_toggle(pin) | Toggle a named LED, then timestamp observed level |
| embed_delay_ms(ms) | HAL_Delay, using the official SysTick/HAL tick |
| embed_millis() | HAL_GetTick, uint32 milliseconds since HAL initialization, wraps naturally |

Invalid handles/modes and writes to BTN are ignored; invalid reads return false.
Configure BTN with INPUT before reading. No pull resistor, polarity inversion,
debouncing, keyboard scanning or button interrupts are invented. BTN polling is
an opt-in GPIOC clock/input configuration from the SDK_EXTI mapping; the default
LED-only cLAB peripheral setup stays intact. Do not assume that a high electrical
level means a pressed button without hardware confirmation. Calling write on an
input changes its latch, not its mode, matching HAL behavior.

Only the named pins are exposed; arbitrary numeric values do not address other
peripherals. LED timestamps use SDK_TRACE_Timestamp and the official event IDs.
The wrapper checks available trace space before every event; after capacity is
exhausted GPIO operations continue but additional events are dropped. No writes
are made into the print/dump regions. Tracing is initialized before user code.

## Integration and initialization

`firmware/build.py` invokes the installed Kotlin compiler with `--emit-asm`.
GNU GCC assembles this output; GNU objcopy renames its object symbol `main` to
`embed_program_main` (including relocations). The backend's normal main symbol
and standalone assembly snapshots are unchanged. A single C `main`, derived
from the official cLAB main, calls it in this order:

1. HAL_Init (including SysTick).
2. Official SystemClock_Config: HSE 25 MHz, PLL M=25/N=336/P=2/Q=4, LSI on,
   AHB /1, APB1 /4, APB2 /2, FLASH_LATENCY_5 (168 MHz HCLK).
3. Official MX_GPIO_Init: GPIOH/D/A/B clocks, PD13/14/15 reset, push-pull high speed.
4. Official MX_IWDG_Init: prescaler 64, reload 4095. It is not disabled/refreshed.
5. MX_TRACE_Init, SDK_TRACE_Start.
6. embed_program_main.
7. SDK_TRACE_Stop: CRC finalization and software reset, then fallback infinite loop.

Error_Handler retains the returning behavior of the hardware-tested official
example. Diagnostic builds count initialization errors without accessing trace
before it is initialized; they report the count after trace startup and skip
generated code if it is nonzero. The earlier interrupt-disabled fail-stop loop
was removed. No runtime logging reports a hardware test as passed.

Official startup initializes data/BSS, calls SystemInit, __libc_init_array, main.
The original startup, system file, interrupt handlers, linker script, GPIO,
watchdog, trace and CRC implementations are compiled from the pinned snapshot.
The original C main is excluded. GCC/newlib supplies C-library initialization;
only reachable library sections survive linking. There are no language heap APIs.

The default `--profile clab-reference` uses the successful reference's `-O0`,
`DEBUG`, explicit static link and `-lc/-lm` library group with nano/nosys specs.
`--profile size` uses `-Os` for diagnostic comparison and writes a separate
`*_size` directory. It is experimental until checked on the board. Target,
startup, memory map and watchdog settings are identical between profiles.

## Install dependencies

Use JDK 17 and the checked-in Gradle wrapper as described in README. Install
Python 3.10+ and the **Arm GNU Toolchain 13.3.Rel1, arm-none-eabi** distribution
(GCC 13.3.1), which includes GCC, binutils and newlib/nano specs. Binutils alone
is insufficient. The Arm installation guide is
[here](https://learn.arm.com/install-guides/gcc/arm-gnu/).

Exact portable Windows installation, from the repository root:

```powershell
New-Item -ItemType Directory -Force .tools/arm-gnu | Out-Null
curl.exe -L --fail -o .tools/arm-gnu.zip https://developer.arm.com/-/media/Files/downloads/gnu/13.3.rel1/binrel/arm-gnu-toolchain-13.3.rel1-mingw-w64-i686-arm-none-eabi.zip
tar.exe -xf .tools/arm-gnu.zip -C .tools/arm-gnu
python -m pip install -r firmware/requirements-tests.txt
$armBin = "$PWD/.tools/arm-gnu/arm-gnu-toolchain-13.3.rel1-mingw-w64-i686-arm-none-eabi/bin"
& "$armBin/arm-none-eabi-gcc.exe" --version
```

On Linux, unpack Arm's matching `13.3.rel1-x86_64-arm-none-eabi.tar.xz`
distribution and pass its `bin` directory. Install Python dependencies in a venv
if the system Python is externally managed. `requirements.txt` alone suffices
for builds; `requirements-tests.txt` also installs Unicorn for local tests.

## Build and verify

```powershell
.\gradlew.bat --no-daemon :compiler:test :compiler:installDist
python firmware/build.py examples/remote_blink.emb --toolchain-bin $armBin
python firmware/build.py tests/fixtures/runtime_symbols.emb --toolchain-bin $armBin
python firmware/build.py examples/basic.emb --toolchain-bin $armBin
python tests/firmware_checks.py
python tests/arm_execution.py --assembler "$armBin/arm-none-eabi-as.exe" --linker "$armBin/arm-none-eabi-ld.exe"
```

Tools can instead be on PATH. The builder accepts `--output <directory>`. Each
default output directory is `firmware/build/<source stem>/` and contains
`program.s`, objects, `firmware.elf`, `firmware.bin`, map, disassembly, symbol list,
GCC `.su` stack-usage files and `verification.json`. Build outputs are ignored by
Git. Rebuild `installDist` after any compiler change; the firmware script does
not silently build Gradle or download dependencies. Reproducibility means the
same pinned sources/toolchain/flags; the verification report records source,
assembly and binary hashes. Debug paths can vary between machines.

The verification step rejects unresolved symbols, missing runtime ABI symbols,
incorrect constant values, misplaced vectors, wrong initial SP/reset/SysTick,
allocated sections or load segments outside application RAM, differing load/run
addresses, insufficient linker reservations, and BIN bytes that differ from ELF.
The symbol fixture exercises all six builtins and all named pins/modes through
generated assembly. Runtime ABI symbols are retained even in small programs.

The Python tests execute the actual ARM runtime and finite Blink with mocked
HAL/trace entry points. They check mappings, argument/result ABI, callee-saved
registers, stack alignment, invalid operations, trace capacity, timing calls and
wrapper initialization order. This does not emulate physical LEDs, RCC, SysTick,
watchdog timing or the cLAB loader.

## RAM and stack limits

All allocated sections must lie within `[0x2000D000, 0x20020000)` (76 KiB).
The original script reserves 512 bytes minimum heap and 1024 bytes minimum stack;
SP starts at `0x20020000`. The report checks space for these reservations. No
application section may occupy lower SRAM, CCM trace RAM or Flash.

GCC `.su` files describe individual C function stack use; generated assembly
has no `.su` metadata. The finite Blink test measures its stack under HAL/trace
stubs, not a full hardware worst-case bound. Recursion and arbitrary user call
chains are not statically bounded; the link-time 1 KiB reservation is not a proof
against stack overflow. Review the map, C call chain, interrupt use and generated
assembly before accepting larger programs. See [ITMO_CLAB.md](ITMO_CLAB.md).

## Marked hardware diagnostics

The official reference BIN has now been reported by the user to work through
direct upload. The earlier EmbedLang BIN timed out on the same path. Reproduction
commands, candidate hashes, differences and interpretation of markers are in
[CLAB_DIAGNOSTICS.md](CLAB_DIAGNOSTICS.md). These new candidate images have local
verification only; no automatic upload is part of the diagnostic workflow.

The opt-in `--diagnostic probe-recovered` mode handles only the confirmed
already-active matching-PLL false error in the pinned HAL. It validates the
failure return site, decoded configuration, oscillator readiness and later
initialization state before allowing a generated function call. It requires
the clab-reference build profile and leaves all previous modes/artifacts intact.
See [CLAB_PLL_RECOVERY.md](CLAB_PLL_RECOVERY.md) for the complete fail-closed policy.

The user subsequently confirmed that this exact recovered probe executed on the
physical STM32F407 and returned 42. See [hardware evidence and timestamp
units](HARDWARE_VALIDATION.md). A separate subsequent physical Blink test also
passed, with five pulses and successful completion markers, as recorded there.

To reproduce the verified finite demonstration, use `--diagnostic blink-recovered` with
`examples/remote_blink.emb`. It reuses the identical recovery and initialization
gates, executes the generated main, traces PD13/LED1 changes and completes after
2.75 seconds of programmed delays plus overhead. See [build, verification and
manual acceptance](CLAB_BLINK.md). Physical Blink success is user-confirmed;
reported timestamp units and conditional durations are documented separately.
