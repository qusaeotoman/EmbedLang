# Local F427 OLED demonstration

> Public edition: six upstream files are intentionally omitted. Historical
> full-local-snapshot descriptions below do not imply those files are included.
> See [publication exclusions](../PUBLICATION_NOTES.md).

Prepared and programmed with explicit user approval on 2026-10-15.
**Physical success reported 2026-10-17 (Europe/Moscow): the user confirmed
that THE BEST GROUP appears clearly on the built-in OLED.** The completed Blink commit remains
`5a5fbd608614d5a1d86e004630728025771beb15`. Its hardware-tested BIN and the
cLAB reference/probe/Blink images are preserved unchanged.

## Official hardware reference

Inspected the actual files in the official
[SDK_OLED example](https://github.com/lmtspbru/SDK-1.1M/tree/bd8cba8f4bd5fc2d1460e6ad4da7b7dd13d9e14d/SDK_OLED),
at SDK-1.1M commit `bd8cba8f4bd5fc2d1460e6ad4da7b7dd13d9e14d`:

| Evidence | Finding |
| --- | --- |
| Repository README | Winstar WEO012864DL graphical OLED |
| `Core/Inc/oled.h` | 128×64, HAL I2C address 0x78 |
| `Core/Src/oled.c` | SSD1306-family initialization commands; eight 128-byte pages; 1,024-byte framebuffer |
| `Core/Src/i2c.c` executable setup | I2C1, PB8/SCL + PB9/SDA, AF4, open drain, pullups, very high GPIO speed, 400 kHz, 7-bit addressing |
| `SDK_OLED.ioc` | PB8=I2C1_SCL, PB9=I2C1_SDA, corroborating executable code |
| `Core/Src/fonts.c`, `Core/Inc/fonts.h` | Official 7×10 font; also larger fonts not needed here |

The PB6/PB7 comments in `i2c.c` contradict its executable pin masks and `.ioc`.
The integration follows **PB8/PB9**, not those comments. 0x78 is HAL's shifted
write address, corresponding to **7-bit address 0x3C**, not address 0x78 on the
7-bit bus. Commands use control byte 0x00; display data uses 0x40.

[Winstar's WEO012864D product listing](https://www.winstar.com.tw/products/finder/page%3A13.html?sort=customfield_22)
identifies the controller family as SSD1306. This agrees with the official
driver's command sequence; the exact controller silicon revision on the user's
module has not been physically read. No SH1106 offset or alternate pin mapping
is assumed.

The confirmed STM32F427VIT6 supports I2C1 and GPIO AF4 on these pins, as used by
the common SDK board. The F427 device definitions, startup and Flash layout are
the previously verified local profile. The OLED example's unrelated UART, PA8
MCO and HSI-based 120 MHz system-clock setup are not copied. The local wrapper
retains its hardware-tested **25 MHz HSE / 168 MHz system clock**, APB1=42 MHz;
HAL derives the 400 kHz I2C timing from that actual peripheral clock. Synthetic
tests check CR2 frequency=42 and fast-mode CCR=35/duty 2. Electrical operation,
ACKs and pullup margins are not independently measured. The user subsequently
confirmed successful text display on this physical board; see the hardware record.

## Additive runtime API

Only the compiler's existing built-in signature table is extended. Grammar,
AST, semantic analysis algorithm, IR and ARM backend are unchanged. These names
are reserved built-ins and lower through the existing typed external-call ABI:

| Function | Signature | Meaning |
| --- | --- | --- |
| `oled_init` | `() -> bool` | Configure I2C1, initialize the panel and transmit a blank frame |
| `oled_clear` | `() -> void` | Clear the framebuffer and reset cursor to (0,0); no transfer |
| `oled_cursor` | `(x: u32, y: u32) -> bool` | Set pixel cursor; reject x≥121 or y≥54 |
| `oled_write_char` | `(ascii: u32) -> bool` | Render one printable ASCII code, 32–126, white 7×10 font; advance 7 pixels |
| `oled_update` | `() -> bool` | Transfer the eight framebuffer pages |

The cursor and glyph boundaries match the original driver's strict edge
check: a glyph whose right/bottom edge equals 128/64 is rejected. There is no
wrapping or scrolling. Cursor/character rejection returns false without sending
traffic. Rendering requires successful initialization. Clear is a no-op before
initialization; the bool operations return false. `oled_init` starts a fresh
initialization attempt; it does not retry automatically.

This is a **local F427 runtime extension**. Ordinary Blink and cLAB builds do
not link it; calling these names requires the opt-in `--oled` build. Unsupported
runtime calls fail at link time. Strings, pointers, allocation and Unicode remain
excluded. Existing `u32` ASCII codes suffice for this demonstration, so no string
literal or new type is necessary.

`examples/oled_group.emb` supplies all fourteen characters of **THE BEST GROUP**.
Its compiled code initializes, clears, selects (15,27), writes each code and
updates only if every operation succeeded. Fourteen 7-pixel glyphs occupy 98
pixels, centered horizontally. The C adapter contains no application message
or handwritten text-output loop. The unchanged local startup wrapper calls
`embed_program_main`, freezes local trace and idles on return without resetting;
the panel is left displaying its last transmitted frame.

## Driver and error handling

The official OLED/font source bytes are retained verbatim, with manifest hashes.
Only `oled.c` is compiled with
`-DHAL_I2C_Mem_Write=embed_oled_mem_write`. That wrapper calls the actual HAL
routine and captures the first failure; it does not change the panel commands.
The original driver ignores HAL status codes, so its unconditional success
return alone would be insufficient. Further bus transfers are suppressed after
the first error, initialization/update return false, and diagnostics retain:

| Symbol | Meaning |
| --- | --- |
| `embed_oled_status` | 0 before init, 1 initialized, 2 last update successful; 0x80000001 I2C init failed, 0x80000002 transfer failed |
| `embed_oled_hal_status` | First raw HAL error/busy/timeout status |
| `embed_oled_hal_error` | I2C handle's ErrorCode at that failure |
| `local_blink_status` / `local_hal_error` | Existing wrapper completion and system-clock status; completion=2 alone does not establish OLED success |

The official 100 ms startup wait and 10 ms command / 25 ms page timeouts remain.
All I2C is blocking; no I2C interrupts, DMA transfers, UART or watchdog are
started. DMA support is linked only because the original HAL I2C initialization
object references its DMA-abort support. The local profile enables
HAL_I2C_MODULE_ENABLED by compiler flag; the cLAB HAL configuration is not edited.

The OLED HAL I2C component comes from SDK_OLED's HAL 1.7.4 snapshot, alongside the
existing core/GPIO/RCC HAL 1.7.10. Only the needed I2C headers/source are added;
existing HAL bytes are preserved. Compilation, real HAL I2C initialization under
synthetic MMIO and the transfer-boundary tests pass, but these checks do not
replace physical validation of this combination. Provenance/licenses are in
[THIRD_PARTY.md](../firmware/THIRD_PARTY.md); 78 vendor hashes are checked.

## Build and inspect

From the repository root with JDK 17, the existing ARM GNU 13.3.Rel1 toolchain,
Python and `firmware/requirements-tests.txt` dependencies:

```powershell
$env:JAVA_HOME = (Get-ChildItem .tools/jdk -Directory | Select-Object -First 1).FullName
$env:GRADLE_USER_HOME = Join-Path (Get-Location) '.tools/gradle-user-home'
$env:PYTHONPATH = (Resolve-Path .tools/python-deps).Path
.\gradlew.bat --no-daemon :compiler:test :compiler:installDist
$armBin = '.tools/arm-gnu/arm-gnu-toolchain-13.3.rel1-mingw-w64-i686-arm-none-eabi/bin'
python firmware/build_local.py examples/oled_group.emb --mcu stm32f427vit6 --oled --toolchain-bin $armBin
python tests/local_oled_checks.py -v
```

Separate ignored output: `firmware/build/local_oled_f427/firmware.elf` and
`firmware.bin`, with generated assembly, map, symbols, disassembly and verification
report. No build/test command connects to or programs the board.

Prepared BIN: **13,576 bytes**, SHA-256
`a76fd04e15b0d6e2e7d5726d93433f6a677501e8f198883f5c4b77564d5a0c8c`.
Vectors at 0x08000000 (428 bytes), initial SP=0x20030000,
Thumb reset=0x080005DD. Flash load image ends at 0x08003508, within sector 0
[0x08000000,0x08004000). Main SRAM data=28 bytes, BSS=1,176 bytes,
BSS end=0x200004B4. Heap/stack reservations remain 512/1,024 bytes; CCM trace
layout remains unchanged. No unresolved symbols. Existing upstream unused-
parameter, GNU-stack and RWX linker warnings remain visible.

The seven OLED integration tests check compiler provenance, exact emitted
character sequence and pixel frame, original panel initialization sequence,
actual HAL I2C timing/GPIO setup, failure propagation/traffic suppression,
ASCII/cursor limits and preserved Blink images. Emulated stack high-water is
280 bytes, not a physical interrupt worst-case bound.

Complete verification on 2026-10-15: **160 checks passed, zero failures**:

| Suite | Passed |
| --- | ---: |
| Compiler JUnit (76 previous + 6 OLED) | 82 |
| ARM execution | 15 |
| Existing runtime/cLAB diagnostic/recovery/Blink | 43 |
| Existing local F407 / F427 | 8 / 5 |
| New local OLED integration | 7 |

All original 147 checks remain passing. The build executed successfully using
ARM GNU 13.3.Rel1. ELF/BIN verification passed, and all 78 vendor hashes matched;
the prior 67 manifest entries were unchanged. Hardware-tested local F427 Blink,
cLAB recovered Blink and recovered probe BIN hashes matched their preserved
values. Logs and generated firmware remain ignored. No hardware access was
performed for these tests.

## Manual programming boundary

OLED display success is now user-confirmed. No board access occurred during preparation;
the later programming operation was separately approved, as recorded below.
Future programming requires the user's separate approval and should reconfirm the
F427 identity/options, preserve a fresh readback of the currently installed firmware,
verify the BIN hash/layout, erase only sector 0, write at 0x08000000, verify both
the image and unchanged unrelated sectors/options, then reset/run. The completed OLED deployment replaced
Blink in sector 0; its committed sources and preserved image remain available.
Physical XP3/BOOT0 is still unconfirmed; the earlier successful Blink boot is
evidence of that run, not a measurement of the jumper state.

The user confirmed **THE BEST GROUP** appears clearly. The program requests a
single centered row and leaves the last frame displayed; no calibrated position
or duration measurement was supplied. If the screen stays blank, inspect OLED status/HAL error and actual
I2C acknowledgment before changing pins, controller initialization or clocks.
Do not alter jumpers, option bytes or drivers as an automatic troubleshooting
step. OLED support is not yet available in the remote ITMO.cLAB image.

## Approved programming result, 2026-10-15

OpenOCD reconfirmed DBGMCU_IDCODE=0x20016419, 2 MiB Flash and a 16 KiB first
sector. A fresh 2,097,152-byte Flash backup was read and verified against the
board, then compared byte-for-byte with the previous post-Blink full readback.
Its SHA-256 is
`1901c433d89a54f01a94699c5cee747c3b4e4d8075e803bd49264f6a7ab94ec5`.
The original 7,304-byte Blink image also matched its bytes at the Flash base.

Immediately before erasing, that full backup was verified against Flash again.
The approved operation explicitly erased only `flash erase_sector 0 0 0`, wrote
the 13,576-byte OLED BIN at 0x08000000, verified the complete sector including
erased 0xFF padding, and verified all **2,080,768 unrelated Flash bytes** against
the fresh backup. FLASH_OPTCR=0x0FFFAAED and FLASH_OPTCR1=0x0FFF0000 were unchanged.
No option-byte programming, mass erase, driver or jumper change was performed.
OpenOCD completed `reset run` and exited 0 with no Error messages.

The initial halt reported the previously observed unknown-state warning while
the prior Blink application was idle; stable identification, backup verification
and the subsequent reset/halt succeeded. The backup-only connection also warned
that no RAM working area was available for its checksum helper; verification
completed successfully. Neither warning was a programming failure.

Backup, verified image copy, scripts, logs and result JSON remain ignored in
`.tools/oled-deployment-20261015-201707/`. Successful programming is distinct
from the subsequent user-confirmed display result recorded below.


## Confirmed physical display result

**Report recorded 2026-10-17 (Europe/Moscow, UTC+03:00).** The user physically
confirmed that **THE BEST GROUP appears clearly** on the built-in OLED of the
local SDK-1.1M board with the previously confirmed STM32F427VIT6 marking. The
separate programming operation took place on 2026-10-15; the exact wall-clock
time of the user's visual observation was not supplied. The date above is the
confirmation/report date, not an inferred instrument timestamp.

The reported result concerns the 13,576-byte `local_oled_f427/firmware.bin`
identified by the SHA-256 above and the actual compiled
`examples/oled_group.emb` program. This establishes physical operation of the
compiled scalar OLED calls, board initialization and official panel/font path
for this demonstration. No photo, logic-analyzer capture, raw I2C trace or
measured display timing was supplied. It does not establish electrical margins,
all-character rendering or fault behavior beyond the separate local tests.
See [the consolidated hardware validation record](HARDWARE_VALIDATION.md#local-stm32f427vit6-oled-confirmed-physical-text-display).

No OpenOCD connection, reset, firmware programming, driver or option-byte change
was made while documenting this result and preparing the preservation commit.


### Preservation verification, 2026-10-17

The full suite was rerun after the physical success report: **160 checks passed**,
zero failures (82 compiler, 15 ARM execution, 43 existing firmware/cLAB, 8 local
F407, 5 local F427, 7 OLED integration). ELF/BIN, vendor integrity and preserved
Blink checks passed. The OLED image and integration-source hashes remained
unchanged. No source changes were required during this preservation step;
only documentation was finalized. The completed source, tests, vendor snapshot
and hardware record are preserved in Git; binaries, backups and programming
logs remain ignored. See the consolidated hardware record for the dated result.
