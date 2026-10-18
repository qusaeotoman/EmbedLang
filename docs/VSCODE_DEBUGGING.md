# VS Code: local EmbedLang source debugging

Verified on 2026-10-17 with VS Code 1.139.1, Cortex-Debug 1.12.1,
ARM GNU 13.3.Rel1 / GDB 14.2.90 and Unicorn 2.1.4. The source-line milestone
is preserved as `87807cefcb7eb96445ab79cb8f5c162a53ef5681`.
This VS Code integration was subsequently preserved as
`b4bd308d56685035d35267241c5fbc2fb41aba33`. The following sections record its
tested behavior. A separate [Zed continuation](ZED_DEBUGGING.md) now has build
and protocol validation; Zed UI acceptance remains pending.

## Design and boundaries

The existing maintained **Cortex-Debug** adapter connects VS Code DAP to ARM
GDB/MI2, which connects by loopback TCP RSP to our Unicorn Cortex-M4 target.
There is no custom DAP adapter. The compiler, AST, IR, ARM backend and firmware
profiles are unchanged by this integration.

The command compiles the saved current `.emb` file with `--emit-asm --debug-lines`,
assembles using `-mcpu=cortex-m4 -mthumb -g --gdwarf-4`, and links with
`-Ttext=0x10000 -e main`. Outputs are ignored files under the source workspace's
`build/vscode-debug/program.{s,o,elf}`. This is a pure CPU debug image with
synthetic RAM and a return sentinel, not a Flash/cLAB firmware image. Hardware
runtime calls remain unresolved; GPIO, OLED, RCC, watchdog and interrupts are not
emulated by this profile. Use the arithmetic fixture, not a hardware application.

## Setup and use

1. Build the compiler distribution with JDK 17:
   `./gradlew --no-daemon :compiler:installDist` (Windows: `./gradlew.bat`).
2. Load/install the [local EmbedLang extension](../extensions/vscode/README.md).
   Separately install **Cortex-Debug**, identifier `marus25.cortex-debug`.
   The EmbedLang command does not automatically install it. Basic language
   features work without it.
3. Provide ARM GNU tools (`arm-none-eabi-as`, `ld`, `gdb`, `nm`, `objdump`) and
   Python with `pip install -r firmware/requirements-tests.txt`.
4. Configure the following local settings, using absolute tool paths when tools
   are not on PATH. Keep machine paths out of Git.

| Setting | Meaning |
| --- | --- |
| `embedlang.compilerDirectory` / `embedlang.javaPath` | Existing compiler/JDK settings |
| `embedlang.localDebug.repositoryDirectory` | EmbedLang repository containing tools/debug/unicorn_rsp.py; default source workspace root |
| `embedlang.localDebug.toolchainDirectory` | ARM GNU bin directory; empty uses PATH |
| `embedlang.localDebug.pythonPath` | Python executable; empty uses python on PATH |
| `embedlang.localDebug.pythonModulePath` | Optional PYTHONPATH for locally installed test dependencies |

Open a **trusted** workspace and saved
[tests/fixtures/source_debug.emb](../tests/fixtures/source_debug.emb).
Set a breakpoint on line 2, then use **EmbedLang: Debug Current File in Local
Unicorn** from the Command Palette. No launch.json is required. The command saves
dirty text first; if the source or trust changes during the build, restart it.
Use VS Code's Continue, Pause, Step Into and Stop controls. Inspect the current
stack frame and registers, or evaluate `$r0` and `$sp`. Disassembly is available
through Cortex-Debug/DAP. Step Into reaches source lines 3, 4, 5 and 6; Continue
returns 42 with SP restored to `0x20010000` in the fixture.

Only one owned target session runs at a time. Stop before editing/rebuilding.
Stop/session termination, extension disposal and failed startup clean up the
owned Python process. Start a new session for a fresh CPU; Restart/reset and
changing register/memory contents are not supported by this RSP target.

## External adapter and execution control

The generated configuration uses `type: cortex-debug`, `request: attach`,
`servertype: external`, an ephemeral **127.0.0.1** port, and `loadFiles: []`.
Empty `overrideAttachCommands` removes the adapter's default `monitor halt`;
empty `overrideRestartCommands` avoids a default hardware reset sequence.
SWO, RTT and live watch are disabled. No OpenOCD, Flash load or hardware reset
is launched by this workflow.

Cortex-Debug selects extended-remote. The RSP target now acknowledges `!` for
this single already-created target; extended process launch/restart is not
implemented. Its opt-in `--interactive` mode polls raw Ctrl-C between bounded
1000-instruction chunks so Pause works without concurrent Unicorn access.
A 30-second execution cap also interrupts runaway execution; idle timeout is
300 seconds. The earlier default 100000-instruction/one-second bounded mode is
preserved for command-line regression tests. Both modes bind only loopback.

## Executed verification

The actual VS Code Extension Host ran the installed Cortex-Debug adapter, real
ARM GDB/MI2 and the actual generated ELF over TCP. Eight scenarios passed:
adapter activation; build/start; verified `.emb` breakpoint and editor position;
top frame/registers/disassembly; four source steps with editor positions;
result 42/restored stack; target cleanup; and Continue/Pause/resume/Pause in a
separate loop fixture. Execution controls use the real VS Code workbench commands.
This verifies editor API behavior; no human visual acceptance is claimed.

From `extensions/vscode`, after installing Cortex-Debug into an isolated
extensions directory, reproduce with:

```text
npm test
node test/run-debug-host.js "<absolute Code executable>" "<isolated extensions directory>"
```

The integration harness uses the repository's existing ignored `.tools` ARM GNU
and Python dependency directories; set `EMBEDLANG_TEST_PYTHON` to the Python
executable if it is not `python`. See the harness for those fixture paths.
Tests create isolated profiles/workspaces, do not alter normal editor settings,
and keep logs/results/generated artifacts ignored. Installed adapter/dependency
licenses remain in their installation; third-party packages are not vendored.
The [verification journal](report/VERIFICATION.md) records all 253 checks.

## Remaining limitations

Typed EmbedLang local/parameter debugging and complete stack unwinding are
**not supported**. Only a useful current frame is demonstrated; deeper frame
names/unwinding can be inaccurate. Step Over/Out across calls and comprehensive
source control-flow cases are not verified. The earlier Windows JDK/Cp1251
Unicode CLI-path limitation remains. Other OS/editor versions need acceptance.
Zed debugging and physical hardware debugging are not implemented or tested here.

Primary references: [Cortex-Debug](https://github.com/Marus/cortex-debug),
[configuration attributes](https://github.com/Marus/cortex-debug/blob/master/debug_attributes.md),
[VS Code debugger API](https://code.visualstudio.com/api/extension-guides/debugger-extension).
Existing [source mapping](SOURCE_DEBUGGING.md) and [RSP investigation](GDB_DEBUGGING.md)
documents describe the underlying proof and its boundaries.
