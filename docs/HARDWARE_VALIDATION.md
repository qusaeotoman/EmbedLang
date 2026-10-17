# Physical hardware validation

## Recovered generated probe: confirmed by manual ITMO.cLAB test

The user reported successful direct upload and execution on the physical
SDK-1.1M STM32F407 of the following locally built artifact:

- `firmware/build/diagnostic_probe_recovered/firmware.bin`
- Size: 16,164 bytes.
- SHA-256: `fb5ec379f307a3e29477563233df78548e5de0bb16153883611e8b98142f3ea6`.

Reported PRINT trace, in order:

```text
PLL_MATCH_RECOVERED
BEFORE_GENERATED
PROBE_RESULT=42
AFTER_GENERATED
TRACE_COMPLETE
```

This establishes physical execution of the compiler-generated ARM function
`diagnostic_probe(6, 7)`, which computes multiplication and returns 42. It also
confirms that the narrow active-PLL recovery allowed execution and reached the
completion marker. The report comes from the user's manual hardware test;
the development agent did not upload firmware. No raw trace attachment or
timing measurements were supplied for that probe. Blink was tested separately,
as recorded below.

The earlier pristine official reference also ran successfully according to the
user. Preserve both reference and probe artifacts when building new candidates.
See [recovery checks and limitations](CLAB_PLL_RECOVERY.md).

## Finite recovered Blink: confirmed by manual ITMO.cLAB test

**Test report recorded: 2026-10-15 (Europe/Moscow, UTC+03:00).** The user reported
the test as just completed; a separate run wall-clock timestamp was not supplied.
This date records the reported physical test, not an independently obtained
laboratory execution log timestamp.

The user confirmed successful execution of EmbedLang-generated finite Blink on
the real SDK-1.1M STM32F407 through ITMO.cLAB. The prepared image is:

- `firmware/build/diagnostic_blink_recovered/firmware.bin`
- Size: 16,184 bytes.
- Local SHA-256: `cc1875ee45bd5eed052b75dfbd8c98bc5b8f55f23fb6690e6bb1d964fd4c3fb5`.
- Source: `examples/remote_blink.emb`; mode: `--diagnostic blink-recovered`.

The local artifact's identity is preserved here; no independent server-side
uploaded-file checksum was supplied. The user-provided trace excerpt is
preserved verbatim in [the trace record](hardware/2026-10-15-blink-trace.txt):

```text
INIT_ERRORS=0
PLL_MATCH_RECOVERED
BEFORE_GENERATED at 1.942
AFTER_GENERATED at 2511.801
TRACE_COMPLETE at 2762.795
```

The user also reported five LED pulses in the laboratory waveform, consistent
with the generated program's ten alternating state transitions. This confirms
physical execution of the generated finite Blink path and reaching its exit
and completion markers. Green LED1 uses the verified PD13 mapping. The waveform
observation is the user's report; no waveform image, complete trace export,
individual edge timestamps or additional measurements were supplied. The agent
did not upload firmware or access the laboratory.

### Meaning of the recovered initialization error

INIT_ERRORS=0 does not mean the raw oscillator call never returned an error.
The earlier hardware investigation identified HAL_RCC_OscConfig's HAL_ERROR at
the pinned `stm32f4xx_hal_rcc.c:549` comparison of encoded PLL fields with decoded
request parameters. PLL_MATCH_RECOVERED means the guarded firmware shim accepted
only that confirmed false error after matching its source/line, enabled/ready
PLL and HSE, active PLL SYSCLK, requested source and M/N/P/Q parameters, unchanged
PLL register and required oscillator states. It retains the raw HAL_ERROR while
returning effective HAL_OK to the original initialization caller.

The final gate checks the complete initialization sequence and live clock,
SysTick/global interrupt mask, flash/voltage and watchdog settings before
generated execution. Other oscillator, clock and watchdog failures still deny
the application. Thus the initial HAL_ERROR was safely recovered in this tested
handoff condition; it was not globally ignored. See
[the exact checks](CLAB_PLL_RECOVERY.md).

