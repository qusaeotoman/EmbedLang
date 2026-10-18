'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { invocation, runCompiler } = require('./compiler');

function tool(directory, name) {
  const executable = `${name}${process.platform === 'win32' ? '.exe' : ''}`;
  return directory ? path.join(directory, executable) : executable;
}

function configuration({ workspaceRoot, elf, endpoint, toolchainDirectory }) {
  if (!/^127\.0\.0\.1:[1-9]\d{0,4}$/.test(endpoint) || Number(endpoint.split(':')[1]) > 65535)
    throw new Error('Local debugging requires a loopback TCP endpoint.');
  return {
    name: 'EmbedLang: Local Unicorn', type: 'cortex-debug', request: 'attach', servertype: 'external',
    cwd: workspaceRoot, executable: elf, gdbTarget: endpoint,
    gdbPath: tool(toolchainDirectory, 'arm-none-eabi-gdb'),
    ...(toolchainDirectory ? { armToolchainPath: toolchainDirectory } : {}),
    // External attach's default monitor halt is inappropriate for this CPU target.
    overrideAttachCommands: [], overrideRestartCommands: [], loadFiles: [],
    liveWatch: { enabled: false }, swoConfig: { enabled: false }, rttConfig: { enabled: false }
  };
}

async function build({ workspaceRoot, source, compilerDirectory, javaPath, toolchainDirectory }) {
  const spec = invocation({ workspaceRoot, source, compilerDirectory, javaPath, mode: 'asm' });
  spec.args.splice(spec.args.length - 1, 0, '--debug-lines');
  const result = await runCompiler(spec);
  if (result.code !== 0) throw new Error(result.stderr || 'EmbedLang compilation failed.');
  const output = path.join(workspaceRoot, 'build/vscode-debug');
  fs.mkdirSync(output, { recursive: true });
  const assembly = path.join(output, 'program.s');
  const object = path.join(output, 'program.o');
  const elf = path.join(output, 'program.elf');
  fs.writeFileSync(assembly, result.stdout);
  for (const [name, args] of [
    ['arm-none-eabi-as', ['-mcpu=cortex-m4', '-mthumb', '-g', '--gdwarf-4', '-o', object, assembly]],
    ['arm-none-eabi-ld', ['-Ttext=0x10000', '-e', 'main', '-o', elf, object]]
  ]) {
    const compiled = await runCompiler({ executable: tool(toolchainDirectory, name), args, cwd: workspaceRoot });
    if (compiled.code !== 0) throw new Error(compiled.stderr || `${name} failed.`);
  }
  return elf;
}

function startTarget({ pythonPath, repositoryDirectory, elf, pythonModulePath = '', output }) {
  return new Promise((resolve, reject) => {
    const script = path.join(repositoryDirectory, 'tools/debug/unicorn_rsp.py');
    if (!fs.existsSync(script)) return reject(new Error('Configure embedlang.localDebug.repositoryDirectory to the EmbedLang repository.'));
    const env = { ...process.env };
    if (pythonModulePath) env.PYTHONPATH = pythonModulePath;
    const processHandle = spawn(pythonPath || 'python', [script, '--elf', elf, '--entry', 'main', '--port', '0', '--interactive'],
      { cwd: repositoryDirectory, env, windowsHide: true, shell: false, stdio: ['ignore', 'pipe', 'pipe'] });
    let buffer = '', ready = false;
    const timer = setTimeout(() => { processHandle.kill(); reject(new Error('Local Unicorn target did not start within 15 seconds.')); }, 15000);
    processHandle.stderr.on('data', data => output?.append(data.toString()));
    processHandle.stdout.on('data', data => {
      buffer += data.toString();
      const match = /^RSP_READY (127\.0\.0\.1:\d+)\r?$/m.exec(buffer);
      if (match && !ready) { ready = true; clearTimeout(timer); resolve({ process: processHandle, endpoint: match[1] }); }
    });
    processHandle.on('error', error => { clearTimeout(timer); reject(error); });
    processHandle.on('exit', code => { clearTimeout(timer); if (!ready) reject(new Error(`Local target exited before readiness (${code}). Check Python/Unicorn/pyelftools.`)); });
  });
}

module.exports = { configuration, build, startTarget };
