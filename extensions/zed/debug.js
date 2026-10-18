'use strict';
// Build a CPU-only ELF and emit local Zed launch settings. No adapter/target is started here.
const fs = require('node:fs');
const path = require('node:path');
const { build } = require('../vscode/src/local-debug');

function configuration({ root, elf, toolchain, python, pythonModules, adapter, node = process.execPath }) {
  for (const [key, value] of Object.entries({ root, elf, toolchain, python, adapter, node }))
    if (!value || !path.isAbsolute(value)) throw new Error(`${key} must be an absolute path`);
  return {
    adapter: 'EmbedLang GDB', label: 'EmbedLang: local source debug', request: 'launch',
    nodePath: node, cdtAdapterPath: adapter, program: elf, cwd: root,
    gdb: path.join(toolchain, `arm-none-eabi-gdb${process.platform === 'win32' ? '.exe' : ''}`),
    gdbAsync: true, gdbNonStop: false, openGdbConsole: false, run: 'preserve',
    initCommands: [], preRunCommands: [], customResetCommands: [],
    target: {
      type: 'remote', host: '127.0.0.1', server: python,
      serverParameters: [path.join(root, 'tools/debug/unicorn_rsp.py'), '--elf', elf, '--entry', 'main', '--port', '0', '--interactive'],
      serverPortRegExp: 'RSP_READY 127\\.0\\.0\\.1:([0-9]+)',
      environment: pythonModules ? { PYTHONPATH: pythonModules } : {},
      automaticallyKillServer: true, watchServerProcess: true, cwd: root,
      portDetectionTimeout: 15000
    }
  };
}

async function prepare(root, source, env = process.env) {
  const required = ['EMBEDLANG_ARM_BIN', 'EMBEDLANG_PYTHON', 'EMBEDLANG_CDT_ADAPTER'];
  for (const key of required) if (!env[key]) throw new Error(`Set ${key} to its absolute local path first.`);
  if (!fs.existsSync(source) || path.extname(source) !== '.emb') throw new Error('An existing saved .emb source is required.');
  const destination = path.join(root, '.zed/debug.json');
  // Never replace a user's existing scenarios automatically.
  if (fs.existsSync(destination)) throw new Error('Existing .zed/debug.json preserved. Move it aside or merge scenarios manually.');
  const elf = await build({ workspaceRoot: root, source: path.resolve(source),
    compilerDirectory: env.EMBEDLANG_COMPILER_DIRECTORY || '', javaPath: env.EMBEDLANG_JAVA || '',
    toolchainDirectory: env.EMBEDLANG_ARM_BIN });
  const config = configuration({ root, elf, toolchain: env.EMBEDLANG_ARM_BIN, python: env.EMBEDLANG_PYTHON,
    pythonModules: env.EMBEDLANG_PYTHON_MODULES, adapter: env.EMBEDLANG_CDT_ADAPTER });
  if (!fs.existsSync(config.cdtAdapterPath)) throw new Error('CDT target adapter script not found.');
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.writeFileSync(destination, JSON.stringify([config], null, 2) + '\n', { flag: 'wx' });
  console.log(`CPU ELF: ${elf}\nLocal Zed configuration: ${destination}`);
  return config;
}
if (require.main === module) {
  const root = path.resolve(__dirname, '../..');
  prepare(root, path.resolve(process.argv[2] || path.join(root, 'tests/fixtures/source_debug.emb')))
    .catch(error => { console.error(error.message); process.exitCode = 1; });
}
module.exports = { configuration, prepare };
