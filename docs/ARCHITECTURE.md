# Compiler architecture

## Milestone design

The repository uses one JVM compiler subproject in a root Gradle Kotlin DSL
build. It targets JDK 17. Tests live in the requested root `tests/` directory and
are included in the compiler test source set. Root `build` delegates to the
compiler assembly and checks. Milestone 2 extends the existing frontend with
typed, structured IR. Milestone 3 adds a stack-based Thumb-2 text emitter in the
ARM package, while preserving the frontend, semantic rules, and IR.

```text
UTF-8 source
  → ANTLR lexer / parser
  → parse tree
  → Kotlin AstBuilder
  → source-located AST
  → SemanticAnalyzer
  → typed analysis result (or diagnostics)
  → IrLowerer
  → typed, structured IR
  → IrPrinter / ArmBackend
  → typed IR text / GNU Thumb-2 assembly text
```

## Components

- `compiler/src/main/antlr/EmbedLang.g4` defines tokens, statement boundaries,
  syntax, and operator precedence. Gradle generates Java lexer/parser/visitor
  classes in package `embedlang.parser`, under the compiler build directory.
- `embedlang.ast` defines immutable data classes and sealed interfaces for
  programs, functions, statements, expressions, and source locations. The AST has
  no dependency on generated parser types.
- `embedlang.frontend.AstBuilder` converts successful parse trees into the AST.
  It folds binary chains left and records one-based locations.
- `embedlang.frontend.Frontend` provides `parse` and `analyze` APIs. Lexical and
  parser errors share a diagnostic listener. Syntax errors prevent AST construction
  and semantic analysis, avoiding analysis of a recovered invalid tree.
- `embedlang.semantic.Builtins` is the single signature and constant-type table.
- `embedlang.semantic.SemanticAnalyzer` first registers all functions, validates
  main, then checks bodies using nested scopes. Each call uses fresh state.
  It validates declarations, references, calls, operands, integer ranges,
  assignments, conditions, return types, and function fallthrough.
  `analyze(program)` retains the original diagnostics-only API. The additive
  `analyzeTyped(program)` API records resolved expression types in a per-analysis
  identity map, without changing type rules or mutating the AST.
- `embedlang.semantic.TypedAnalysisResult` associates type facts with the exact
  AST instance checked. Signed literal chains are checked and recorded as a whole.
- `embedlang.ir` defines sealed IR statements/expressions, local identities, and
  resolved function symbols. Types and source locations reuse existing AST value
  types; IR nodes contain no AST expressions or ANTLR contexts.
- `embedlang.ir.IrLowerer` accepts only successful typed analysis. It registers
  function symbols before bodies, resolves locals with nested scopes, normalizes
  signed literals, and copies analyzed types onto expressions. It does not infer
  types, optimize, allocate registers, or emit target instructions.
- `embedlang.ir.IrPrinter` produces deterministic, human-readable textual IR.
- `Frontend.lower(source, file)` composes parsing, typed analysis, and lowering;
  syntax or semantic errors return diagnostics with no IR.
- `embedlang.MainKt` is the CLI. It reads one file, prints diagnostics to stderr,
  and returns a process exit code. `--emit-ir` prints textual IR to stdout. The
  normal check-only mode remains unchanged. `--emit-asm` invokes the ARM emitter.
  It produces text only, not machine code or firmware images.
- `embedlang.backend.arm.ArmTarget` names the intended STM32F407VGT6 target.
  `ArmBackend.emit` emits functions, stack frames, typed instructions, labels,
  and external runtime calls. It uses no frontend changes or IR transformations.

## Type checking

Declared types are exact. Literals are contextually typed with `BigInteger`
range checks, preventing host overflow. A lightweight peek at typed expression
leaves chooses the numeric type before literals are checked. This handles
`1 + counter`, nested arithmetic, and function-argument literal contexts without
adding an implicit conversion rule. Error recovery keeps checking independent
statements; unresolved expressions use a null error type to reduce cascades.

Return-path analysis is deliberately conservative: returns and literal infinite
loops terminate, if/else terminates only when both branches do, and ordinary
while loops may execute zero times. There is no optimizer or constant evaluator.

## Verification and extension boundary

JUnit 5 tests exercise the public frontend APIs, AST precedence, scopes, built-ins,
literal boundaries, diagnostics, malformed input, and every shipped example.
IR tests check type preservation, resolved bindings, shadowing, call targets,
structured control flow, locations, and exact example snapshots. CLI tests run
the actual entry point in a separate JVM and verify output and exit codes.
Generated code is rebuilt on clean builds and is not committed.

