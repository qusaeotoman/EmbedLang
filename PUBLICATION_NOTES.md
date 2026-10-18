# Public source snapshot exclusions

## Source update — 2026-10-18

This update exports verified local milestone **854c413** plus the subsequently
reviewed documentation/compliance audit. It adds the VS Code and Zed source,
DWARF `.emb` line mapping, ARM GDB/MI → localhost TCP RSP/Unicorn tools, tests,
and Russian report templates/appendices. It continues the existing public
`main` history rooted at `feeb72965b136fdd7a9cc3f4f310719aaecc47cd`.
Original local milestone commits are provenance references only; their private
Git ancestry is not merged, rebased onto, or pushed into the public repository.

All six exclusions below remain absent. The original public **72-file vendor
manifest and vendor bytes** are unchanged. The public missing-OLED build guard,
upstream licenses and public-guide warnings are retained. No new project-wide
license is assigned. New extension source/lockfiles/attribution are included;
CDT, Cortex-Debug, Rust crates/toolchains and npm dependencies are installed
separately, not vendored. A future compiled-extension release requires its full
applicable transitive notices and a separate release review.

### Verified public-edition results

The tests below ran against **this separate public checkout**, not merely the
private milestone. Existing external tools, cached packages and ignored local
dependency directories were reused; this is not a clean-machine CI claim.

| Suite | Passed |
| --- | ---: |
| Compiler/CLI JUnit, forced Gradle rerun | 89 |
| ARM execution | 15 |
| GDB/RSP connection and `.emb` DWARF/source stepping | 9 + 5 |
| Node VS Code unit/CLI, Zed grammar/tasks/DAP/component checks | 60 |
| Actual isolated VS Code Host / Restricted / Cortex-Debug Host | 12 + 1 + 8 |
| Rust API glue unit tests | 2 |
| Public firmware suite | 52 |
| **Total passed; zero failures** | **253** |

The public firmware runner executes 53 cases: **52 passed, 1 optional comparison
skipped** because the pristine official reference ELF is not supplied. It
explicitly excludes three historical cases that require private preservation
manifests or the original hardware-tested BINs. Seven OLED firmware checks are
not run because their upstream driver/font files are not redistributed.
The original assertions and recorded hardware hashes are unchanged.
Thus the earlier **264 full-local checks** are not presented as 264 public tests.

Nine fresh firmware builds completed with successful ELF/BIN verification:
ordinary remote Blink; probe; diagnostic Blink; size-profile diagnostic Blink;
init diagnostics; recovered probe; recovered Blink; local F407 Blink; local F427
Blink. GNU symbols, target/profile memory/vector layout and BIN output were
verified by their existing builders/tests. All generated artifacts remain ignored.
The public OLED command was checked to reject unavailable driver files explicitly.
Both the Tree-sitter grammar WASM (Zig 0.13.0) and debugger component
(`wasm32-wasip2`, Rust 1.90.0) built; debugger packaging passed.

Fresh diagnostic BIN hashes differ from preserved hardware artifacts because
diagnostic `__FILE__` strings embed the build location. This was observed during
the historical F427 preservation test; the assertion was not weakened or its
expected hardware hash replaced. Use the public runner below for freshly built
images. They are **not newly hardware-validated images** and are not distributed.

Actual **Zed 1.24.2 UI** acceptance was performed earlier on identical debugger
source/component: `.emb:2`, steps 3–6, Continue/Pause/resume, registers/useful
frames, Console disassembly, 42/restored SP and cleanup. It was not repeated as
part of publication. Exported public-source DAP/GDB tests were rerun here. Typed
locals, full unwinding, arbitrary control-flow stepping and dedicated Zed
disassembly UI are not claimed. No board, Flash, driver or laboratory action
was performed for this publication.

### Reproduce the public checks

Use JDK 17, Node 22+, ARM GNU toolchain, Python dependencies from
`firmware/requirements-tests.txt`, Rust 1.90.0/wasm32-wasip2, and Zig or wasi-sdk
for the grammar. Lockfiles pin source dependencies. Follow
[VS Code](docs/VSCODE_DEBUGGING.md) and [Zed](docs/ZED_DEBUGGING.md) setup, then:

```powershell
.\gradlew.bat --no-daemon :compiler:test :compiler:installDist --rerun-tasks
npm --prefix extensions/vscode ci --ignore-scripts
npm --prefix extensions/zed ci --ignore-scripts
# Install the pinned Tree-sitter CLI binary if a fresh --ignore-scripts install needs it:
npm --prefix extensions/zed rebuild tree-sitter-cli
# Set ZIG (or WASI_SDK_PATH) to your existing portable toolchain:
npm --prefix extensions/zed run build
cargo +1.90.0 build --locked --manifest-path extensions/zed/debugger/Cargo.toml --target wasm32-wasip2 --release
cargo +1.90.0 test --locked --manifest-path extensions/zed/debugger/Cargo.toml
node extensions/zed/debugger/package.js
```

On GNU Windows Rust, use the documented `1.90.0-x86_64-pc-windows-gnu` host
and its MinGW linker. Set absolute `EMBEDLANG_ARM_BIN`, `EMBEDLANG_PYTHON`,
`EMBEDLANG_PYTHON_MODULES` if needed, and `EMBEDLANG_CDT_ADAPTER` as documented
in the guides; none belongs in committed machine configuration.