### Observed numbers versus timing interpretation

The displayed timestamp differences are directly calculable in **display
units**, without assuming their scale:

| Interval | Difference in display units |
| --- | ---: |
| BEFORE_GENERATED to AFTER_GENERATED | 2509.859 |
| AFTER_GENERATED to TRACE_COMPLETE | 250.994 |
| BEFORE_GENERATED to TRACE_COMPLETE | 2760.853 |

If the Web IDE displays milliseconds, these correspond to 2.509859 s,
0.250994 s and 2.760853 s respectively. They closely match ten programmed 250 ms
delays plus the wrapper's final 250 ms delay, with overhead. This supports an
**inference that these displayed units are milliseconds**; the renderer's
conversion and the raw exported timestamps have not been independently checked.
Do not present these conditional conversions as independently calibrated timing
measurements. The raw firmware format itself uses microseconds, as established
from the official source below. No individual pulse-width measurement is claimed.

Local tests separately execute generated ARM, HAL initialization, recovery
guards, GPIO/delay hooks and trace finalization under synthetic MMIO. They check
the expected twelve LED state records (initial/final LOW included), ten toggles,
watchdog configuration, negative recovery cases, CRC/reset and memory bounds.
Those local checks do not measure hardware timing. Conversely, this physical
Blink success is new evidence beyond emulation; it does not validate arbitrary
programs, worst-case interrupt stack use, clock accuracy or watchdog expiry.
See [Blink build and verification](CLAB_BLINK.md).

### Local verification rerun before preservation

On 2026-10-15, all **134 checks passed again**: 76 compiler JUnit tests, 15 ARM
execution checks, 13 runtime/firmware tests, 6 marked-diagnostic tests,
6 initialization tests, 12 PLL recovery tests and 6 recovered Blink tests.
The compiler distribution was rebuilt; firmware tests rechecked ELF/BIN bytes,
symbols, vectors and application RAM bounds. The successful Blink and probe
BINs were preserved unchanged, rather than overwritten by a rebuild. All 60
vendored source hashes remained intact. These are local regression results,
separate from the physical hardware evidence above.

## Local STM32F427VIT6: programmed and physically observed Blink

**Recorded 2026-10-15 (Europe/Moscow).** This is the user's local SDK-1.1M board,
physically marked STM32F427VIT6, separate from the remote cLAB F407 board.
The user explicitly authorized programming despite unconfirmed physical
XP3/BOOT0 configuration. No jumper, option-byte or USB-driver changes were made
during this deployment. The user explicitly confirmed **five green LED pulses
followed by the LED staying off**, and reconfirmed this observation when
requesting preservation of the completed implementation on 2026-10-15.

The exact programmed image was
`firmware/build/local_blink_f427/firmware.bin`, 7,304 bytes, SHA-256
`90f5028e93c9cfad412a3e4ae87a7eac7737437928ba949b10e905f69c4d8deb`.
Its ELF/BIN contents and build-input hashes were rechecked before writing.
MCU preflight again confirmed ID 0x419, revision 0x2001 and 2,048 KiB Flash.

The original full Flash backup matched a fresh pre-write readback byte-for-byte:
2,097,152 bytes, SHA-256
`6ec241a5b3cb745580f79b2041ded78dc9ab9442b2f7f09ea47e4f2bb13b8ef0`.
Only Flash bank 0 sector 0, [0x08000000,0x08004000), was explicitly erased.
The image was written at 0x08000000 and verified, then all Flash beyond that
sector was verified against the backup before reset/run. No mass erase,
unprotect or option programming was issued. OpenOCD exited successfully.

A subsequent independent full readback confirmed every image byte exactly,
erased 0xFF padding to the end of sector 0, and all **2,080,768 bytes outside
sector 0 unchanged**. Post-write full Flash SHA-256:
`1901c433d89a54f01a94699c5cee747c3b4e4d8075e803bd49264f6a7ab94ec5`.
FLASH_OPTCR=0x0FFFAAED and FLASH_OPTCR1=0x0FFF0000 remained unchanged.