The IR is structured rather than SSA or a control-flow graph. This is an additive
stage; the grammar, AST model, semantic rules, and original 34 tests are retained.
Future control-flow lowering, optimization, ARM generation, and STM32F407 runtime
bindings must be explained before implementation. See `IR.md` and `ARM_TARGET.md`.
The first ARM emitter and its execution policies are documented in
`ARM_BACKEND.md`.

## Milestone 4A firmware boundary

The compiler still emits assembly text. A separate `firmware/build.py` layer
assembles it with ARM GNU GCC, renames object symbol `main` to
`embed_program_main`, and links the official cLAB startup/runtime with one C
entry wrapper. It produces ELF and raw BIN plus a checked memory-layout report.
No AST, IR, frontend or compiler-backend changes are needed for this integration.

```text
EmbedLang --emit-asm → program.s → program.o (entry symbol renamed)
  + C board wrapper + EmbedLang HAL runtime + pinned official startup/HAL/trace
  → GNU linker with official cLAB RAM script → firmware.elf → objcopy → firmware.bin
```

`firmware/vendor` contains attributed, checksummed official source snapshots.
`firmware/src` contains the adapted main wrapper and the board-specific ABI
implementation. `firmware/tools/verify.py` rejects images outside the RAM loader
contract. Python integration tests verify runtime behavior and generated firmware
separately from portable compiler JUnit tests. Upload remains a manual operation
outside the build. See `STM32_RUNTIME.md` and `ITMO_CLAB.md`.

Firmware builds now default to the hardware-tested reference's Debug compiler
and linker flags. `--diagnostic probe` calls a pure generated function from the
C wrapper and checks its return; `--diagnostic blink` brackets generated main.
Both use bounded official PRINT/P0 markers after initialization and before
normal trace finalization. This instrumentation is confined to the C firmware
layer; grammar, AST, IR and ARM emission are unchanged.

The optional recovered probe adds two firmware-only gates: normalization of the
pinned HAL's confirmed identical-active-PLL false error after exact readiness
and parameter checks, then complete initialization/live-state validation before
generated code. It retains the raw HAL error in diagnostics and keeps all other
failures fatal to application execution. It does not alter default language or
backend behavior. See `CLAB_PLL_RECOVERY.md`.

`--diagnostic blink-recovered` selects those same two gates and the existing
marked wrapper, then calls compiler-generated finite Blink main. Only build
selection changes; the recovery implementation and runtime are shared unchanged
with the physically verified probe. See `CLAB_BLINK.md`.

## Local F427 Flash and OLED runtime

`firmware/build_local.py` uses a separate Flash profile, F427 startup and
capacity-adjusted linker script, with the existing object-entry renaming and
typed calling convention. Its local wrapper retains hardware-tested 168 MHz
cold-start initialization, leaves the software watchdog unstarted, and idles
after generated main returns. Existing Blink and cLAB outputs are separate.

Opt-in `--oled --mcu stm32f427vit6` adds the official SDK_OLED framebuffer/font
driver, blocking I2C HAL and a small local adapter. Five new scalar built-in
signatures use existing typed call lowering and ARM emission. The generated
EmbedLang program supplies ASCII characters; no string type, grammar change or
new IR node is introduced. Only the official driver's I2C calls are redirected
at compile time to capture errors otherwise discarded by that driver. The
OLED profile produces `firmware/build/local_oled_f427`, leaving the verified
Blink outputs intact. See [hardware mapping and verification](LOCAL_OLED.md).

## Milestone 6: VS Code adapter

`extensions/vscode` is an independent, dependency-free runtime adapter plus a
declarative TextMate grammar and language configuration. It invokes the existing
installed compiler's Java CLI entry point with argument arrays and no shell.
The compiler/frontend/AST/IR/ARM emitter and firmware remain unchanged. This is
not a language server: validation reads a saved local file, and emission opens
an untitled preview rather than writing firmware or overwriting source.

The adapter translates one-based CLI point diagnostics into VS Code ranges,
including Unicode code-point to UTF-16 conversion, preserves diagnostic codes,
and drops results from stale document versions. It clears errors on edit/close,
supports per-document workspace settings, bounds execution time/output, and
does not run compiler processes in an untrusted workspace. Syntax configuration
continues to work there. Development dependencies are used only for tests and
local packaging, not included as runtime dependencies.

The local extension has unit/TextMate, real CLI, and actual Extension Development
Host tests, including a separate Restricted Mode run. See the
[extension guide](../extensions/vscode/README.md) and
[living academic report](report/REPORT.md). No debugger or hardware
execution is added by the VS Code milestone. Future milestones should update the report
and its verification journal while preserving the students' personal sections.

## Zed editor adapter

