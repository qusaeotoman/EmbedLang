# Zed: local EmbedLang source debugging

Status recorded **2026-10-18**: actual Windows **Zed 1.24.2** acceptance confirms
both unpacked extensions load, highlighting/bracket matching, the Validate task,
`.emb:2` breakpoint, source steps 3–6, Continue/Pause/resume, registers, useful
stack entries, result **42**, restored SP and target cleanup. Disassembly was
inspected through the GDB console, not a dedicated UI pane. The earlier
build/protocol-only milestone did **not** prove editor loading; its core-WASM
packaging defect was found and corrected during this acceptance. Typed locals,
complete unwinding and hardware debugging remain unsupported.

The preceding VS Code milestone is preserved at
`b4bd308d56685035d35267241c5fbc2fb41aba33`. The reviewed Zed implementation is
preserved as `cca8b36cf34ac0e334ec2a7d4300ca8328e0a629`.

## Windows installation history and actual acceptance, 2026-10-18

No Zed was found on PATH, in standard LocalAppData/Program Files locations,
in current-user or machine uninstall records (including 32-bit records), or
among running processes. A portable copy at an unknown custom path is not ruled
out. Winget was available. This describes the check before approved installation.

After explicit approval, the official Windows installation command is:

```powershell
winget install -e --id ZedIndustries.Zed
# In a fresh terminal after installation:
zed --version
```

