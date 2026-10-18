# EmbedLang for VS Code — local Milestone 6 prototype

Basic editing support for `.emb` files, using the existing EmbedLang compiler
CLI. Optional local CPU debugging uses Cortex-Debug and Unicorn over TCP/IP.
No language server, STM32 connection or firmware upload is involved.
This extension has not been published to the Marketplace.

## Features

- `.emb` language recognition and TextMate syntax highlighting, including the
  actual GPIO/time/OLED built-ins. Unsupported strings are not highlighted as a
  supported language construct.
- `//` comments, parentheses/braces, matching/autoclosing and basic indentation.
- **EmbedLang: Validate Current File** (`embedlang.validate`).
- **EmbedLang: Emit Typed IR** (`embedlang.emitIr`).
- **EmbedLang: Emit ARM Assembly** (`embedlang.emitAsm`).
- **EmbedLang: Debug Current File in Local Unicorn** (`embedlang.startLocalDebug`),
  with a separately installed Cortex-Debug adapter and ARM GNU/Python tools.
- Errors in the Problems panel with compiler codes and source locations.
- Optional validation on save (enabled by default); edits clear outdated errors.
- IR/assembly opens in a separate untitled editor. Source files and firmware
  outputs are not overwritten. Save the preview explicitly if needed.

## Compiler setup

VS Code 1.85+ and **JDK 17** are required. Build the compiler from the EmbedLang
repository root first:

```powershell
.\gradlew.bat --no-daemon :compiler:test :compiler:installDist
```

Open the repository root as a VS Code workspace. By default, the extension
uses `compiler/build/install/embedlang/lib/*` under the workspace containing the
source document. It runs `embedlang.MainKt` with the existing CLI arguments,
using Java directly rather than interpolating a Windows `.bat` into a shell.
JVM path selection is: configured Java executable, `JAVA_HOME/bin/java`, then
`java` on PATH. No Java or compiler distribution is bundled in the extension.

For a different installation, configure these settings through VS Code settings
or your local workspace configuration (do not commit personal absolute paths):

| Setting | Default / behavior |
| --- | --- |
| `embedlang.compilerDirectory` | Empty: workspace-relative installed distribution above. Otherwise absolute or workspace-relative distribution directory containing `lib/compiler.jar`. |
| `embedlang.javaPath` | Empty: JAVA_HOME/PATH. Otherwise Java executable path only, without shell syntax or command arguments. |
| `embedlang.validateOnSave` | `true` |
| `embedlang.timeoutMs` | 15000; permitted range 1000–120000 |

For a standalone source folder, set compilerDirectory to an existing distribution.
Multi-root workspaces resolve settings and relative paths for the document's
own folder. Only saved local `file:` documents are supported. Manual commands
save a dirty file before running; an untitled file must first be saved by the user.

In Restricted Mode only declarative editing features are available; all compiler
execution is blocked. A trusted workspace can execute its configured Java/CLI,
so use a compiler distribution you trust. The extension itself makes no network
requests and contains no telemetry. It logs compiler output to a local Output
channel, not to a file or external service.

## Local installation and development

Run without installing into the normal VS Code profile, from the repository root:

```powershell
code --new-window --extensionDevelopmentPath="$PWD/extensions/vscode" "$PWD"
```

This opens an Extension Development Host. Open an `.emb` file and use the
commands in the Command Palette. Build tooling/tests require **Node.js 22+** and
npm; the extension has no runtime npm dependencies.

```powershell
cd extensions/vscode
npm ci --ignore-scripts
npm test
npm run test:cli
# Run with the actual VS Code executable, not a .cmd wrapper:
node test/run-host.js "<absolute path to Code.exe>"
node test/run-host.js "<absolute path to Code.exe>" --untrusted
```

Host tests launch isolated temporary user-data/extensions/workspace directories.
They do not change the user's normal settings or install the extension globally.
`test:cli` and the Host tests require the built distribution and usable JDK.
The host runner uses an already installed VS Code; it downloads no editor.
Test profiles/evidence are local temporary files, not project deliverables.

To build a local installation package:

```powershell
New-Item -ItemType Directory -Force build
npm run package:local
code --install-extension build/embedlang-0.1.0.vsix
```

The last command is for the user to run deliberately; development/testing does
not perform it. On Linux/macOS, use `mkdir -p build` before packaging, and pass
the actual VS Code executable path to the host runner. Use the VS Code extension
menu's **Install from VSIX...** as an alternative. Generated VSIX files are
ignored and are not releases. No Marketplace publishing command is part of the
workflow. This prototype declares `UNLICENSED`; no project-wide license has been
selected for the original code.

## Diagnostics and limitations

The adapter parses the CLI's one-based `file:line:column` syntax/semantic errors.
It converts code-point columns to UTF-16 offsets. Because the CLI supplies no
token span, the marker covers one code point, or a zero-width EOF position.
Diagnostic codes remain unchanged. Failed compiler launches, timeouts and CLI
usage/file errors appear in the local Output channel and manual error messages;
they do not fabricate source locations.

Only saved files are analyzed, not each keystroke. Results from an older document
version are discarded. There is no completion, rename, definition navigation,
formatter or LSP in this adapter. Zed has a
[separate local prototype](../zed/README.md). Output is bounded to 4 MiB per
compiler invocation. The firmware runtime available at link time remains a
separate concern; semantic recognition of an OLED call does not supply the
excluded OLED driver in the public source edition.

## Verification

For `.emb` breakpoints, source stepping, Continue/Pause, registers and disassembly,
follow the [local debugging guide](../../docs/VSCODE_DEBUGGING.md). Eight scenarios
were exercised in actual VS Code 1.139.1 with Cortex-Debug 1.12.1. This CPU-only
workflow does not provide typed EmbedLang locals or complete stack unwinding.
It does not run the STM32 firmware runtime or access hardware.

Verified counts and tested editor version are recorded in the repository's
[living report](../../docs/report/VERIFICATION.md). Unit tests include actual
TextMate tokenization; CLI tests execute the compiler; Host tests exercise VS Code
language activation, commands, Problems, preview output and Restricted Mode.
No hardware result is inferred from these tests.

Implementation follows the official VS Code
[language extension guide](https://code.visualstudio.com/api/language-extensions/overview),
[API reference](https://code.visualstudio.com/api/references/vscode-api) and
[Extension Host testing guide](https://code.visualstudio.com/api/working-with-extensions/testing-extension).
