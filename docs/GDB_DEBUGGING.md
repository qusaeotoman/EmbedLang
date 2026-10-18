# Milestone 7 investigation: GDB over TCP/IP

Initial local connection investigation, 2026-10-17, preserved at `848a38e`.
The subsequent optional `.emb` mapping and actual GDB source-step results are in
[SOURCE_DEBUGGING.md](SOURCE_DEBUGGING.md). Findings and mapping proposals below
describe the pre-mapping baseline; existing firmware ELFs retain that baseline.
The later [VS Code DAP/MI2 integration](VSCODE_DEBUGGING.md) demonstrates actual
editor source debugging in a separate local CPU profile. The limitations below
describe this initial investigation, not that subsequent editor test result.
No hardware, flashing or editor debug integration. The editor/report commit is
`40fa24276761ee67af803e6741c483f7f6f89a93`; its working tree was clean before
this investigation began. Zed UI acceptance and Zed Problems/LSP remain incomplete.
The Zed dev-builder route also still requires a pinned source revision containing
generated parser C/headers; those inputs are currently ignored. The unpacked
package remains the local prototype route, pending real-editor validation.

## Evidence from existing artifacts

Read-only inspection used pyelftools and the existing ARM GNU tools. The original
ELFs/BINs were not rewritten. Reproduce with:

```powershell
python tools/debug/inspect_elf.py firmware/build/local_blink_f427/firmware.elf firmware/build/local_oled_f427/firmware.elf firmware/build/diagnostic_blink_recovered/firmware.elf
```

| Artifact | Entry | Observed debug coverage |
| --- | --- | --- |
| Local F427 Blink | `0x08000351` | ARM ELF, `.symtab`, `embed_program_main`, C/startup DWARF and generated `program.s` line table |
| Local F427 OLED | `0x080005dd` | ARM ELF, same kinds of debug metadata; generated `program.s` |
| Recovered cLAB Blink | `0x2000d401` | ARM ELF, C/startup DWARF and generated function symbol; no generated program source in the inspected line files |
| Existing ARM execution fixture | `0x10001` | ARM ELF and generated function symbols; no `.debug*` sections |

**No inspected line table names an `.emb` file.** `-g3` in firmware builders
provides C/startup/generated-assembly information; it does not map instructions
back to EmbedLang. The backend emits `.type`, `.thumb_func` and `.size`, but no
`.file`, `.loc` or `.cfi_*` directives. IR nodes already retain SourceLocation;
no frontend/IR redesign is needed for the initial mapping proposal.

Assembly line tables alone are not complete typed debug information: GDB may
associate assembly lines with an unexpected enclosing symbol and report
multiple breakpoint locations. Typed EmbedLang locals/parameters and reliable
cross-function unwinding have not been demonstrated.

## Tools and target selection

- Available: ARM GNU **13.3.Rel1**, ARM GDB
  **14.2.90.20240526-git**, target `arm-none-eabi`, `armv7e-m` accepted.
- This GDB reports **without Python**. Actual `--interpreter=dap` invocation
  fails with `Interpreter 'dap' unrecognized`. MI2 was exercised using tokenized
  `-gdb-version` and `-gdb-exit`, both successful. The native host GDB is not a
  substitute for the ARM-target build.
- Unicorn **2.1.4** and pyelftools **0.33** are already available for regression
  testing. A small RSP endpoint uses Unicorn's Cortex-M4/Thumb instruction
  execution, not a mock register transcript.
- No `qemu-system-arm` installation was found on PATH. QEMU documents F405-based
  boards, not this complete SDK-1.1M F427 system, and lists missing GPIO/I2C/
  watchdog/full RCC support. A QEMU CPU test could be useful later; unchanged
  STM32 OLED/clock firmware is not assumed to work there.
- OpenOCD remains the eventual hardware-server candidate. It was not started
  or contacted in this investigation.

## Local RSP proof

