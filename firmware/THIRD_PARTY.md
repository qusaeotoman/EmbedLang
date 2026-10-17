# Upstream provenance and licenses

> Public edition: six upstream files are intentionally omitted. Historical
> full-local-snapshot descriptions below do not imply those files are included.
> See [publication exclusions](../PUBLICATION_NOTES.md).

Sources were inspected and copied from these exact Git commits:

| Repository | Revision | Files used |
| --- | --- | --- |
| [SDK_cLAB](https://github.com/lmtspbru/SDK_cLAB/tree/430df587cbb7630efd763579576f5545e31756fb) | `430df587cbb7630efd763579576f5545e31756fb` | `Core/`, GNU Cortex-M4 build dependencies from `Drivers/`, `STM32F407VGTX_RAM.ld`, `.cproject`, `README.md`, `LICENSE` |
| [SDK-1.1M](https://github.com/lmtspbru/SDK-1.1M/tree/bd8cba8f4bd5fc2d1460e6ad4da7b7dd13d9e14d) | `bd8cba8f4bd5fc2d1460e6ad4da7b7dd13d9e14d` | `SDK_EXTI/Core/Inc/main.h`, `SDK_EXTI/Core/Src/gpio.c`; Apache license text from `SDK_LED/Drivers/CMSIS/LICENSE.txt` |

The retained snapshot files in `vendor/` are unmodified. `vendor/manifest.json` records every
snapshot file's SHA-256; the build verifies them. `.gitattributes` prevents Git
newline conversion for these files. The manifest hashes the checked-out bytes
copied from the pinned clones. No private project settings or credentials were copied.

`src/board_main.c` is derived from SDK_cLAB's `Core/Src/main.c`. Its original
copyright notice is retained. The demonstration body between trace start/stop
is replaced with `embed_program_main()`, declared as an external void function.
Its HAL error handler retains the original returning behavior. Diagnostic builds
count calls to that handler before tracing is available, then report the count
and skip generated code if initialization reported an error. All successful-path
initialization is retained. The earlier Milestone 4A fail-stop loop was removed
when aligning integration with the hardware-tested official reference.

`--diagnostic init` creates build-only copies of `stm32f4xx_hal.c`,
`stm32f4xx_hal_rcc.c` and `stm32f4xx_hal_iwdg.c`, inserting RAM-only logging
immediately before failure returns. `#line` preserves original source locations
and all original headers remain in those copies. Calls from the wrapper and
original `iwdg.c` are intercepted through a diagnostic-only forced include.
Vendored source bytes, return statuses and hardware configuration are unchanged.
These generated copies and firmware artifacts are not committed.

The opt-in `--diagnostic probe-recovered` build reuses that instrumentation and
checks the confirmed HAL error at original line 549 against the exact requested
and live clock state. Only the application-level wrapper can normalize this
specific result; the original HAL implementation and raw return evidence remain
unchanged. Later initialization failures still block generated code. The full
policy and test evidence are documented in `docs/CLAB_PLL_RECOVERY.md`.

SDK_cLAB's root license is GPL-3.0 and is reproduced in `vendor/SDK_cLAB/LICENSE`.
The upstream trace/CRC sources are retained under that repository license.
ST-generated sources and HAL/device headers have their own BSD-3-Clause notices;
CMSIS core headers have Apache-2.0 notices. These notices remain intact. The full
Apache license is included in `vendor/APACHE-2.0.txt`, and the BSD terms are in
`BSD-3-Clause.txt`. Respect these licenses when redistributing the combined
firmware, including GPL corresponding-source requirements; this integration does
not relicense the existing Kotlin compiler. The toolchain is separately installed
and its accompanying licenses remain in that installation.

The original example `Core/Src/main.c` is a reference only and is never compiled.
Drivers are limited to the build's explicit source list and headers identified
by GNU GCC dependency inspection. Headers for other CPU cores/toolchains and
unused drivers are omitted. Reference main/configuration files and licenses are
retained as evidence for the documented integration. No SDK-1.1M EXTI handler is installed: the button
mapping is used for polling only.

## Local Flash SDK-1.1M reference files

The separate local build additionally uses four verbatim files from the same
pinned SDK-1.1M revision `bd8cba8f4bd5fc2d1460e6ad4da7b7dd13d9e14d`:

- `SDK_EXTI/STM32F407VGTX_FLASH.ld`
- `SDK_EXTI/Core/Startup/startup_stm32f407vgtx.s`
- `SDK_EXTI/Core/Src/system_stm32f4xx.c`
- `SDK_EXTI/SDK11M.cfg` (reference only; not executed directly).

Original ST BSD-3-Clause notices remain in the first three files; the existing
`BSD-3-Clause.txt` supplies the license text. The four new SHA-256 entries extend
the vendor manifest without changing the previous entries or revisions. The
original cfg has a STM32F427 label; the maintained local configuration uses the
README's common STM32F4/JTAG wiring, explicitly selects FTDI channel 0 and uses
current OpenOCD command spellings. Probe-only overrides suppress automatic
target register writes/reset clock hooks. See `docs/LOCAL_SDK11M.md`.

## Confirmed STM32F427 local module

The local F427 profile adds only the official `Include/stm32f427xx.h`,
`Source/Templates/gcc/startup_stm32f427xx.s` and `License.md` from ST's
`cmsis-device-f4` v2.6.6, commit
`3d7a3c1bae597f1ff36431145a2e34ae82fdeecb`. Headers/startup retain their ST
BSD-3-Clause notices; the repository's Apache-2.0 license is retained verbatim
as well. This fills in the device header selected by the existing CMSIS 2.6.5
family wrapper; its F407 files are not replaced. v2.6.5 is not tagged in the
standalone ST repository, so the adjacent tagged v2.6.6 is pinned explicitly.
Compile tests and actual HAL execution tests cover the combined local profile.

`firmware/local/STM32F427VITX_FLASH.ld` is an attributed adaptation of the pinned
SDK_EXTI Flash linker script, with only target description/capacities changed:
2 MiB Flash and 192 KiB contiguous SRAM. The original ST BSD notice remains.
CCM stays separate. All prior vendor bytes and hashes are unchanged; the three
new ST files extend the manifest from 64 to 67 entries. See `docs/LOCAL_F427.md`.

## Local OLED runtime

At the same pinned SDK-1.1M revision, ten verbatim SDK_OLED files are added:
`Core/Src/oled.c`, `Core/Src/fonts.c`, `Core/Inc/oled.h`, `Core/Inc/fonts.h`,
`Core/Inc/i2c.h`, `Core/Src/i2c.c`, `SDK_OLED.ioc`, and HAL `stm32f4xx_hal_i2c.c`,
`stm32f4xx_hal_i2c.h`, `stm32f4xx_hal_i2c_ex.h`. The `.ioc` and original `i2c.c`
are wiring/configuration evidence; the latter is not compiled. No original main,
UART, IDE metadata or full driver tree is copied. Only the 7x10 font is retained
in the linked image by section garbage collection.

The OLED/font files carry no explicit license notice in this snapshot; their
upstream content and attribution are preserved without assigning them a new
license. Redistribution permission for those portions must not be inferred from
ST notices on separate HAL files. HAL files retain their original ST BSD notices;
the existing BSD license text remains applicable to those components.

One additional verbatim DMA source is copied from the pinned SDK_cLAB revision,
needed by the linked I2C HAL initialization object. All 67 existing hashes remain
unchanged; these eleven files extend the manifest to 78. The OLED component is
HAL 1.7.4, combined with the existing HAL 1.7.10 core/GPIO/RCC; no old component
is replaced. The local adapter's I2C setup follows the executable official
configuration and `.ioc`, resolving the stale PB6/PB7 comments in favor of
PB8/PB9. `oled.c` alone receives a compile-time function-name redirection to
capture HAL transfer failures; its source bytes remain unchanged. See
`docs/LOCAL_OLED.md` for build flags, tests and limitations.