This command comes from [Zed's official Windows guide](https://zed.dev/docs/windows).
The user subsequently approved installation and the package's declared machine
scope/UAC. The current-user-only attempt had no applicable installer; the exact
command above then installed official stable **1.24.2**, commit
`fb69067729cb16a7f6135e2c1600c26a28c59659`. No drivers were changed. Acceptance
used a separate ignored `--user-data-dir` profile, leaving the normal profile
untouched. The user handled project trust for this repository only.

Zed initially rejected the old `wasm32-wasip1` core module with
`attempted to parse a wasm module with a component parser`. Zed 1.24.2's
[official extension builder](https://github.com/zed-industries/zed/blob/v1.24.2/crates/extension/src/extension_builder.rs)
uses **wasm32-wasip2**. Only extension packaging/target and its regression test
changed; compiler, firmware, API glue and adapter behavior were preserved.
The corrected component is **206,091 bytes**, SHA-256
`d3a3b865c1370027c37ae9345d83f829fa2bbd43fca14550dad7c30509117a43`.
Packaging now rejects a core module before installation.

The existing built local packages can be used without installing a new compiler
toolchain. With Zed closed, copy their contents to distinct unpacked directories
as described in the checklist; preserve any existing extension directories first.
Regenerate the arithmetic ELF/configuration before starting: automated tests
also build a loop fixture into the shared CPU-image output, so a leftover test
ELF must not be assumed to match the source currently open in the editor.

## Architecture

```text
Zed DAP client → EmbedLang Debugger extension (Rust/WASM API glue)
             → Eclipse CDT target adapter (stdio DAP)
             → ARM GDB/MI → loopback TCP RSP → Unicorn Cortex-M4
```

The separate `extensions/zed/debugger` extension registers `EmbedLang GDB` in
`extension.toml` with a configuration schema. Its `get_dap_binary` and
`dap_request_kind` hooks implement the official published `zed_extension_api`
**0.7.0**, using `DebugAdapterBinary` and `StartDebuggingRequestArguments`.
It launches Node and the standalone **cdt-gdb-adapter 1.10.0** target adapter.
The VS Code Cortex-Debug extension is not used by Zed. No custom DAP translator
is implemented here. The extension does not download dependencies at runtime.

The original Zed highlighting/task package is preserved separately. The debugger
package has no grammar revision dependency. It can coexist with that package.
The compiler, AST, IR, source-line mapping, ARM backend and firmware are unchanged.

The preparation command reuses the tested pure Node CPU-image builder from the
VS Code integration; it has no VS Code API dependency. Its existing output name
is `build/vscode-debug/program.{s,o,elf}`, including when called from Zed. This
shared output means **stop all local debug sessions before rebuilding or switching
editors**, and use one source/image at a time.

The ELF uses `.text` at `0x10000`, synthetic RAM and a return sentinel. It is not
a firmware image. No HAL/GPIO/OLED/watchdog model or physical board is involved.
Hardware runtime symbols are intentionally not supplied; use pure CPU fixtures.

## Reproduce the build

Requirements: Node.js 22+, JDK 17, ARM GNU as/ld/GDB, Python with
`pip install -r firmware/requirements-tests.txt`, and Rust with `wasm32-wasip2`.
Verified: Rust **1.90.0 GNU Windows host**, ARM GNU **13.3.Rel1 / GDB 14.2.90**,
Unicorn **2.1.4**, Node **24.13.0**. Other platforms/editor releases need acceptance.

From the repository root:

```powershell
.\gradlew.bat --no-daemon :compiler:installDist
cd extensions/zed
npm ci --ignore-scripts
cd ../..
rustup toolchain install 1.90.0 --profile minimal --target wasm32-wasip2
cargo +1.90.0 build --locked --manifest-path extensions/zed/debugger/Cargo.toml --target wasm32-wasip2 --release
cargo +1.90.0 test --locked --manifest-path extensions/zed/debugger/Cargo.toml
node extensions/zed/debugger/package.js
```

On Windows without Visual Studio C++ Build Tools, use a GNU Rust host with MSYS2
MinGW-w64 GCC on PATH: replace `1.90.0` above with
`1.90.0-x86_64-pc-windows-gnu`. This is the build executed here. On Linux/macOS
use the normal native host toolchain and `./gradlew`.

`--ignore-scripts` avoids CDT's optional Linux native-console build; that console
is disabled in this workflow. The old Tree-sitter CLI may need its original
installation step (`npm rebuild tree-sitter-cli`) if building the highlighting
package after a fresh install. Do not enable unrelated dependency scripts blindly.

Build output:
`extensions/zed/debugger/target/wasm32-wasip2/release/embedlang_debugger.wasm`.
Unpacked install package: `extensions/zed/build/embedlang-debugger/` with
`extension.wasm`, manifest and schema. All are ignored build artifacts. The
Cargo and npm lockfiles are source-controlled reproducibility inputs.

## Generate machine-local debug settings

Set these environment values to **absolute paths** on your machine; placeholders
below are not working paths. Do not commit personal settings:

```powershell
$env:EMBEDLANG_ARM_BIN = 'YOUR_ARM_GNU_BIN_DIRECTORY'
$env:EMBEDLANG_PYTHON = 'YOUR_PYTHON_EXECUTABLE'
$env:EMBEDLANG_CDT_ADAPTER = (Resolve-Path extensions/zed/node_modules/cdt-gdb-adapter/dist/debugTargetAdapter.js).Path
# Optional: local Python modules, alternate Java/compiler distribution:
# $env:EMBEDLANG_PYTHON_MODULES = 'YOUR_LOCAL_PYTHON_DEPENDENCY_DIRECTORY'
# $env:EMBEDLANG_JAVA = 'YOUR_JAVA_EXECUTABLE'
# $env:EMBEDLANG_COMPILER_DIRECTORY = 'YOUR_INSTALLED_COMPILER_DISTRIBUTION'
node extensions/zed/debug.js tests/fixtures/source_debug.emb
```

This builds the saved source with actual `.emb` DWARF metadata and writes the
ignored **`.zed/debug.json`**, an array containing `adapter: "EmbedLang GDB"`
and a local launch scenario. It captures the current absolute Node, Python,
GDB, adapter and source-image paths. Keep them private; regenerate after moving
the repository. The helper refuses to overwrite any existing `.zed/debug.json`.
Preserve or merge existing scenarios yourself; to regenerate a known generated
file, move it into an ignored build directory first. It does not launch a target.
Rebuild after source edits; do not debug stale ELF/source combinations.

CDT launches our Python target on port **0**, reads its `RSP_READY` port, connects
GDB to `127.0.0.1`, and owns target cleanup. `run: "preserve"` keeps the target
stopped during configuration. There are no image load/monitor/reset scripts.
`target.automaticallyKillServer` is enabled. DAP travels over stdio; **the RSP
TCP port is not a Zed `tcp_connection` DAP endpoint**. The Rust hook rejects a
TCP DAP override and non-loopback target configuration.

## Reproducible Zed acceptance checklist

1. Install a current Zed release supporting debugger extensions/API 0.7.0. Record
   its exact version/OS. Install the existing EmbedLang highlighting package by
   [its separate instructions](../extensions/zed/README.md). Check `.emb` recognition.
2. Close Zed. Copy the **contents** of the built `embedlang-debugger` package into
   its own unpacked extension directory, without overwriting another installation:
   Windows `%LOCALAPPDATA%/Zed/extensions/installed/embedlang-debugger/`;
   Linux `${XDG_DATA_HOME:-$HOME/.local/share}/zed/extensions/installed/embedlang-debugger/`;
   macOS `~/Library/Application Support/Zed/extensions/installed/embedlang-debugger/`.
   Restart Zed. This unpacked layout was validated in an isolated Windows profile.
   Alternatively try **Install Dev Extension** on `extensions/zed/debugger` with
   the required Rust environment. This separate package has no grammar fetch;
   the dev-builder route is also untested here.
3. Open the repository as a trusted worktree. Ensure the generated `.zed/debug.json`
   points to the freshly built arithmetic fixture. Open `tests/fixtures/source_debug.emb`.
   Put the caret on **line 2** and press **F9**; a red gutter marker should appear.
   This route was validated; mouse gutter-click behavior was not established.
4. Run **debugger: start** and select **EmbedLang: local source debug**. Check that
   startup succeeds and the breakpoint becomes verified. The preserved initial
   stop may precede it: press **Continue**, then confirm the editor stops on line 2.
5. Use source **Step Into** four times; expect lines **3, 4, 5, 6**. Check the
   current stack frame, Register scope and disassembly if that Zed release exposes
   them. Protocol availability does not guarantee UI widgets in every release.
6. Remove/disable the breakpoint and Continue to the synthetic return stop.
   Select the current frame; evaluate **`$r0`** (42) and **`$sp`** (`0x20010000`).
   CDT requires a selected frame for evaluation. The sentinel has no `.emb` line.
7. Stop the session. Confirm the owned Python/GDB processes terminate and the
   logged RSP port is closed. Start a new session for fresh CPU state; Restart
   is not implemented by this target.
8. For Pause/resume, use the test-created `build/zed-debug/pause.emb`, or create
   an equivalent pure CPU program with `while true { x = x + 0 }`. Preserve the
   old generated config, rerun the preparation command for this file, and launch
   its scenario. Continue → Pause → Continue → Pause should stop in that `.emb`
   file. Stop afterward. Interactive execution has a 30-second run cap and
   300-second idle timeout; this is not unlimited real-time execution.
9. Record version, breakpoint status, source lines, register result, Pause and
   cleanup observations in the Russian verification journal. If installation or
   UI behavior fails, preserve the error and diagnose it before claiming acceptance.

## Automated evidence and limits

Run from the root with the environment above:

```powershell
node --test extensions/zed/test/debug.test.js
node --test extensions/zed/test/wasm.test.js
# Existing highlighting/task checks:
npm --prefix extensions/zed test
```

The protocol tests use the **actual pinned CDT adapter**, ARM GDB/MI and the
loopback Unicorn target, not a simulated DAP adapter. They verify a `.emb`
breakpoint with a path containing spaces/`&`, source stepping 3–6, top frame,
register scope, disassembly, 42/restored SP, two Pause/resume cycles, failed
startup reporting and target cleanup after disconnect. The WASM test checks real
component format, embedded exports and `zed:api-version` bytes, including rejection
of the old core-module artifact. Rust tests exercise API configuration conversion
and validation. These tests are separate from the actual UI acceptance below.

### Actual Windows UI observations

- Language selector **EmbedLang**, colored keywords/types/numbers and matched
  function braces. Automatic insertion was not established by the input helper.
- The task picker lists Build/Validate/IR/ASM; **Validate saved file** ran and
  reported two checked functions. IR/ASM tasks are covered by automated tests,
  not separately claimed as UI acceptance here.
- F9 set the source breakpoint; Continue hit line 2. Four Step Into actions
  highlighted lines 3, 4, 5 and 6. Source-probe/main stack entries and Register
  scope were visible. At the return sentinel, select the `??` top frame before
  evaluation: `$r0` displayed **42**, `$sp` displayed **0x20010000**.
- `>x/5i $pc` in the console displayed ARM instructions. No dedicated disassembly
  pane was found. The expected synthetic return SIGTRAP is not a hardware fault;
  its unmapped frame can leave an earlier source line selected.
- On the separate loop fixture, Continue/Pause/resume/Pause stopped on line 3
  twice. Stop reported GDB/server exit; owned processes disappeared and the
  captured ephemeral TCP port refused connections.

Nonfatal UI limitations observed: CDT expression-completion requests returned
null and Zed logged a completion error; Windows GDB emitted a character-set
warning during partial console input. Explicit expressions and commands worked.

Typed EmbedLang locals/parameters, complete stack unwinding, arbitrary source
control-flow cases and Step Over/Out across calls are not demonstrated. Windows
JDK/Cp1251 Unicode CLI path limitations remain. No hardware debug, Flash, network
laboratory access or publication was performed. The normal user Zed profile
was not modified by the isolated acceptance setup.

CDT is an external EPL-2.0 dependency; Zed's API crate is Apache-2.0. The package
retains API attribution/license, and the WASM incorporates API/runtime dependencies.
Original transitive notices remain in the local Cargo registry/toolchain; a future
public binary release needs their complete applicable notice bundle. Adapter
binaries, vendored crates and toolchains are not bundled. See the package's
THIRD_PARTY.md. No new project-wide license is assigned; nothing is published.

Primary references (checked 2026-10-18):
[Zed debugger extension API](https://zed.dev/docs/extensions/debugger-extensions),
[published API 0.7.0](https://docs.rs/zed_extension_api/0.7.0/zed_extension_api/trait.Extension.html),
[Zed debug configurations and controls](https://zed.dev/docs/debugger),
[Eclipse CDT adapter](https://github.com/eclipse-cdt-cloud/cdt-gdb-adapter).
See [VERIFICATION.md](report/VERIFICATION.md) for exact executed results.