Read-only execution evidence from the actual MCU:

- local_blink_status=2; local_hal_error=0.
- Reported SystemCoreClock=168000000; PD13 configured as output and final ODR LOW.
- Trace metadata contains 96 event bytes, twelve LED1 records.
- Boot alias vectors equal the Flash vectors: SP=0x20030000, reset=0x08000351;
  SYSCFG_MEMRMP=0. This confirms Flash mapping for the observed run, not the
  physical BOOT0 level or jumper position.

| Firmware timecode (microseconds) | LED1 state |
| ---: | --- |
| 8 | LOW |
| 11 | HIGH |
| 251000 | LOW |
| 502000 | HIGH |
| 753000 | LOW |
| 1004000 | HIGH |
| 1254999 | LOW |
| 1506000 | HIGH |
| 1757000 | LOW |
| 2008000 | HIGH |
| 2258999 | LOW |
| 2510000 | LOW |

These are physical-board DWT trace values interpreted by the unchanged firmware
formula using its reported 168 MHz HCLK. They are not independently calibrated
wall-clock measurements. Ten alternating transitions give five pulses; the
initial and final LOW assignments are additional state records. The physical
waveform observation is the user's confirmation, separate from these memory
reads and from earlier synthetic tests.

One non-halting post-run probe returned inconsistent Flash-size/option values
while the application was idle, and its preflight correctly aborted without
writes. Briefly halting for stable read-only inspection restored the expected
identity/options and enabled the complete readback above. OpenOCD warned that
the target state was unknown when halt was requested. This is consistent with
an idle/sleep debug-access issue; the precise cause is not independently proven.
The MCU was resumed without another reset. No firmware correction was made.

Logs and readbacks remain ignored under `.tools/`:
`f427-programming.log`, `f427-after-program.log`,
`f427-after-program-halted.log`, `f427-execution-state.json`, and
`local-board-backup/`. They are not committed as firmware/backup artifacts.
The working cLAB F407 images and compiler pipeline remain unchanged.
See [local F427 build/deployment details](LOCAL_F427.md).

### Regression verification before the local Blink commit

On 2026-10-15, all **147 checks passed again**, with no failures:

| Suite | Passing checks |
| --- | ---: |
| Compiler JUnit (forced rerun) | 76 |
| ARM execution | 15 |
| Runtime/firmware integration | 13 |
| Marked diagnostics | 6 |
| Initialization diagnostics | 6 |
| Guarded PLL recovery | 12 |
| Recovered cLAB Blink | 6 |
| Local F407 Flash integration | 8 |
| Local F427 Flash integration | 5 |

ELF/BIN verification covered Flash/SRAM layout, vector tables, resolved runtime
symbols, exact load-image bytes, target-profile separation and corrupted-image
rejection. All 67 vendored-file SHA-256 values matched the manifest. The
hardware-tested F427 BIN retained its recorded size and hash; the preserved
F407 and cLAB images also passed their preservation checks.

This rerun was entirely local: no OpenOCD connection, board reset, programming,
driver change or new physical experiment was performed. The physical success
above is the user's reported observation, distinct from these regression tests.
The commit contains source, tests, necessary vendor files/licenses and portable
documentation. Firmware images, Flash backups, programming logs and host tool
installations remain ignored under `firmware/build/` and `.tools/`.

## Local STM32F427VIT6 OLED: confirmed physical text display

**Report recorded 2026-10-17 (Europe/Moscow, UTC+03:00).** The user supplied
this physical observation:

> I physically confirmed that "THE BEST GROUP" appears clearly on the built-in OLED of my STM32F427VIT6 SDK-1.1M board.

The board is the local **SDK-1.1M with STM32F427VIT6**, distinct from the remote
ITMO.cLAB F407. The confirmation date is recorded above; the exact date/time of
the visual observation was not separately supplied. The approved programming
and verification operation was previously completed on 2026-10-15.

