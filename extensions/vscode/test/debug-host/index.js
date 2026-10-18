'use strict';
const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const net = require('node:net');

async function waitFor(predicate, label) {
  const deadline = Date.now() + 20000;
  while (!(await predicate())) {
    if (Date.now() > deadline) throw new Error(`Timed out: ${label}`);
    await new Promise(resolve => setTimeout(resolve, 30));
  }
}

async function run() {
  const root = path.resolve(__dirname, '../../../..');
  const workspace = vscode.workspace.workspaceFolders[0].uri.fsPath;
  const config = vscode.workspace.getConfiguration('embedlang');
  for (const [key, value] of Object.entries({
    compilerDirectory: path.join(root, 'compiler/build/install/embedlang'),
    validateOnSave: false, 'localDebug.repositoryDirectory': root,
    'localDebug.toolchainDirectory': path.join(root, '.tools/arm-gnu', fs.readdirSync(path.join(root, '.tools/arm-gnu')).find(name => name.startsWith('arm-gnu-toolchain')), 'bin'),
    'localDebug.pythonPath': process.env.EMBEDLANG_TEST_PYTHON || 'python',
    'localDebug.pythonModulePath': path.join(root, '.tools/python-deps')
  })) await config.update(key, value, vscode.ConfigurationTarget.Workspace);
  const results = [], packets = [], stops = [];
  const tracker = vscode.debug.registerDebugAdapterTrackerFactory('cortex-debug', {
    createDebugAdapterTracker() { return { onDidSendMessage(message) {
      packets.push(message);
      if (message.type === 'event' && message.event === 'stopped') stops.push(message.body);
    } }; }
  });
  const check = async (name, action) => { await action(); results.push(name); console.log(`PASS: ${name}`); };
  let session, thread, source, endpoint;
  async function document(name, text) {
    source = path.join(workspace, name); fs.writeFileSync(source, text);
    const doc = await vscode.workspace.openTextDocument(source);
    await vscode.window.showTextDocument(doc);
    await vscode.extensions.getExtension('qusaeotoman.embedlang').activate();
    return doc;
  }
  async function frame() {
    thread = (await session.customRequest('threads')).threads[0].id;
    return (await session.customRequest('stackTrace', { threadId: thread, startFrame: 0, levels: 5 })).stackFrames[0];
  }
  async function action(command, args = {}) {
    const count = stops.length;
    await vscode.commands.executeCommand(command === 'stepIn' ? 'workbench.action.debug.stepInto' : 'workbench.action.debug.continue');
    await waitFor(() => stops.length > count, `${command} stop`);
  }
  try {
    await check('real maintained Cortex-Debug adapter is installed', async () => {
      const extension = vscode.extensions.getExtension('marus25.cortex-debug');
      assert.ok(extension); await extension.activate();
      assert.equal(extension.packageJSON.version, '1.12.1');
    });
    await document('source_debug.emb', fs.readFileSync(path.join(root, 'tests/fixtures/source_debug.emb'), 'utf8'));
    vscode.debug.addBreakpoints([new vscode.SourceBreakpoint(new vscode.Location(vscode.Uri.file(source), new vscode.Position(1, 0)))]);
    await check('EmbedLang command builds ELF and starts actual VS Code DAP/MI2 session', async () => {
      const started = await vscode.commands.executeCommand('embedlang.startLocalDebug');
      assert.ok(started.ok, JSON.stringify(started));
      endpoint = started.endpoint;
      await waitFor(() => vscode.debug.activeDebugSession && stops.length, 'initial debug stop');
      session = vscode.debug.activeDebugSession;
      assert.equal(session.type, 'cortex-debug');
      await vscode.commands.executeCommand('workbench.view.debug');
      await frame();
    });
    await check('breakpoint in .emb is verified and reached in source editor', async () => {
      await action('continue');
      const top = await frame();
      assert.equal(path.resolve(top.source.path), source);
      assert.equal(top.line, 2);
      assert.ok(packets.some(message => message.type === 'response' && message.command === 'setBreakpoints' &&
        message.body?.breakpoints?.some(point => point.verified)));
      await waitFor(() => vscode.window.activeTextEditor?.document.uri.fsPath === source, 'source editor');
      await waitFor(() => vscode.window.activeTextEditor.selection.active.line === 1, 'editor selection at source breakpoint');
    });
    await check('useful top stack frame, core registers and disassembly are available', async () => {
      const top = await frame(); assert.ok(top.name); assert.ok(top.instructionPointerReference);
      const registers = await session.customRequest('read-registers', { hex: true });
      assert.ok(registers.some(register => register.number === '0'));
      const assembly = await session.customRequest('disassemble', { memoryReference: top.instructionPointerReference, instructionCount: 4 });
      assert.ok(assembly.instructions.length >= 1);
      assert.ok(assembly.instructions.some(instruction => instruction.instruction));
    });
    await check('VS Code source step-in reaches .emb lines 3, 4, 5 and 6', async () => {
      for (const line of [3, 4, 5, 6]) {
        await action('stepIn'); assert.equal((await frame()).line, line);
        await waitFor(() => vscode.window.activeTextEditor.selection.active.line === line - 1, 'source editor step location');
      }
    });
    await check('continue completes 6 times 7 with result 42 and restored stack', async () => {
      vscode.debug.removeBreakpoints(vscode.debug.breakpoints);
      await action('continue');
      const r0 = await session.customRequest('evaluate', { expression: '$r0', context: 'watch' });
      const sp = await session.customRequest('evaluate', { expression: '$sp', context: 'watch' });
      assert.match(r0.result, /(?:42|0x0*2a)/i); assert.match(sp.result, /20010000/i);
    });
    await check('stopping the session cleans up the owned local target', async () => {
      await vscode.debug.stopDebugging(session);
      await waitFor(() => !vscode.debug.activeDebugSession, 'session termination');
      await waitFor(() => new Promise(resolve => {
        const socket = net.createConnection({ host: '127.0.0.1', port: Number(endpoint.split(':')[1]) });
        socket.on('connect', () => { socket.destroy(); resolve(false); });
        socket.on('error', () => resolve(true));
      }), 'owned endpoint closure');
    });
    stops.length = 0;
    await document('pause.emb', 'fn main() -> void {\n let x: u32 = 6 * 7\n while true { x = x + 0 }\n}\n');
    await check('actual VS Code pause interrupts a running local program and can resume', async () => {
      const started = await vscode.commands.executeCommand('embedlang.startLocalDebug'); assert.ok(started.ok, JSON.stringify(started));
      await waitFor(() => vscode.debug.activeDebugSession && stops.length, 'pause session start');
      session = vscode.debug.activeDebugSession; await frame();
      for (let attempt = 0; attempt < 2; attempt++) {
        await vscode.commands.executeCommand('workbench.action.debug.continue');
        const count = stops.length;
        await new Promise(resolve => setTimeout(resolve, 200));
        assert.equal(stops.length, count, 'target should remain running until user pause');
        await vscode.commands.executeCommand('workbench.action.debug.pause');
        await waitFor(() => stops.length > count, 'DAP pause stop');
        assert.ok((await frame()).source.path.endsWith('pause.emb'));
      }
      await vscode.debug.stopDebugging(session);
      await waitFor(() => !vscode.debug.activeDebugSession, 'pause session cleanup');
    });
    fs.writeFileSync(process.env.EMBEDLANG_DEBUG_RESULTS, JSON.stringify({ passed: results.length, results,
      vscode: vscode.version, adapter: 'marus25.cortex-debug@1.12.1', hardware: false, typedLocals: false }, null, 2));
  } finally {
    tracker.dispose();
    if (vscode.debug.activeDebugSession) await vscode.debug.stopDebugging(vscode.debug.activeDebugSession);
    fs.writeFileSync(path.join(root, '.tools/cortex-debug/dap-events.json'), JSON.stringify(packets, null, 2));
  }
}
module.exports = { run };