```powershell
node --test extensions/vscode/test/unit.test.js extensions/vscode/test/local-debug.test.js extensions/vscode/test/cli.test.js extensions/zed/test/grammar.test.js extensions/zed/test/tasks.test.js extensions/zed/test/debug.test.js extensions/zed/test/wasm.test.js
python tests/arm_execution.py --assembler "$armBin/arm-none-eabi-as.exe" --linker "$armBin/arm-none-eabi-ld.exe"
python tests/gdb_connection_checks.py --assembler "$armBin/arm-none-eabi-as.exe" --linker "$armBin/arm-none-eabi-ld.exe" --gdb "$armBin/arm-none-eabi-gdb.exe"
python tests/source_debug_checks.py --assembler "$armBin/arm-none-eabi-as.exe" --linker "$armBin/arm-none-eabi-ld.exe" --gdb "$armBin/arm-none-eabi-gdb.exe"
```

`$armBin` denotes your absolute ARM GNU bin directory. VS Code Host commands are
documented in the editor guides. The existing debug Host harness expects ignored
`.tools/arm-gnu/arm-gnu-toolchain*/bin`, `.tools/python-deps` and a writable
`.tools/cortex-debug` evidence directory; supply external tools there or use local
directory links. Those directories/dependencies are never committed. Stop debug
sessions before another test rebuilds the shared CPU ELF.

Prepare all public firmware test images, without connecting a board:

```powershell
python firmware/build.py examples/remote_blink.emb --toolchain-bin $armBin
python firmware/build.py examples/diagnostic_probe.emb --diagnostic probe --output firmware/build/diagnostic_probe --toolchain-bin $armBin
python firmware/build.py examples/remote_blink.emb --diagnostic blink --output firmware/build/diagnostic_blink --toolchain-bin $armBin
python firmware/build.py examples/remote_blink.emb --diagnostic blink --profile size --output firmware/build/diagnostic_blink_size --toolchain-bin $armBin
python firmware/build.py examples/diagnostic_probe.emb --diagnostic init --output firmware/build/diagnostic_init --toolchain-bin $armBin
python firmware/build.py examples/diagnostic_probe.emb --diagnostic probe-recovered --output firmware/build/diagnostic_probe_recovered --toolchain-bin $armBin
python firmware/build.py examples/remote_blink.emb --diagnostic blink-recovered --output firmware/build/diagnostic_blink_recovered --toolchain-bin $armBin
python firmware/build_local.py examples/remote_blink.emb --mcu stm32f407vgt6 --toolchain-bin $armBin
python firmware/build_local.py examples/remote_blink.emb --mcu stm32f427vit6 --toolchain-bin $armBin
python tests/public_firmware_checks.py
```

The runner lists its three historical exclusions and retains the F407/F427
generated-assembly equality precheck. Original tests remain available for users
who legitimately have the original preservation fixtures. It does not silently
claim a hash match for a fresh build or skip errors in the applicable suite.

### Security, report and scope

Reviewed source and staged content are checked for credential/private-key/token
signatures, personal absolute paths, credential-bearing URLs, unexpected binary
files and private configuration. Vendor/license notices and the six exclusions
are checked separately. Pattern scans reduce disclosure risk; they are not a
proof that arbitrary text can never contain sensitive data. The Git author uses
the account's public noreply address. The sole retained binary build bootstrap
is the pre-existing, unchanged Gradle wrapper JAR; no generated product binary
is added. No node_modules, Rust target, ELF/BIN/WASM/VSIX, logs, backups, original
assignment PDF, user profiles or `.zed/debug.json` is published.

Russian report sections reserved for student authorship remain placeholders.
The original assignment audit predates this approved publication: statements
about unpublished editor work there describe its historical state. The source
update does not establish student authorship, CubeIDE usage/instructor approval,
physical GDB debugging or new hardware results. Existing hardware observations
retain their dates, hashes and distinction from simulation.

## Original publication exclusions

The original local project and milestone history remain unchanged. This public
snapshot deliberately omits six upstream files because no applicable
redistribution permission was established from the inspected sources:

- `firmware/vendor/SDK-1.1M/SDK_OLED/Core/Src/oled.c`
- `firmware/vendor/SDK-1.1M/SDK_OLED/Core/Src/fonts.c`
- `firmware/vendor/SDK-1.1M/SDK_OLED/Core/Inc/oled.h`
- `firmware/vendor/SDK-1.1M/SDK_OLED/Core/Inc/fonts.h`
- `firmware/vendor/SDK-1.1M/SDK_EXTI/SDK11M.cfg`
- `firmware/vendor/SDK-1.1M/SDK_OLED/SDK_OLED.ioc`

The absence of a license notice is not treated as permission to redistribute.
The remaining vendor files have explicit ST BSD/Apache notices or are covered
by the included SDK_cLAB GPL-3.0 license. Original copyright notices, license
texts and attribution are retained. No project-wide license is assigned to the
original EmbedLang code.

The vendor manifest lists only the 72 included upstream files. The original
hardware tests used the complete local snapshot, with 78 vendor entries. The
public compiler, cLAB build and local Blink build remain available; OLED builds
and OLED firmware integration tests need separately permitted copies of the
four OLED/font files at their documented paths. They are not downloaded by the
public builder. Do not assume that public availability of upstream code grants
redistribution permission. Obtain permission or use a separately reviewed,
licensed replacement before redistributing that component.

The preserved OLED hardware validation is historical evidence, not a claim
that the restricted driver/font files are included in this public repository.
No firmware binaries, Flash backups, logs, tool installations or private
configuration are included. The initial public commit uses the GitHub account's
noreply address, and contains no original private Git history or metadata.

## Historical verification before the initial publication

Before initial publication, the public snapshot passed all 82 compiler JUnit
tests, with zero failures/errors/skips. Its F427 local Blink and ITMO.cLAB
remote_blink firmware builds both completed and passed ELF/BIN verification.
The OLED build is intentionally blocked until separately permitted OLED/font
files are supplied. All generated outputs stayed in ignored build directories.
No board connection, reset, programming or laboratory upload was performed.
