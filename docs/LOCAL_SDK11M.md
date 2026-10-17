# Local SDK-1.1M: USB diagnosis and finite Flash Blink

**Subsequent confirmed result:** the user installed WinUSB on MI_00 only, and
OpenOCD now communicates successfully. The physical chip is **STM32F427VIT6**,
not the original assumed F407. Its ID is 0x419, Flash is 2,048 KiB, and watchdog
selection is software. MI_01/COM5 retain their FTDI drivers. Use the separate
[current F427 profile and verification report](LOCAL_F427.md). The initial
diagnosis and preserved F407 build below remain historical reference, not the
programming choice for the attached F427 board. The user subsequently confirmed
five green pulses followed by OFF; see the [physical validation record](HARDWARE_VALIDATION.md).
All statements below about blocked access or pending approval describe the initial
preparation stage, before the separately approved driver change and F427 deployment.

## Historical preparation snapshot, 2026-10-15

Stable commit `6b81ba3fc7c8fa2487629861dbc36f33d21c7c7c` is preserved. Compiler,
language, AST, IR, ARM backend and the successful cLAB integration are unchanged.
The new local firmware is built and locally tested, **not flashed or physically
validated**. No driver, registry, PATH or Windows system configuration was changed.
The portable OpenOCD download stays in ignored `.tools/`.

## USB findings

Read-only PowerShell CIM/PnP queries on this computer found:

| Device | Hardware IDs / interface | Driver | State |
| --- | --- | --- | --- |
| Composite adapter | USB VID_0403, PID_6010, REV_0500 | Microsoft usbccgp, usb.inf | OK, problem code 0 |
| USB Serial Converter A | USB\VID_0403&PID_6010&MI_00 | FTDI FTDIBUS, 2.12.36.20, signed | OK, problem code 0 |
| USB Serial Converter B | USB\VID_0403&PID_6010&MI_01 | FTDI FTDIBUS, 2.12.36.20, signed | OK, problem code 0 |
| USB Serial Port COM5 | FTDIBUS\COMPORT&VID_0403&PID_6010&MI_01 | FTDI FTSER2K, 2.12.36.20, signed | OK, problem code 0 |

COM5 belongs to **interface 1**, not the JTAG debug channel. Interface 0 is
recognized by Windows, but is bound to the FTDI serial-converter driver instead
of WinUSB. A healthy Device Manager status alone does not establish OpenOCD
compatibility or identify the MCU behind the adapter.

