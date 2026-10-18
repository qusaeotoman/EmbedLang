# EmbedLang for Zed — local prototype

This document covers the original editing/task package. A separate optional
[Rust/WASM debugger extension](../../docs/ZED_DEBUGGING.md) now provides the
official Zed DAP API glue for standalone Eclipse CDT → ARM GDB → Unicorn.
Its build/protocol tests pass; actual **Zed 1.24.2 Windows** loading and local
source-debug acceptance are recorded in that guide.
The two packages coexist; the debugger has no grammar-fetch dependency.

This adds an editor-only Tree-sitter grammar, `.emb` association, comments,
bracket pairs, indentation and function outlines. Repository tasks build the
compiler, validate the saved file, and emit typed IR or Cortex-M4 assembly.
The Kotlin/ANTLR compiler remains authoritative; this tolerant editor grammar
does not enforce statement terminators or semantic rules. No strings are added.

## Compiler and tasks

Requirements: Node.js 22+, Java 17 and the existing Gradle wrapper. Open the
**EmbedLang repository root** as a Zed worktree. Configure `JAVA_HOME` before
starting Zed, or set `EMBEDLANG_JAVA` in your local terminal environment to the
Java executable. An alternate installed distribution can be selected with
`EMBEDLANG_COMPILER_DIRECTORY`. Keep personal paths out of tracked files.

The tracked [`.zed/tasks.json`](../../.zed/tasks.json) uses Zed's task schema,
not VS Code's `tasks.json` / `problemMatcher` schema. Run **task: spawn**, then:

1. **EmbedLang: Build compiler distribution** → `:compiler:installDist`.
2. Open an `.emb` file; **EmbedLang: Validate saved file**.
3. **EmbedLang: Emit typed IR** / **EmbedLang: Emit ARM assembly**.

File tasks request `save: current`; build requests `save: all`. Diagnostics are
the compiler's original `file:line:column: ... [CODE]: message` in the task
terminal. Zed supports Ctrl+Click (Cmd+Click on macOS) navigation for such paths.
Paths with spaces may depend on terminal path detection; use Go to Line manually
if a link is not recognized. Columns are the CLI's one-based Unicode code-point
columns. This task workflow does **not** publish LSP diagnostics or populate an
integrated Problems list, and it does not validate on each edit/save automatically.
That requires a future language-server adapter. No unsupported problem matcher
is presented as a solution.

Successful emissions are printed and saved to ignored
`build/zed/<source-relative-path>.ir` / `.s`. A failed emission writes nothing;
an earlier successful output may remain and must not be mistaken for a fresh
build. Source filenames travel through `ZED_FILE`, not shell interpolation.
Java is launched with an argument array, a 15-second timeout and bounded output.
The build task has a five-minute process limit. Tasks execute local project code;
review it and trust the worktree before running them. No task programs hardware.

Equivalent PowerShell workflow, from the repository root:

```powershell
node extensions/zed/task.js build
$env:ZED_FILE = (Resolve-Path examples/basic.emb).Path
node extensions/zed/task.js validate
node extensions/zed/task.js ir
node extensions/zed/task.js asm
```

## Build the highlighting package

Install pinned tools locally in `extensions/zed`:

```powershell
npm.cmd ci
# Extract an official WASI SDK and set its root, containing bin/clang.exe:
$env:WASI_SDK_PATH = 'YOUR_WASI_SDK_DIRECTORY'
npm.cmd run build
npm.cmd test
```

Alternatively set `ZIG` to the **absolute path** of a portable **Zig 0.13.0**
executable and leave `WASI_SDK_PATH` unset. Obtain the archive for your OS from
the [official download index](https://ziglang.org/download/); extract it with
its adjacent `lib` directory intact. This is the path verified on this machine:

```powershell
$env:ZIG = 'YOUR_ZIG_DIRECTORY/zig.exe'
npm.cmd run build
npm.cmd test
```

The build uses Zig's bundled WASI headers without linking its application
startup or C runtime. Versions and the actually
executed build/test results are recorded in
[VERIFICATION.md](../../docs/report/VERIFICATION.md).
Generated parser C/headers, WASM, dependencies and packages remain ignored.
The local package is `extensions/zed/build/embedlang/`, containing its manifest,
language configuration, queries and `grammars/embedlang.wasm`.

### Unpublished local installation

This package remains unpublished and its dev-builder source revision is not
configured. The editor/report sources were preserved locally in commit `40fa242`.
Zed's **Install Dev Extension** builder fetches a Git revision for grammars;
using that builder requires a real local or published source pin **containing
the generated `src/parser.c` and headers**. Those generated inputs are currently
ignored and absent from the preserved commit. **Do not use that button on this
prototype**: the empty `rev` is intentional and is not a released source pin.

For a local test, close Zed and copy the **contents of the built package** into
its unpacked installed-extension directory:

- Windows: `%LOCALAPPDATA%/Zed/extensions/installed/embedlang/`
- Linux: `${XDG_DATA_HOME:-$HOME/.local/share}/zed/extensions/installed/embedlang/`
- macOS: `~/Library/Application Support/Zed/extensions/installed/embedlang/`

Do not overwrite another installed EmbedLang extension; move it aside first.
Restart Zed, open `examples/basic.emb`, confirm the language selector reads
**EmbedLang**, then check highlighting, comments, bracket insertion, indentation,
function outline and task navigation. Remove only this package directory to
uninstall. No installer is run automatically by this project. This unpacked
workflow follows the runtime loading layout in Zed's official source; it is
not an Extension Gallery installation. Enabling the normal dev-extension builder
later requires agreeing on a source package with generated parser inputs and
pinning its revision, then testing that route. Setting `rev` alone is insufficient.
The current unpacked workflow remains available; publication is not required.

Actual Zed 1.24.2 acceptance used separate unpacked editing/debugger packages in
an isolated user-data profile. Recognition, highlighting, matched function braces
and successful **Validate saved file** were observed. The task picker also listed
Build/IR/ASM; these commands retain automated tests, but were not each run through
the UI. Automatic bracket insertion, outline and terminal-link navigation were
not established by this acceptance. Component tests remain distinct evidence.

## Limits and provenance

No LSP, completion, rename, formatter, GDB/DAP integration, TCP/IP stepping,
firmware build/flash command or remote service is added. GNU firmware builders
remain separate. Linux/macOS are not tested here. Tasks reuse
`extensions/vscode/src/compiler.js`, a pure Node adapter without VS Code APIs;
installing the prebuilt highlighting package alone does not install the compiler.

The grammar and queries are project sources. Development dependencies
`tree-sitter-cli` and `web-tree-sitter` are MIT; their original notices remain in
node_modules. [TREE_SITTER_LICENSE](TREE_SITTER_LICENSE) accompanies the generated
parser package. Portable toolchains are external development dependencies and
are not redistributed. No new project-wide license is assigned.

Official implementation references, inspected 2026-10-17:

- [Language configuration, grammar and queries](https://zed.dev/docs/extensions/languages)
- [Dev extensions and WASI compilation](https://zed.dev/docs/extensions/developing-extensions)
- [Task fields, variables and saving](https://zed.dev/docs/tasks)
- [Terminal source navigation](https://zed.dev/docs/terminal#path-hyperlinks)
- [Installed extension directories](https://zed.dev/docs/extensions/installing-extensions)
- [Zed grammar builder](https://github.com/zed-industries/zed/blob/main/crates/extension/src/extension_builder.rs)
- [Zed runtime grammar loading](https://github.com/zed-industries/zed/blob/main/crates/extension_host/src/extension_host.rs)
