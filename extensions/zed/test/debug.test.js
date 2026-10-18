'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const net = require('node:net');
const { configuration, prepare } = require('../debug');
const { build } = require('../../vscode/src/local-debug');
const { DapClient } = require('./dap-client');
const root = path.resolve(__dirname, '../../..');
const env = process.env;
const options = () => ({ root, elf: path.join(root, 'build/vscode-debug/program.elf'),
  toolchain: env.EMBEDLANG_ARM_BIN, python: env.EMBEDLANG_PYTHON,
  pythonModules: env.EMBEDLANG_PYTHON_MODULES, adapter: env.EMBEDLANG_CDT_ADAPTER });

test('Zed configuration owns loopback RSP server and uses no load/reset scripts', () => {
  const config = configuration(options());
  assert.equal(config.adapter, 'EmbedLang GDB'); assert.equal(config.target.host, '127.0.0.1');
  assert.equal(config.request, 'launch'); assert.ok(config.target.serverParameters.includes('--interactive'));
  assert.equal(config.target.automaticallyKillServer, true);
  assert.deepEqual(config.initCommands, []); assert.deepEqual(config.customResetCommands, []);
  assert.equal(config.imageAndSymbols, undefined);
});
test('Zed configuration rejects relative machine executable paths', () => {
  assert.throws(() => configuration({ ...options(), python: 'python' }), /absolute/);
});
test('preparation preserves existing user debug scenarios', async () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'embedlang-zed-config-'));
  try {
    fs.mkdirSync(path.join(temporary, '.zed')); fs.writeFileSync(path.join(temporary, '.zed/debug.json'), 'original');
    await assert.rejects(prepare(temporary, path.join(root, 'tests/fixtures/source_debug.emb'), env), /preserved/);
    assert.equal(fs.readFileSync(path.join(temporary, '.zed/debug.json'), 'utf8'), 'original');
  } finally { fs.rmSync(temporary, { recursive: true }); }
});
test('Zed adapter manifest, schema and pinned API are present', () => {
  const extension = path.join(root, 'extensions/zed/debugger');
  assert.match(fs.readFileSync(path.join(extension, 'extension.toml'), 'utf8'), /debug_adapters\."EmbedLang GDB"/);
  const schema = JSON.parse(fs.readFileSync(path.join(extension, 'debug_adapter_schemas/embedlang.json')));
  assert.equal(schema.properties.request.const, 'launch');
  assert.match(fs.readFileSync(path.join(extension, 'Cargo.toml'), 'utf8'), /zed_extension_api = "=0.7.0"/);
  const adapterPackage = path.resolve(env.EMBEDLANG_CDT_ADAPTER, '../../package.json');
  assert.equal(JSON.parse(fs.readFileSync(adapterPackage)).version, '1.10.0');
});

async function session(source, action) {
  const elf = await build({ workspaceRoot: root, source, toolchainDirectory: env.EMBEDLANG_ARM_BIN });
  const config = configuration({ ...options(), elf });
  const client = new DapClient(config.cdtAdapterPath);
  try {
    const capabilities = await client.request('initialize', { adapterID: 'EmbedLang GDB', clientID: 'embedlang-zed-protocol-test',
      linesStartAt1: true, columnsStartAt1: true, pathFormat: 'path', supportsVariableType: true,
      supportsMemoryReferences: true, supportsRunInTerminalRequest: false });
    // These fields are consumed by Zed's extension hook, not forwarded to CDT.
    const launch = { ...config }; for (const key of ['adapter', 'label', 'nodePath', 'cdtAdapterPath']) delete launch[key];
    await client.request('launch', launch); await client.event('initialized');
    await action(client, capabilities);
    await client.request('disconnect', { restart: false, terminateDebuggee: true });
    await client.event('terminated');
    const output = client.events.filter(e => e.event === 'output').map(e => e.body.output).join('');
    const port = /RSP_READY 127\.0\.0\.1:(\d+)/.exec(output)?.[1]; assert.ok(port);
    const closed = await new Promise(resolve => { const socket = net.createConnection({ host: '127.0.0.1', port: Number(port) });
      socket.on('connect', () => { socket.destroy(); resolve(false); }); socket.on('error', () => resolve(true)); });
    assert.ok(closed, 'disconnect must stop the owned target');
  } finally {
    const destination = path.join(root, 'build/zed-debug'); fs.mkdirSync(destination, { recursive: true });
    fs.writeFileSync(path.join(destination, `${path.basename(source)}.dap.json`), JSON.stringify(client.trace, null, 2));
    client.stop();
  }
}
async function frame(client) {
  const threadId = (await client.request('threads')).threads[0].id;
  return { threadId, top: (await client.request('stackTrace', { threadId, startFrame: 0, levels: 3 })).stackFrames[0] };
}
async function resume(client, command, args) {
  const after = client.events.length; await client.request(command, args); await client.event('stopped', after);
}