The [official board documentation](https://github.com/lmtspbru/SDK-1.1M/blob/bd8cba8f4bd5fc2d1460e6ad4da7b7dd13d9e14d/README.md)
specifies FTDI 0403:6010, JTAG, the supplied layout masks, USB DBG connection and
WinUSB on **Interface 0**, explicitly excluding Interface 1 from replacement.
The existing COM5 connection therefore matches the serial side of that adapter.
Actual MCU identification remains blocked by debug-interface access.

Reproduce Windows inventory from the repository root:

```powershell
.\firmware\local\inspect_connection.ps1
```

Sandbox CIM queries initially returned Access Denied; host read-only queries
succeeded. No system permission or device setting was altered to perform them.
Unique USB instance suffixes are omitted from this document; the relevant public
VID/PID/interface IDs are retained.

## Development tools

| Tool | Observed availability |
| --- | --- |
| ARM GNU GCC / binutils | Existing portable Arm GNU 13.3.Rel1 in `.tools/arm-gnu/arm-gnu-toolchain-13.3.rel1-mingw-w64-i686-arm-none-eabi/bin` |
| arm-none-eabi-gdb | Same directory; version command succeeded, GDB 14.2.90.20240526-git |
| OpenOCD | Not initially detected; portable xPack 0.12.0-7 prepared in `.tools/openocd/xpack-openocd-0.12.0-7` |
| STM32CubeIDE | Not detected in PATH, standard ST/Program Files locations or uninstall registry inventory |
| STM32CubeProgrammer | Not detected in those locations/inventory |
| Zadig | Not detected in PATH, checked install locations, Downloads/Desktop filenames or uninstall inventory |
| WinUSB binding for debug channel | Missing on MI_00; FTDI FTDIBUS is currently bound |

Custom software locations outside the checked paths cannot be ruled out.
CubeIDE and CubeProgrammer are not required for this build/OpenOCD path.
Windows includes WinUSB support; the missing piece is the specific interface
binding, not necessarily an absent operating-system driver file.

Portable OpenOCD source: [xPack release 0.12.0-7](https://github.com/xpack-dev-tools/openocd-xpack/releases/tag/v0.12.0-7).
Archive `xpack-openocd-0.12.0-7-win32-x64.zip` SHA-256 was checked before extraction:
`6bfd3c97135aafef8affc9af1acf34fd0e2b9ca26044506f6abd7f95b7630052`.
Executable version: `0.12.0+dev-02228-ge5888bda3-dirty (2025-10-04-22:44)`.
No privileged installer was run; its bundled licenses remain with the tool.

## Read-only OpenOCD connection result

`firmware/local/openocd/sdk11m.cfg` uses the official layout and JTAG wiring
with current OpenOCD spelling and explicit `ftdi channel 0`. The CHIPNAME is a
configuration label, not evidence of an identified MCU. Original SDK_EXTI cfg
uses a STM32F427 label; the README describes a shared F407/F427 configuration.
The maintained file targets the STM32F4 family and a requested F407 build.

The local configuration disables the upstream target script's reset-init hook
that would switch to a 64 MHz PLL. The probe configuration additionally clears
automatic examine-end DBGMCU writes and disables the RAM work area. It issues
no reset, halt, program, erase, unlock or option-byte modification. Debug-protocol
initialization itself still communicates through the probe.

The actual probe failed before target examination:

```text
Error: libusb_open() failed with LIBUSB_ERROR_NOT_FOUND
Error: unable to open ftdi device with description '*', serial '*' at bus location '*'
Probe exit code=1
```

Full local log: `.tools/local-openocd-probe.log`. This is consistent with MI_00's
current non-WinUSB binding; it is not evidence that the STM32 is defective.
No MCU ID, Flash capacity, option-byte value or local hardware execution was
obtained. COM5 was not opened or used as a programming port.

After an approved driver correction, repeat only:

```powershell
.\firmware\local\probe.ps1
```

The script disables network servers, scans the chain and reads DBGMCU_IDCODE
at 0xE0042000, the Flash-size halfword at 0x1FFF7A22 and FLASH_OPTCR at 0x40023C14,
then exits. Addresses come from the pinned STM32F407 CMSIS header. Confirm the
expected STM32F407-compatible family and 1,024 KiB Flash before deployment; USB
enumeration cannot establish these. Do not use readout-unprotect/unlock commands.

### Required driver correction: approval pending

Only after explicit approval, use [Zadig](https://zadig.akeo.ie/) as instructed by
the official board documentation:

1. Options → List All Devices.
2. Select **USB Serial Converter A / Dual RS232 (Interface 0)**, or its SDK debug
   equivalent; verify USB ID 0403:6010 and interface **MI_00**.
3. Replace that interface's driver with **WinUSB**.
4. Leave **MI_01**, USB Serial Converter B, COM5 and the composite parent alone.
   Do not uninstall the shared FTDI package: MI_01 still uses it.
5. Re-query device services/status and repeat the read-only probe.

This changes a privileged Windows driver binding and can temporarily remove
interface A's FTDI functionality. It was not performed automatically. A driver
approval does **not** authorize Flash programming.

## Separate local Flash firmware

The new entry point is `firmware/build_local.py`; existing `firmware/build.py`
and all cLAB outputs are unchanged. Both invoke the same compiler CLI and reuse
the same generated `examples/remote_blink.emb` program and board runtime.
There is no handwritten C Blink loop or change to the compiler pipeline.

The local build uses these byte-preserved SDK_EXTI files at SDK-1.1M revision
`bd8cba8f4bd5fc2d1460e6ad4da7b7dd13d9e14d`:

- `STM32F407VGTX_FLASH.ld`: Flash 0x08000000/1 MiB, SRAM 0x20000000/128 KiB.
- `Core/Startup/startup_stm32f407vgtx.s`: reset/data-copy/BSS initialization/vector table.
- `Core/Src/system_stm32f4xx.c`: VTOR at Flash base, offset zero, FPU initialization.
- `SDK11M.cfg`: original wiring reference, retained unmodified.

The manifest extends the original 60 checksums to 64; original hashes and
licenses are intact. Existing pinned HAL, interrupts, trace library and runtime
are reused. See `firmware/THIRD_PARTY.md`.

`firmware/local/main.c` supplies one C startup main; the generated object's main
is renamed to `embed_program_main`, as in the cLAB build. From a **cold hardware
reset**, it requires HAL_Init, HSE/PLL setup and clock configuration to succeed.
Clock parameters follow SDK_EXTI: HSE crystal, M=25, N=336, P=2, Q=4, nominal
168 MHz, AHB /1, APB1 /4, APB2 /2, voltage scale 1, Flash latency 5. The board
reference assumes a 25 MHz HSE; crystal accuracy is not locally measured.
The wrapper also checks SysTick reload/control and global interrupt masking.

There is **no PLL recovery** in the local build. An inherited active-PLL false
error, genuine oscillator timeout or clock failure stops generated execution.
Use a real reset/normal Flash boot rather than jumping from an already-running
application or cLAB handoff. Failure is visible through `local_blink_status`
(0x80000001 HAL initialization, 0x80000002 oscillator, 0x80000003 clock/tick,
0x80000004 Error_Handler) and `local_hal_error`.

The generated code configures only the requested green PD13 GPIO through the
existing runtime, writes LOW, toggles ten times with ten 250 ms delay calls,
writes final LOW and returns. This makes five pulses. The wrapper sets status 1
before generated execution and status 2 after completion, then idles in WFI.
It does not reset/restart the demonstration. Nominal delays total 2.5 seconds;
physical local timing and LED behavior are unverified.

The SDK_LED example does not start IWDG, and neither does this local wrapper.
The cLAB watchdog initialization and execution budget are not blindly inherited.
**Read the hardware watchdog option before flashing:** FLASH_OPTCR bit 5
(`FLASH_OPTCR_WDG_SW`, `OB_IWDG_SW=0x20`) must indicate software selection for
this no-refresh image. Hardware-IWDG mode needs a separate reviewed strategy;
do not silently change option bytes. Readout protection/sector protection also
need review; downgrading protection can erase data. No options have been read yet.

Runtime LED events remain in local application-owned CCM using the original
trace implementation. The wrapper initializes it only after the clocks succeed,
sets task_id=0, and freezes its cycle counter after Blink. It deliberately never
calls SDK_TRACE_Stop, which would reset the MCU. These local in-memory events are
not a cLAB upload or live COM5 stream. The existing cLAB trace lifecycle is intact.

### Build and artifacts

From the repository root, with JDK 17 and the existing Python dependencies:

```powershell
$env:JAVA_HOME = (Get-ChildItem .tools/jdk -Directory | Select-Object -First 1).FullName
$env:GRADLE_USER_HOME = Join-Path (Get-Location) '.tools/gradle-user-home'
$env:PYTHONPATH = (Resolve-Path .tools/python-deps).Path
.\gradlew.bat --no-daemon :compiler:installDist
$armBin = '.tools/arm-gnu/arm-gnu-toolchain-13.3.rel1-mingw-w64-i686-arm-none-eabi/bin'
python firmware/build_local.py examples/remote_blink.emb --toolchain-bin $armBin
python tests/local_firmware_checks.py -v
```

- ELF: `firmware/build/local_blink/firmware.elf`
- BIN: `firmware/build/local_blink/firmware.bin`
- Size: **7,236 bytes**.
- BIN SHA-256: `b5bafeac1e63a477f6a52477672e93c257eff236c564ce52df2d8696a8492853`.
- Vectors 0x08000000; initial SP 0x20020000; Thumb reset vector 0x0800032D.
- .data VMA 0x20000000, initializers in Flash; BSS ends 0x20000040.
- Minimum heap/stack: 512/1,024 bytes. No unresolved symbols.
- ELF/BIN verification passed; assembly, map, symbols, disassembly, `.su` files
  and `verification.json` are adjacent. Build log: `.tools/local-blink-build.log`.
- Existing unused-parameter, GNU-stack and RWX-segment warnings remain visible.
  Stack observations do not establish a physical interrupt worst-case bound.

`firmware/local/verify.py` checks Flash LMAs, SRAM VMAs, exact BIN contents,
vectors, SysTick entry, reset/entry, runtime ABI/constants and heap/stack space.
It rejects the cLAB RAM image. **Never flash a cLAB BIN at 0x08000000.**

## Executed tests

All **142 checks passed** on this preparation run:

- 76 compiler JUnit tests, zero failures/errors; all compiler tests were rerun.
- 15 ARM execution checks.
- All 43 existing runtime/diagnostic/initialization/recovery/Blink checks.
- 8 new local Flash tests, including actual reset startup and original HAL clock
  code with synthetic ready bits, Flash-to-SRAM data initialization, generated
  PD13 transitions, final LOW, fatal HAL/HSE/tick failures, refusal to recover
  the warm PLL error, corrupted BIN rejection and cLAB-image rejection.

Synthetic local stack high-water was 280 bytes; GPIO/delay/tick hooks and ready
bits do not replace physical testing. No IWDG start/refresh or reset request was
emitted on the positive local path. HAL_Init's AIRCR priority-group write was
distinguished from a reset request.

The working cLAB Blink/probe/reference BIN hashes are unchanged. The stable Git
commit and physical evidence documents were preserved. The local implementation
is now preserved in Git with the later F427 validation record.

## Prepared programming command: NOT EXECUTED

First obtain working read-only MCU communication, confirm the target/Flash size,
software-watchdog and protection options, and confirm normal Flash boot selection
(BOOT0 low for this target). Review whether existing firmware must be backed up.
Only then request **separate explicit approval to erase/program Flash**.

After that approval, the prepared ELF command from the repository root is:

```powershell
$ocd = '.tools/openocd/xpack-openocd-0.12.0-7/bin/openocd.exe'
$scripts = '.tools/openocd/xpack-openocd-0.12.0-7/openocd/scripts'
$elf = (Resolve-Path firmware/build/local_blink/firmware.elf).Path.Replace('\', '/')
& $ocd -s $scripts -f firmware/local/openocd/sdk11m.cfg -c "program {$elf} verify reset exit"
```

The ELF specifies load addresses beginning at **0x08000000**. This command
performs erase/write/verify and reset; it is not a connection test. It can
overwrite existing application or bootloader contents in affected Flash sectors,
including the first sector containing the vector table. A readback backup is
needed beforehand if those contents must be preserved and protection permits.
Do not use mass erase, option-byte changes or readout unprotect as a shortcut.
Observe five green pulses and final LOW after a successful approved deployment;
no local physical Blink success is claimed yet.