| Firmware detail | Verified local artifact / configuration |
| --- | --- |
| EmbedLang source | `examples/oled_group.emb` |
| BIN | `firmware/build/local_oled_f427/firmware.bin` |
| ELF | `firmware/build/local_oled_f427/firmware.elf` |
| BIN size | 13,576 bytes |
| BIN SHA-256 | `a76fd04e15b0d6e2e7d5726d93433f6a677501e8f198883f5c4b77564d5a0c8c` |
| Load / vector address | 0x08000000; 428-byte F427 vector table |
| Initial stack / Thumb reset | 0x20030000 / 0x080005DD |
| Panel path | Official SDK_OLED 128×64 SSD1306-family driver and 7×10 font |
| Interface | I2C1, PB8 SCL / PB9 SDA, AF4, 400 kHz; 7-bit address 0x3C |
| Local clocks | Existing 25 MHz HSE / 168 MHz system-clock configuration |

The message is supplied by actual compiled EmbedLang code through typed OLED
runtime calls; it is not a message hard-coded in C. The program requests cursor
(15,27), emits fourteen printable ASCII codes and updates the framebuffer. String
literals, grammar, AST, IR and ARM backend remain unchanged. The user's observation
confirms readable text for this program; no precise glyph-position, duration,
I2C-waveform, controller-revision or electrical-margin measurement is claimed.
No photograph or instrument capture was supplied.

Before the approved programming, a fresh full 2 MiB Blink backup was verified
against the board and matched the preserved post-Blink readback. Only sector 0
[0x08000000,0x08004000) was erased. OpenOCD verified the OLED image/padding and
all 2,080,768 unrelated Flash bytes, confirmed unchanged option registers, and
completed reset/run with exit code 0. These programming results are distinct
from the later visual confirmation. Backups, binaries and logs remain ignored;
[LOCAL_OLED.md](LOCAL_OLED.md) records the source provenance and deployment details.

The successful local Blink commit remains
`5a5fbd608614d5a1d86e004630728025771beb15`, with its BIN preserved. Existing cLAB
source and physically tested probe/Blink images remain unchanged. The current
preservation step performs local regression tests only and does not access or
modify the board.

### Regression rerun before the OLED preservation commit

On **2026-10-17**, all **160 checks passed again**, with zero failures:
82 compiler JUnit tests (forced rerun), 15 ARM execution checks,
43 runtime/cLAB diagnostic/initialization/recovery/Blink tests,
eight local F407 tests, five local F427 tests and seven OLED integration tests.
ELF/BIN verification, generated text/pixel-frame checks, I2C setup and error
handling, bounds checks, and Blink preservation checks passed. All 78 vendor
hashes matched, with the previous 67 entries unchanged. The 13,576-byte OLED
BIN retained the hash recorded above; its integration input hashes also matched.

This verification used existing local artifacts and emulation. The successful
hardware-tested firmware was not overwritten by a rebuild. No board connection,
reset, flash, option-byte or driver change was performed. The preservation
commit includes source, required vendor files/licenses, tests and documentation;
generated binaries, Flash backups, logs, credentials and machine-specific files
are excluded. These local checks are separate from the user's visual hardware
confirmation.

## Trace timestamp units

The pinned official `Core/Inc/trace.h` defines `CLK_Prescaler` as 1,000,000 and
`GetCC()` as `DWT_CYCCNT`. In `Core/Src/trace.c`, both timestamp events and PRINT
records store:

```c
GetCC() / (HAL_RCC_GetHCLKFreq() / CLK_Prescaler)
```

With the verified 168 MHz HCLK this divides the cycle count by 168: the raw
stored timecode is integer **microseconds**, with truncation. A 250 ms interval
therefore corresponds nominally to 250,000 raw units. This formula and the
counter are preserved unchanged. The 32-bit cycle counter wraps after about
25.57 seconds at 168 MHz, beyond the laboratory's approximate eight-second
execution window.

The Web IDE's decimal timestamp display units have not been independently
verified from its renderer. The Blink report above supports milliseconds as an
inference, separate from the verified raw microsecond format. Programmed delay
totals and synthetic test timecodes are not physical execution measurements.
