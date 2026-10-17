# Milestone 4A local validation

Validation performed on 2026-10-15, Windows, before any remote execution.

## Preserved baseline

Milestone 3 was uncommitted at the start. Its existing changes were preserved,
76 JUnit tests and 15 ARM execution checks passed, and the requested commit was
created:

`0a20e79e64ae24c1f837df447ecb05dc92f4d77a`

Message: `Milestone 3: ARM Thumb-2 backend`.

Milestone 4A was initially left uncommitted for review and then reverified for
the requested preservation commit. No tracked user changes were discarded.
There are no changes to compiler source, Kotlin tests, AST, semantics,
IR, backend or language specification relative to this commit.

## Executed results

| Validation | Result |
| --- | --- |
| Complete compiler JUnit suite, rerun tasks | 76 passed, 0 failures/errors |
| Existing Cortex-M4 execution harness, GNU ARM tools + Unicorn | 15 checks passed |
| New firmware tests, actual ARM code + controlled HAL/trace hooks | 12 tests passed |
| ARM GNU GCC assembly/link of remote_blink | Passed |
| Assembly/link of all-runtime-symbols fixture | Passed |
| Assembly/link of basic example | Passed |
| ELF sections, vectors, symbols, BIN bytes | Passed for all three images |
| Independent repeat build of remote_blink in another output directory | Identical BIN SHA-256 |
| Git whitespace check | Passed |
| Remote upload / physical hardware execution | Not performed |

The new tests include original SystemInit vector relocation, SysTick tick
advancement, preservation of trace task_id, actual trace encoding, original CRC
and reset-register write. GPIO tests intercept HAL calls; the finite test uses
HAL/trace stubs. These checks do not reproduce a physical board or remote loader.

Installed toolchain: Arm GNU Toolchain 13.3.Rel1 (Build arm-13.24), GCC 13.3.1
20240614. Python 3.12.11, pyelftools 0.33, Unicorn 2.1.4. The downloaded official
Windows ZIP's observed SHA-256 is
`e46fda043c0ce83582bc8db4b3ef85f77f4beb7333344c2f4193c17e1167a095`.
This is a locally measured digest, not a claim of signature verification.

## Artifacts and memory

All paths below are relative to the repository root. Each directory also
contains the ELF, map, disassembly, symbols, `.su` files and `verification.json`.

| BIN | Bytes | Free RAM after minimum reservations |
| --- | ---: | ---: |
| `firmware/build/remote_blink/firmware.bin` | 6,148 | 70,088 |
| `firmware/build/basic/firmware.bin` | 6,240 | 70,000 |
| `firmware/build/runtime_symbols/firmware.bin` | 6,308 | 69,928 |

Finite Blink SHA-256:
`4f759e3b0c34322f89ea4737f14801c76abc0145cd64a73a62f1d897d4abe57c`.

Finite Blink sections:

| Section | Address | Bytes |
| --- | --- | ---: |
| .isr_vector | 0x2000D000 | 392 |
| .text | 0x2000D188 | 4,636 |
| .rodata | 0x2000E3A4 | 1,080 |
| .ARM | 0x2000E7DC | 8 |
| .init_array | 0x2000E7E4 | 4 |
| .fini_array | 0x2000E7E8 | 4 |
| .data | 0x2000E7EC | 24 |
| .bss | 0x2000E804 | 48 |
| ._user_heap_stack | 0x2000E834 | 1,540 including alignment |

Reset vector: `0x2000D32D` (Thumb). Initial SP: `0x20020000`. Minimum heap:
512 bytes; minimum stack: 1,024 bytes. Unresolved symbols: none. No allocated
sections in lower reserved SRAM, CCM trace RAM, or Flash. The emulated finite
Blink call chain used 72 bytes with HAL/trace stubs; that excludes real HAL/trace
callee stacks and interrupts and is not a complete hardware stack bound. Example
C frames include SystemClock_Config 88 bytes, gpio_mode 48 bytes and official
timestamp 24 bytes; per-function `.su` reports are retained for review.

## Warnings and outstanding verification

The unmodified upstream C sources emit unused-parameter warnings. GNU ld warns
about an RWX load segment because the official template puts executable code and
writable data together in RAM, and about a missing GNU-stack note in toolchain
`crtn.o`. These warnings were visible, not hidden; the build/link and address
checks passed. The official linker script was not modified to suppress them.

The public cLAB site timed out during inspection. Live upload control names,
task-specific restrictions and physical execution still need verification after
review. General recursive EmbedLang programs have no static stack bound; the
linker's minimum reservation is not a proof of stack safety. No credentials,
secrets, private lab settings, upload or flash operations were used.

## Change inventory

- Added `firmware/build.py`, `firmware/tools/verify.py`, runtime C/header, adapted
  board main, pinned vendor files/manifest, dependency lists and license notices.
- Added `examples/remote_blink.emb`, `tests/fixtures/runtime_symbols.emb`, and
  `tests/firmware_checks.py`.
- Added `docs/STM32_RUNTIME.md`, `docs/ITMO_CLAB.md`, and this report.
- Updated README, architecture, ARM target/backend cross-references and milestone
  requirements. Added vendor newline preservation in `.gitattributes` and Python
  cache exclusions in `.gitignore`.

Generated artifacts and portable tools remain ignored. See
[ITMO_CLAB.md](ITMO_CLAB.md#next-upload-steps-manual-after-review) for the manual
upload sequence to perform only after review.

## Preservation review

Before the Milestone 4A commit, all compiler, ARM emulation and firmware tests
were rerun. Vendor review identified 24 unused driver files and headers for
other CPU cores/toolchains through GNU GCC dependency inspection. Those files
were moved to an ignored local archive and omitted from the snapshot manifest;
all retained upstream file contents and licenses are unchanged. The firmware
was rebuilt after this reduction. No compiler/runtime implementation or
architecture change was needed. Staged files were checked for credentials,
secrets, generated firmware/build artifacts and unnecessary vendor files.