`tools/debug/unicorn_rsp.py` runs a **single-client loopback-only** TCP endpoint.
It loads only pure `.text` linked at synthetic address `0x10000` (maximum 64 KiB),
plus synthetic stack RAM and a return sentinel. These are host-test addresses,
not SDK-1.1M Flash/SRAM configuration. No reset vectors, PLL, GPIO, OLED, HAL,
watchdog, interrupts or physical timing are modeled.

The minimal acknowledged RSP subset implements target XML, core-register reads,
bounded memory reads, logical `Z0/z0` breakpoints, continue and instruction step,
thread queries and detach. Breakpoints stop Unicorn at instruction boundaries;
they are not STM32 FPB hardware breakpoints. Unsupported operations return the
standard empty reply. No memory/register write, `load`, monitor command, Flash
operation, remote file access, restart or arbitrary process execution is offered.

Each continue is bounded to 100,000 instructions / one second; exhaustion
reports SIGINT, not a breakpoint. The synchronous stub does not offer immediate
asynchronous interrupt processing while running, full RSP compliance, FPU/
system-register coverage, multiple threads or persistent reconnects. Idle/client
startup timeouts are bounded. This is test scaffolding, not a production debug
server or a replacement for OpenOCD.

### Reproduce the automated proof

Requirements: Java 17, installed compiler distribution, ARM GNU assembler/linker/
GDB, Python and `firmware/requirements-tests.txt`. The existing test dependency
file pins Unicorn/pyelftools. No new global dependency is installed by the tests.

```powershell
python -m pip install -r firmware/requirements-tests.txt
./gradlew.bat :compiler:installDist
# Set armBin to your extracted ARM GNU toolchain's bin directory:
python tests/gdb_connection_checks.py --assembler "$armBin/arm-none-eabi-as.exe" --linker "$armBin/arm-none-eabi-ld.exe" --gdb "$armBin/arm-none-eabi-gdb.exe"
```

Linux/macOS can use the same Python test arguments with their tool paths and no
`.exe` suffix; those platforms have not been tested. The test compiles the actual
`examples/diagnostic_probe.emb`, assembles with `-g`, and links a separate ELF.
All generated output is ignored under `build/gdb-poc/`: `probe.s`, `.o`, `.elf`,
`checks.gdb`, `gdb-session.log`, `result.json`. Existing firmware outputs stay intact.

Eight checks pass, including an actual ARM GDB process connected to an actual
localhost TCP socket. It reaches the generated probe breakpoint, observes
arguments **6 and 7**, reads registers/disassembly/stack memory, executes `stepi`,
and continues until **r0=42**, **SP=0x20010000** at the return sentinel. Other
checks cover ELF/assembly-only line data, target XML/register layout, invalid
memory reads, unsupported writes/Flash/monitor requests, loader preconditions,
checksum rejection/fragmented TCP requests and bounded infinite-loop execution.

Observed GDB output includes:

```text
BREAKPOINT_ARGUMENTS_OK
INSTRUCTION_STEP_OK
RESULT=42 SP=0x20010000
RETURN_AND_STACK_OK
```

The Windows GDB build emits a CP1252-to-UTF-32 conversion warning; occasionally
it also warns that regenerated assembly is newer than the executable. These
are retained in ignored logs. Assertions pass; this does not establish Unicode
source-path support. Attempting to force UTF-8 was rejected by this toolchain,
so no unsupported charset setting is hidden in the working recipe.

### Manual terminal session, without an editor

After the automated test builds the fixture, start:

```powershell
python tools/debug/unicorn_rsp.py --elf build/gdb-poc/probe.elf --entry main --port 3333
```

In another terminal, within the startup timeout:

```text
arm-none-eabi-gdb -nx -nh build/gdb-poc/probe.elf
(gdb) target remote 127.0.0.1:3333
(gdb) break embed_fn_diagnostic_probe
(gdb) continue
(gdb) info registers r0 r1 sp pc xpsr
(gdb) x/4i $pc
(gdb) x/2wx $sp
(gdb) stepi
(gdb) continue
(gdb) print $r0
(gdb) detach
```