`extensions/zed/tree-sitter/grammar.js` is a tolerant editor parser compiled to a
Tree-sitter WASM module, with Zed language configuration and highlighting,
bracket, indent and function-outline queries. It does not replace ANTLR or alter
the accepted language: missing statement separators are tolerated while editing,
and the original compiler still validates the saved source.

`.zed/tasks.json` invokes a small Node runner for compiler build, validation,
IR and assembly. It reuses the pure CLI process adapter from
`extensions/vscode/src/compiler.js`, without importing any VS Code API. Source
paths pass via the environment; the Java compiler executes without a shell.
The Gradle wrapper build is a separate fixed command. Successful emissions go
to ignored `build/zed`; errors preserve CLI locations/exit codes in the terminal.
These tasks do not publish LSP diagnostics or implement a debugger.

The unpublished local package is compiled before installation into Zed's
unpacked-extension layout. No grammar Git revision is invented or committed;
normal dev-extension fetching awaits an approved source revision. Component
verification alone does not establish Zed UI loading. Subsequent Zed 1.24.2
acceptance confirmed unpacked loading, highlighting and Validate; see
[setup and limitations](../extensions/zed/README.md).

## Milestone 7 investigation: isolated debug transport

`tools/debug/unicorn_rsp.py` is CPU-test scaffolding outside the compiler and
firmware pipeline. A small loopback-only RSP endpoint exposes a bounded Unicorn
Cortex-M4 instance to real ARM GDB. The probe ELF is compiled/assembled separately
under ignored `build/gdb-poc`; it does not run STM32 initialization or peripherals.
`tests/gdb_connection_checks.py` proves symbol breakpoints, instruction stepping,
register/memory reads and result/stack restoration over TCP.

The initial PoC introduced no DAP adapter or `.emb` debug metadata. The available ARM GDB
supports MI but lacks native DAP, affecting the Zed adapter choice. See the
[evidence and editor plan](GDB_DEBUGGING.md). Current RSP success is neither
editor-debug success nor physical hardware validation.

## Optional EmbedLang source-line metadata

The later `--emit-asm --debug-lines` option enables `ArmBackend.emit` metadata
without changing default output or the IR. Existing SourceLocation values map
statement starts to GNU `.loc` rows and deterministic `.file` entries. The CLI
resolves source paths from its own cwd; UTF-8 path bytes are escaped into ASCII
assembly so the console encoding cannot corrupt filename metadata.

Function setup/teardown and synthetic branches carry non-statement rows at
their original function/control locations. GNU as generates line/CU sections
when assembling with debug information enabled. Generated instructions/frame
storage remain byte-identical; CFI, typed local/parameter DIEs and editor debug
adapters are not added. See [source-line verification](SOURCE_DEBUGGING.md) for
real GDB file/line breakpoints and `step` over the existing local RSP server.

## VS Code local debug integration

The optional editor command builds a separate CPU-only debug ELF and owns a
loopback Unicorn RSP child process. The maintained Cortex-Debug adapter supplies
DAP → GDB/MI2 translation; there is no new compiler stage or custom DAP adapter.
External attach suppresses default monitor/reset/load commands. Source/workspace
trust is checked before execution; session termination/disposal cleans up the
owned target. Interactive RSP execution polls interrupts between bounded chunks,
while the old default bounded mode remains available for regression tests.

Real VS Code workbench commands and source editor positions are tested through
the Extension Host. Registers, disassembly and the current stack frame are
available; typed locals and complete unwinding remain unsupported. See
[setup, executed tests and limits](VSCODE_DEBUGGING.md). Firmware profiles and
the compiler/AST/IR/backend are unchanged by this editor integration.

## Zed debug API glue

The separate `extensions/zed/debugger` package implements Zed's published Rust
extension API 0.7.0 `get_dap_binary` and `dap_request_kind` hooks. Its WASI module
starts the standalone Eclipse CDT target adapter over stdio; the existing ARM
GDB/MI and localhost Unicorn RSP target execute the generated source-mapped ELF.
This does not depend on the VS Code Cortex-Debug extension. The original Zed
highlighting/task package remains separate and unchanged.

Preparation reuses the pure Node CPU-image builder, then writes an ignored local
`.zed/debug.json`, preserving any existing user configuration. CDT owns the
ephemeral loopback server and cleanup. Protocol tests, actual API compilation
and WASM export/version inspection passed. Subsequent actual Zed 1.24.2 Windows
acceptance confirmed source breakpoints/steps, Continue/Pause, registers, useful
stack entries, result 42 and cleanup. That check found a packaging defect:
current Zed requires a **wasm32-wasip2 component**, not the earlier wasip1 core
module. The target/package validator now enforces this format. API glue and
compiler/firmware stages were unchanged. See [reproduction and observed UI
limits](ZED_DEBUGGING.md).
