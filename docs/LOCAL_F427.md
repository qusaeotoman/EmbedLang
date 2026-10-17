# Confirmed local STM32F427VIT6: verified Blink deployment

## Deployment completed, 2026-10-15

After explicit user approval to proceed despite physical BOOT0 uncertainty, the
7,304-byte F427 image was programmed and verified, using only the required first
16 KiB sector. Full readback confirmed all 2,080,768 bytes outside that sector
unchanged, and both option registers matched their originals. The user confirmed
five green pulses and final OFF; MCU completion state=2, HAL error=0 and twelve
LED1 records independently confirmed execution. Flash boot mapping was observed,
while physical XP3/BOOT0 remains unconfirmed.

See [the complete result, raw timecodes and diagnostic warning](HARDWARE_VALIDATION.md#local-stm32f427vit6-programmed-and-physically-observed-blink).
The preparation evidence below predates this approved deployment.

## Identification and driver verification, 2026-10-15

The user read the physical marking **STM32F427VIT6**. This resolves the mismatch
with the earlier assumed F407. The local board and the hardware-tested cLAB
F407 target are distinct; the compiler pipeline and cLAB firmware remain intact.

After the user's approved Zadig installation, read-only Windows queries verified:

| Interface | Driver service | Result |
| --- | --- | --- |
| USB 0403:6010 MI_00, SDK 1.1M Debugger | WinUSB | Healthy, problem code 0 |
| MI_01, USB Serial Converter B | FTDI FTDIBUS, 2.12.36.20 | Unchanged, healthy |
| COM5, associated with MI_01 | FTDI FTSER2K, 2.12.36.20 | Unchanged, healthy |

Read-only OpenOCD examination succeeded with no reset/halt/programming commands:

```text
CPU JTAG ID:      0x4BA00477
Boundary TAP ID:  0x06419041
Core:            Cortex-M4 r0p1
DBGMCU_IDCODE:   0x20016419
DEV_ID / REV_ID: 0x419 / 0x2001
Flash size:      0x0800 KiB = 2048 KiB
FLASH_OPTCR:     0x0FFFAAED
FLASH_OPTCR1:    0x0FFF0000
F427_PREFLIGHT_OK
```

DEV_ID 0x419 identifies the F42x/F43x family, not a unique package/part; the exact
F427VIT6 identity comes from the physical marking. The old `stm32f407` log prefix
was a configuration label, not a silicon identification. The new profile labels
the target `stm32f427`. Family mapping is corroborated by the
[official OpenOCD implementation](https://github.com/openocd-org/openocd/blob/v0.12.0/src/flash/nor/stm32f2x.c).

Option decoding was checked against the ST F427 definitions:

- WDG_SW=1: software-selected independent watchdog, compatible with the wrapper
  that does not start/refresh it.
- RDP=0xAA: readout protection level 0.
- SPRMOD=0 and both nWRP masks=0xFFF: no sector write protection indicated.
- BFB2=0: no bank-2 boot option selected. Physical BOOT0 was not confirmed;
  the user explicitly approved proceeding despite this uncertainty. Flash mapping was observed after execution.

Logs are in ignored `.tools/local-f427-readonly.log` and
`.tools/local-f427-preflight.log`. The reusable probe now uses `echo/read_memory`
so batch logs actually show register values, and rejects a profile/ID/capacity
mismatch. It does not issue erase, unlock, write, reset or halt commands.

```powershell
.\firmware\local\probe.ps1 -Mcu stm32f427vit6
```

## Existing Flash preserved before any write

A read-only `dump_image` saved all 2,097,152 bytes of the current physical board's
Flash without reset or halt:

`.tools/local-board-backup/stm32f427-before-blink.bin`

SHA-256: `6ec241a5b3cb745580f79b2041ded78dc9ab9442b2f7f09ea47e4f2bb13b8ef0`.

This is a readback snapshot of the existing Flash, not a newly generated image
or a tested restore. It stays ignored and is not printed, uploaded or committed.
Backup log: `.tools/local-f427-backup.log`. No program/erase/option changes were
performed during that backup operation. A later restore would itself require
explicit programming approval.

## Separate F427 build profile

Build with an explicit MCU choice; the default F407 profile is retained for
compatibility, not for this physical module:

```powershell
$env:JAVA_HOME = (Get-ChildItem .tools/jdk -Directory | Select-Object -First 1).FullName
$env:PYTHONPATH = (Resolve-Path .tools/python-deps).Path
$armBin = '.tools/arm-gnu/arm-gnu-toolchain-13.3.rel1-mingw-w64-i686-arm-none-eabi/bin'
python firmware/build_local.py examples/remote_blink.emb --mcu stm32f427vit6 --toolchain-bin $armBin
python tests/local_firmware_checks.py -v
python tests/local_f427_checks.py -v
```

The F427 build uses `-DSTM32F427xx`, the official ST F427 device header and F427
GCC startup from CMSIS-device-f4 v2.6.6, pinned to
`3d7a3c1bae597f1ff36431145a2e34ae82fdeecb`. Only the missing F427 header/startup
and license are added; the existing family wrapper, HAL and F407 sources are
not replaced. The nearest tagged release is used explicitly because the old
family wrapper reports 2.6.5, which has no tag in ST's standalone repository.
All files are checksummed, license notices retained; see `firmware/THIRD_PARTY.md`.

`firmware/local/STM32F427VITX_FLASH.ld` adapts the official SDK_EXTI section layout
to the confirmed part's capacities, with ST attribution retained:

| Region / property | F427 local configuration |
| --- | --- |
| Flash | [0x08000000, 0x08200000), 2 MiB |
| Contiguous main SRAM | [0x20000000, 0x20030000), 192 KiB |
| Separate CCM | [0x10000000, 0x10010000), 64 KiB; local trace use |
| Initial SP | 0x20030000 |
| Vectors | 0x08000000, 428 bytes, F427 IRQ table |
| Thumb reset vector / ELF entry | 0x08000351 |
| .data VMA / BSS end | 0x20000000 / 0x20000040 |
| Minimum heap / stack | 512 / 1024 bytes |

The part's 2 MiB Flash and 256 KiB total SRAM including 64 KiB CCM are documented
by [ST](https://www.st.com/en/microcontrollers-microprocessors/stm32f427vi.html).
The verifier checks every load segment and allocated section, Flash LMAs versus
SRAM VMAs, exact BIN bytes, vectors/entry, runtime symbols/constants, unresolved
symbols and stack reservations. It rejects F407 and F427 image interchange.

The shared local wrapper retains the SDK board's 25 MHz HSE configuration with
PLL M=25, N=336, P=2, Q=4, yielding nominal **168 MHz**. AHB /1, APB1 /4, APB2 /2,
Flash latency 5 and the F427 two-bit voltage-scale-1 setting are compiled from
the F427 definitions and tested. It does not select 180 MHz or enable overdrive.
HSE frequency/accuracy and actual local timing have not been measured.

The official F427 startup initializes FPU, Flash VTOR, initialized data/BSS and
the correct IRQ vector set. The wrapper requires a cold reset; clock/tick errors
are fatal to generated execution. There is **no cLAB PLL recovery** or IWDG
initialization. The real option read confirms software watchdog selection.

No handwritten C LED loop is added. `examples/remote_blink.emb` is compiled by
the unchanged EmbedLang CLI, with the resulting assembly byte-for-byte identical
to the preserved F407 version: configure green PD13, initial LOW, ten toggles
with 250 ms delay calls, final LOW, return. It produces five expected pulses,
then the C wrapper idles without resetting. Runtime LED events remain in local
CCM for inspection; this is not a live COM5 trace or a cLAB trace-stop sequence.

## Final artifacts

- ELF: `firmware/build/local_blink_f427/firmware.elf`
- BIN: `firmware/build/local_blink_f427/firmware.bin`
- BIN bytes: **7,304**.
- BIN SHA-256: `90f5028e93c9cfad412a3e4ae87a7eac7737437928ba949b10e905f69c4d8deb`.
- No unresolved symbols. Adjacent map/disassembly/symbols/assembly/verification
  JSON and `.su` files are retained. Build log: `.tools/local-f427-build.log`.
- Existing upstream unused-parameter, GNU-stack and RWX-segment linker warnings
  remain visible; no unrelated linker redesign was introduced.

## Verification results

All **147 checks passed**: 76 compiler JUnit tests, 15 ARM execution checks,
43 existing firmware/diagnostic checks, eight local F407 tests and five F427
tests. The complete suite was rerun before committing the completed local implementation;
see the dated regression record in HARDWARE_VALIDATION.md.

The F427 emulator executes actual startup, original HAL cold initialization and
generated ARM code with synthetic RCC acknowledgements, GPIO/delay/tick hooks.
It checks F427 voltage scale, Flash latency, bus divisors, FPU, SysTick, all ten
PD13 transitions/final LOW, no IWDG start/reset request and fatal clock/tick/warm-
PLL errors. F427-specific vector slots and MCU compile flags are checked too.
Synthetic stack high-water was 280 bytes, not a full physical interrupt bound.

The initial physical checks established USB/JTAG communication, family/capacity
and options. The F427 firmware subsequently executed successfully on this board,
as recorded above. The historical physical cLAB F407 success is separate evidence.

The F407 local BIN (7,236 bytes) and all physically verified cLAB probe/Blink and
reference BIN hashes remain unchanged. Compiler source/architecture, cLAB source
and stable Git commit `6b81ba3fc7c8fa2487629861dbc36f33d21c7c7c` remain intact.
The completed local implementation and physical validation record are preserved
in Git; generated images, readbacks and programming logs remain ignored.

## Programming procedure and approval boundary

The original ELF programming command below was prepared as an example. It was
not the command used for this deployment: the actual operation explicitly erased
only sector 0 and wrote the matching BIN. Future programming still requires
explicit approval. The user waived physical BOOT0 confirmation for this run;
no jumper was moved and no BOOT0 level is assumed.

```powershell
$ocd = '.tools/openocd/xpack-openocd-0.12.0-7/bin/openocd.exe'
$scripts = '.tools/openocd/xpack-openocd-0.12.0-7/openocd/scripts'
$elf = (Resolve-Path firmware/build/local_blink_f427/firmware.elf).Path.Replace('\', '/')
& $ocd -s $scripts -c 'gdb port disabled' -c 'tcl port disabled' -c 'telnet port disabled' `
    -f firmware/local/openocd/sdk11m_f427.cfg -f firmware/local/openocd/check_f427.cfg `
    -c 'init' -c 'sdk11m_check_f427' -c "program {$elf} verify reset exit"
```

`sdk11m_check_f427` returned F427_PREFLIGHT_OK. For the executed deployment,
`.tools/program-approved-f427.tcl` instead issued reset/init and halt, followed by:

```tcl
flash probe 0
flash erase_sector 0 0 0
flash write_image {firmware/build/local_blink_f427/firmware.bin} 0x08000000 bin
verify_image {firmware/build/local_blink_f427/firmware.bin} 0x08000000 bin
verify_image {.tools/local-board-backup/unrelated-flash-before.bin} 0x08004000 bin
```

It then compared both option registers with their saved values before reset/run.
The programming process exited 0. Independent full readback matched the BIN
exactly and confirmed all unrelated sectors unchanged. The saved original backup
also matched a fresh complete pre-write readback. Neither mass erase, unprotect,
option programming nor the cLAB RAM image was used. Existing sector-0 contents
were overwritten as approved; the original full Flash snapshot is preserved.

The first running/idle post-run probe produced inconsistent size/option reads
and aborted safely. Stable inspection with a brief halt confirmed the original
values and successful execution; the MCU was resumed without another reset.
This warning and its unproven sleep/debug-access explanation are retained in
the hardware record rather than being treated as a programming failure.