test('real CDT DAP / ARM GDB / TCP source breakpoint, stepping, registers, disassembly and 42', { timeout: 120000 }, async () => {
  const directory = path.join(root, 'build/zed-debug/source with spaces & chars');
  fs.mkdirSync(directory, { recursive: true });
  const source = path.join(directory, 'source_debug.emb');
  fs.copyFileSync(path.join(root, 'tests/fixtures/source_debug.emb'), source);
  await session(source, async (client, capabilities) => {
    const breakpoints = await client.request('setBreakpoints', { source: { path: source }, breakpoints: [{ line: 2 }] });
    assert.ok(breakpoints.breakpoints[0].verified);
    await client.request('configurationDone'); await client.event('stopped');
    await resume(client, 'continue', { threadId: 1 });
    let current = await frame(client); assert.equal(current.top.line, 2); assert.equal(path.resolve(current.top.source.path), source);
    assert.ok(current.top.name); assert.ok(current.top.instructionPointerReference);
    assert.ok(capabilities.supportsDisassembleRequest);
    const asm = await client.request('disassemble', { memoryReference: current.top.instructionPointerReference, instructionCount: 4 });
    assert.ok(asm.instructions.some(row => row.instruction));
    const scopes = await client.request('scopes', { frameId: current.top.id });
    const registers = scopes.scopes.find(scope => /register/i.test(scope.name)); assert.ok(registers);
    const values = await client.request('variables', { variablesReference: registers.variablesReference });
    assert.ok(values.variables.some(row => row.name === 'r0'));
    for (const line of [3, 4, 5, 6]) {
      await resume(client, 'stepIn', { threadId: current.threadId, granularity: 'line' });
      current = await frame(client); assert.equal(current.top.line, line);
    }
    await client.request('setBreakpoints', { source: { path: source }, breakpoints: [] });
    await resume(client, 'continue', { threadId: current.threadId });
    current = await frame(client);
    const result = await client.request('evaluate', { expression: '$r0', context: 'watch', frameId: current.top.id });
    const sp = await client.request('evaluate', { expression: '$sp', context: 'watch', frameId: current.top.id });
    assert.match(result.result, /(?:42|0x0*2a)/i); assert.match(sp.result, /20010000/i);
  });
});

test('real CDT DAP pause and resume interrupt the running generated loop', { timeout: 120000 }, async () => {
  const directory = path.join(root, 'build/zed-debug'); fs.mkdirSync(directory, { recursive: true });
  const source = path.join(directory, 'pause.emb'); fs.writeFileSync(source, 'fn main() -> void {\n let x: u32 = 6 * 7\n while true { x = x + 0 }\n}\n');
  await session(source, async client => {
    await client.request('configurationDone'); await client.event('stopped');
    for (let attempt = 0; attempt < 2; attempt++) {
      await client.request('continue', { threadId: 1 });
      const after = client.events.length; await new Promise(resolve => setTimeout(resolve, 200));
      assert.equal(client.events.slice(after).filter(e => e.event === 'stopped').length, 0);
      await client.request('pause', { threadId: 1 }); await client.event('stopped', after);
      assert.equal(path.resolve((await frame(client)).top.source.path), source);
    }
  });
});

test('real CDT reports failed target startup instead of a successful launch', { timeout: 60000 }, async () => {
  const config = configuration(options());
  config.target.serverParameters = [path.join(root, 'build/zed-debug/no-such-target.py')];
  const client = new DapClient(config.cdtAdapterPath);
  try {
    await client.request('initialize', { adapterID: 'EmbedLang GDB', linesStartAt1: true, columnsStartAt1: true, pathFormat: 'path' });
    await assert.rejects(client.request('launch', config), /gdbserver exited|exited before ready/i);
  } finally { client.stop(); }
});
