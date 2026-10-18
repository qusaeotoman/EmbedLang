# Minimal EmbedLang source-line debugging

Local continuation of Milestone 7, verified 2026-10-17. The preceding GDB/RSP
proof was preserved as `848a38ecbd6ee445cdf12db95b97e3b47f0bcc4a`; its checkout
was clean before this work. These source-line changes are now preserved as
`87807cefcb7eb96445ab79cb8f5c162a53ef5681`. This document records that milestone;
the later [VS Code integration](VSCODE_DEBUGGING.md) is separate, uncommitted
work. No hardware debugging has been added.

## Generate and assemble

Build the installed compiler distribution, then request the optional mode:

```text
embedlang --emit-asm --debug-lines path/to/program.emb
```

On Windows, for example:

```powershell
./gradlew.bat :compiler:installDist
./compiler/build/install/embedlang/bin/embedlang.bat --emit-asm --debug-lines tests/fixtures/source_debug.emb
```

The CLI prints assembly. Capture it using a UTF-8-capable file writer; keep
generated files in an ignored build directory. Filename directives are ASCII
even for Unicode metadata: UTF-8 bytes are C-octal escaped. Quotes, backslashes
and control characters are escaped too.

Assemble using GNU ARM tools with debug information enabled, for example
`arm-none-eabi-as -mcpu=cortex-m4 -mthumb -g --gdwarf-4 -o program.o program.s`,
then link to the appropriate layout. The assembler supplies DWARF line/CU
sections; this is not a complete typed debug-information generator. Tests use
an isolated ELF linked at `0x10000`, matching the existing Unicorn PoC,
**not a board firmware layout**.

Original `--emit-asm` output remains unchanged. Existing firmware builders,
editor commands, startup/runtime, AST, type rules and IR are unchanged. Builders
do not automatically opt into the new mode; previously built hardware-tested
ELFs are not retroactively given `.emb` mappings.

## Mapping policy

- CLI paths resolve to absolute normalized paths from the compiler cwd, with
  platform-appropriate slash handling. Assembler cwd does not determine where
  GDB finds the source. Symlinks are not resolved; source paths must remain
  available or be remapped in GDB.
- `ArmBackend.emit(program, debugLines = true)` reuses IR SourceLocation.
  Direct API callers retain the filenames supplied in their IR.
- `.file` numbers are deterministic. `.loc` records original one-based statement
  line/column positions and `is_stmt 1`. Generated `.s` lines do not replace them.
- Prologue/epilogue map to the function definition with `is_stmt 0`; the epilogue
  also has `epilogue_begin`. Generated branches/backedges use the associated
  control statement with `is_stmt 0`. GNU as omits line-zero rows, so line zero
  is deliberately not used to exclude instructions.
- Expressions share their statement's location. Blank/comment/brace lines need
  no row. Not every textual line is an executable breakpoint location.
- No instruction, frame or ABI changes; no typed locals or CFI/unwind metadata.

## Reproduce the ELF and real-GDB tests

Use Java 17/JDK, the installed compiler, ARM GNU as/ld/GDB and existing Python
dependencies from `firmware/requirements-tests.txt`. Set `JAVA_HOME` and put
tools on PATH, or supply their paths:

```powershell
python tests/source_debug_checks.py --assembler "$armBin/arm-none-eabi-as.exe" --linker "$armBin/arm-none-eabi-ld.exe" --gdb "$armBin/arm-none-eabi-gdb.exe"
```

The test copies [the fixture](../tests/fixtures/source_debug.emb) to an actual
input path containing spaces and `&` under `build/source-debug/`. It invokes
the compiler with a **relative** source path, then assembles from a **different
cwd**. Decoded DWARF must retain the original absolute input path. Statement
rows are exactly lines **2, 3, 4, 5, 6 and 10**, column 5; non-statement rows
identify function definitions on lines 1 and 9.

An actual ARM GDB process connects to the existing loopback Unicorn RSP server:

```text
break "<absolute original path>/source_debug.emb":2
continue
info line *$pc
step
```

Four real `step` commands stop at **3 → 4 → 5 → 6**. Each stop is checked using
GDB's `info line *$pc`, not just an echoed marker. Ranges in this test ELF:

| Source line | First instruction |
| --- | --- |
| 2: `let left: u32 = 6` | `0x1000c` |
| 3: `let right: u32 = 7` | `0x10012` |
| 4: `let product: u32 = left * right` | `0x10018` |
| 5: `product = product + 0` | `0x10030` |
| 6: `return product` | `0x10046` |

After continue to the emulator's return sentinel, GDB verifies **r0=42,
SP=0x20010000**. This proves `.emb` breakpoints and source-line stepping through
the straight-line function, not typed locals, `next` over calls, comprehensive
unwinding, source stepping through every branch/loop, or editor debug UI.

Five Python tests cover original ELF paths/rows, actual GDB source steps,
mapped/plain `.text` equality for both this probe and the larger ARM execution
fixture, and UTF-8 path metadata. Seven new Kotlin/CLI tests cover opt-in output,
escaping, source positions, control flow and errors. Full regression results are
in the [verification journal](report/VERIFICATION.md).

Generated files stay ignored under `build/source-debug/`: `mapped.elf`, assembly,
GDB commands, logs and result JSON. `build/gdb-poc/probe.elf` remains a separate
assembly-only baseline.

## Unicode boundary observed on this Windows machine

The available Java 17 launcher reports Cp1251 for native/file encoding. Some
Unicode command-line filenames (tested Ω and é) become `?` before source loading.
This existing launcher limitation was not fixed by changing system settings or
the language frontend.

A Java source-mode **test bridge** receives an ASCII base64 path, reads the real
`source_Ω.emb` inside the JVM and invokes Frontend/ArmBackend APIs. GNU as and
pyelftools confirm the original UTF-8 filename in the ELF. This demonstrates
lossless **API/ELF metadata**, not general Unicode CLI paths or Windows GDB
Unicode lookup. Ordinary CLI paths with spaces/metacharacters and GDB source
lookup are tested separately. The bridge adds no production CLI or language feature.

## Remaining work

Typed locals/parameters, scope DIEs, full unwind information, cross-call
`next`/`finish`, further control-flow source tests, portable Unicode launcher
handling, path relocation and both editor adapters remain. ARM GDB still lacks
native DAP; the adapter plan is in [GDB_DEBUGGING.md](GDB_DEBUGGING.md). No board,
OpenOCD, flashing or publication was used. Emulation is not physical validation.

Primary references: [GNU as `.file`](https://sourceware.org/binutils/docs/as/File.html),
[GNU as `.loc`](https://sourceware.org/binutils/docs/as/Loc.html),
[GDB stepping](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Continuing-and-Stepping.html).