The emulator stops at its return sentinel; it is not a normal operating-system
process exit. Restart the server for another session. Do not point a hardware
firmware ELF at this loader or infer board execution from this session.

## Proposed editor solution — not implemented yet

```text
Editor DAP client → debug adapter → ARM GDB → TCP RSP target
                                       ↘ current local Unicorn proof
                                       ↘ future approved OpenOCD hardware server
```

**VS Code:** evaluate the existing Cortex-Debug adapter with its external-server
attach workflow and ARM GDB/MI. First prove symbol/address breakpoints,
instruction stepping, registers, memory and disconnect against the same local
target. Do not make reset, download or Flash programming part of an attach
default. Test an isolated Extension Host profile before registering an EmbedLang
debug configuration. No adapter installation or launch configuration is added now.

**Zed:** it is a DAP client, not an RSP client. Its `tcp_connection` refers to
**DAP transport**, not the GDB target port; pointing it at `3333` would conflate
two protocols. Evaluate a compatible ARM GDB build with native DAP, or an
external DAP-to-GDB/MI adapter. The currently available ARM GDB cannot provide
native DAP. Zed lists a GDB adapter for C, but that does not prove this binary/
target combination works or register EmbedLang automatically. If a custom
adapter is necessary, its manifest, schema and Rust extension hooks must be
implemented/tested later. First complete Zed's basic real-editor acceptance.

Both editors need adapter-level tests for breakpoint hit/removal, instruction
step/continue, register/memory display, target disconnect/timeout and correct ELF
selection. GDB `stepi` over the terminal does not prove an editor Step button.

### Eventual `.emb` source mapping

1. Explain and agree on an **optional debug emission** extension to the ARM
   emitter before changing it. Reuse existing IR SourceLocation; preserve normal
   code generation and all firmware profiles.
2. Emit portable `.file` / statement `.loc` information and verify decoded line
   tables point to actual `.emb` lines. Exclude prologue/epilogue locations where
   appropriate. Preserve relocated addresses and renamed `embed_program_main`.
3. Add/test unwind information for generated prologues/epilogues. Then emit
   subprogram/type/parameter/local metadata with actual stack locations and
   lexical scopes. Line mapping alone does not expose typed locals.
4. Demonstrate `break file.emb:line`, source `step`/`next`, nested calls, stack
   frames and variables in real GDB, then repeat in both editor UIs. Handle
   shadowed locals, branches/loops and Unicode paths with explicit tests.
5. Only after local proof and separate hardware authorization, validate an
   attach session against the matching F427 Flash ELF or F407 cLAB RAM ELF.
   No automatic loading, watchdog changes or hardware reset is authorized here.

These are requirements/plans, **not implemented features**. The language,
ANTLR/AST/IR, ARM emitter, firmware and editor debug integrations are unchanged
in this investigation. No physical or `.emb` source-level debugging is claimed.

## Primary references

- [GDB Remote Serial Protocol](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Remote-Protocol.html)
- [GDB packet definitions](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Packets.html)
- [ARM M-profile XML registers](https://sourceware.org/gdb/current/onlinedocs/gdb.html/ARM-Features.html)
- [GDB DAP attach target](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Debugger-Adapter-Protocol.html)
- [Unicorn documentation](https://www.unicorn-engine.org/docs/)
- [QEMU STM32 coverage and missing peripherals](https://www.qemu.org/docs/master/system/arm/stm32.html)
- [Cortex-Debug](https://github.com/Marus/cortex-debug)
- [Zed debugger/DAP configuration](https://zed.dev/docs/debugger)
- [Zed C debugger candidates](https://zed.dev/docs/languages/c)
- [Zed custom debugger extension API](https://zed.dev/docs/extensions/debugger-extensions)

These references were inspected for the design. Only the local GDB/RSP path
above was executed; no editor adapter or QEMU result is implied.
