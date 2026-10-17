# EmbedLang requirements

## Objective

Implement a reliable frontend for a small high-level embedded systems language
as a university Embedded Systems Programming project. Kotlin implements the
compiler; ANTLR4 supplies the lexer/parser. The eventual target is ARM native
code on STM32F407, but native generation is outside this milestone.

## Acceptance criteria

| Requirement | Implementation / evidence |
| --- | --- |
| Requested project structure | `compiler/`, `examples/`, `docs/`, `tests/` |
| Gradle Kotlin project | Root/subproject Kotlin DSL, wrapper, JDK 17 |
| ANTLR4 integration | Tool and runtime 4.13.2, generated Java visitor |
| Lexer/parser | `EmbedLang.g4`; precedence, boundaries, error listener |
| AST / builder | Sealed Kotlin AST and parse-tree visitor |
| Semantic analysis | Function registration, nested scopes, built-ins, main |
| Type checking | Exact types, contextual literals, operands, calls, returns |
| Diagnostics | Stable error code, source filename, line, column |
| Unit tests | JUnit 5 suite under `tests/src/test/kotlin` |
| Documentation | README, language specification, architecture, requirements |
| Examples | `basic.emb`, `blink.emb`, checked by tests |

Required tests: valid variable declaration, type mismatch, undefined variable,
undefined function, invalid function argument type, missing return value,
if/while boolean conditions, valid function call, valid main. Additional tests
cover scopes, duplicates, all built-ins, integer ranges, return paths, operator
precedence, syntax errors, unsupported syntax, and analysis isolation.

## Supported language surface

Types: `i32`, `u32`, `u8`, `bool`, `void`. Constructs: local declarations,
assignments, arithmetic/comparison/boolean expressions, if/else, while,
functions, calls, return, mandatory main. Built-in signatures/constants are
specified in `LANGUAGE_SPEC.md` and implemented centrally in `Builtins.kt`.

## Explicit exclusions

No ARM generation, assembler, linker, flashing, GPIO execution, runtime, or
interpreter. No classes, objects, inheritance, generics, pointers, malloc/free,
garbage collector, strings, floating point, threads, exceptions, or modules.
Architectural changes must be explained before they are implemented.

## Build acceptance

From a clean checkout with JDK 17, `gradlew build` must generate the parser,
compile Java/Kotlin, and pass all tests. Both example files must pass the CLI.
Invalid input must fail with a diagnostic and nonzero exit code. The installed
CLI must run without a Gradle process using the generated application distribution.

## Verified milestone result

Verified on Windows with a portable JDK 17 and the checked-in Gradle 8.14.3
wrapper: `gradlew.bat --no-daemon clean build :compiler:installDist` passed.
The suite contains 34 passing tests. The installed CLI accepted both examples,
printed usage for `--help`, reported a source-located undefined-variable error
with exit code 1, and returned exit code 2 for a missing source file.

## Milestone 2: typed IR

Extend the working frontend without redesigning its AST, parser, type rules, or
diagnostics. The original 34 tests must continue to pass unchanged.

| Requirement | Implementation / evidence |
| --- | --- |
| Typed IR for v0.1 constructs | `embedlang.ir` sealed expressions/statements, structured blocks |
| AST-to-IR lowering | `IrLowerer`, gated by successful typed semantic analysis |
| Typed constants, locals, calls, operations | Recorded semantic types; resolved local/function symbols |
| Textual IR | Deterministic `IrPrinter`; snapshots for both examples |
| CLI emission | `embedlang --emit-ir program.emb`; original validation mode retained |
| IR generation tests | `IrTest`; type/binding/control-flow/error checks |
| CLI tests | `CliTest`; real entry-point subprocesses and exit codes |
| Pipeline documentation | `ARCHITECTURE.md`, `IR.md`, README |
| Future ARM package | `embedlang.backend.arm.ArmTarget`; metadata only |
| Target documentation | `ARM_TARGET.md`: STM32F407VGT6, Cortex-M4, ARMv7E-M, Thumb |

Acceptance: complete test suite passes, original tests remain intact, and IR for
`basic.emb` and `blink.emb` is emitted and shown. ARM generation, optimization,
runtime behavior, and changes to the v0.1 specification remain outside scope.

Verified milestone 2 result: a clean wrapper build and installed distribution
passed with 57 tests (34 frontend, 19 IR, 4 CLI), zero failures/errors/skips. The
installed `embedlang --emit-ir` command emitted both shipped examples, and the
original grammar, AST, language specification, and 34 test methods were unchanged.

## Milestone 3: ARM assembly text

Keep all 57 existing tests passing. Consume the unchanged IR in
`embedlang.backend.arm.ArmBackend`; emit GNU Thumb-2 assembly text for Cortex-M4.
Support scalar functions, register/stack parameters, return values, bound locals,
assignments, integer/bool constants, arithmetic, typed comparisons, boolean
operations, if/else, and while. Hardware built-ins call external `embed_*`
symbols; no STM32 implementation is supplied. Generated text for both examples
is checked in and regression-tested. `--emit-asm` has CLI success/error tests.

Register usage, stack alignment, frames, labels, local storage, runtime symbol
contracts, IR mappings, and execution policies are documented in `ARM_BACKEND.md`.
No frontend, AST, semantic-rule, IR, or language-specification redesign is needed.
Startup, linker scripts, flashing, GDB/editor integrations, and raw machine-code
emission remain excluded. Acceptance requires a complete passing test suite and
the generated assembly for both examples.

Verified result: 76 JUnit tests passed (all prior 57 plus 17 ARM tests and 2 CLI
tests). GNU ARM assembler accepted both examples. Fifteen optional Cortex-M4
emulation checks passed, including return values, nested/recursive calls,
stack arguments, arithmetic/control flow, and stack/callee-saved restoration.

## Milestone 4A: STM32 runtime and ITMO.cLAB preparation

A separate firmware layer combines generated assembly with pinned official
SDK_cLAB startup, RAM linker script, HAL initialization and trace/CRC. It supplies
all six runtime functions and all built-in board constants from SDK-1.1M sources.
The frontend, AST, IR, language specification and assembly emitter are unchanged.
The build produces ELF/BIN, checks symbol resolution and reserved memory bounds,
and records hashes and a memory report. A separate finite remote Blink returns
after about 2.5 seconds. Local Python tests exercise actual ARM runtime code with
HAL/trace stubs and selected official routines. Upload, flashing, credentials and
claims of hardware execution remain outside the performed work. See
`STM32_RUNTIME.md`, `ITMO_CLAB.md`, and `MILESTONE_4A_VALIDATION.md` for results.
