'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const root = __dirname;
const grammar = path.join(root, 'tree-sitter');
const output = path.join(root, 'build', 'embedlang');
const sdk = process.env.WASI_SDK_PATH;
const zig = process.env.ZIG;
if (!sdk && !zig) throw new Error('Set WASI_SDK_PATH to an extracted official wasi-sdk, or ZIG to a Zig executable.');
const clang = sdk ? path.join(sdk, 'bin', process.platform === 'win32' ? 'clang.exe' : 'clang') : zig;
const cli = path.join(root, 'node_modules/tree-sitter-cli', process.platform === 'win32' ? 'tree-sitter.exe' : 'tree-sitter');
const zigIncludes = !sdk ? ['-isystem', path.join(path.dirname(zig), 'lib/libc/include/wasm-wasi-musl'),
  '-isystem', path.join(path.dirname(zig), 'lib/libc/include/generic-musl')] : [];
function run(command, args, cwd) {
  const result = spawnSync(command, args, { cwd, stdio: 'inherit', windowsHide: true, shell: false });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} failed (${result.status})`);
}
run(cli, ['generate', '--abi', '14'], grammar);
fs.mkdirSync(path.join(output, 'grammars'), { recursive: true });
// A parser is a side module, not a WASI executable: no _start/main or libc.
run(clang, [...(sdk ? [] : ['cc', '-target', 'wasm32-wasi']), ...zigIncludes, '-fPIC', '-shared', '-Os', '-nostdlib', '-Wl,--no-entry', '-Wl,--export=tree_sitter_embedlang',
  '-I', path.join(grammar, 'src'), path.join(grammar, 'src/parser.c'),
  '-o', path.join(output, 'grammars/embedlang.wasm')], root);
fs.copyFileSync(path.join(root, 'extension.toml'), path.join(output, 'extension.toml'));
fs.copyFileSync(path.join(root, 'TREE_SITTER_LICENSE'), path.join(output, 'TREE_SITTER_LICENSE'));
fs.cpSync(path.join(root, 'languages'), path.join(output, 'languages'), { recursive: true });
console.log(`Unpacked local Zed extension: ${output}`);
