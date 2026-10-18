'use strict';
const vscode = require('vscode');
const path = require('node:path');
const local = require('./local-debug');

function register(context) {
  const output = vscode.window.createOutputChannel('EmbedLang Local Debug');
  let owned = null, starting = false;
  const cleanup = () => { owned?.process.kill(); owned = null; };
  context.subscriptions.push(output, { dispose: cleanup }, vscode.debug.onDidTerminateDebugSession(session => {
    if (owned && session.configuration.__embedlangLocal === owned.endpoint) cleanup();
  }));
  context.subscriptions.push(vscode.commands.registerCommand('embedlang.startLocalDebug', async () => {
    if (!vscode.workspace.isTrusted) return { ok: false, reason: 'untrusted' };
    if (owned || starting) return { ok: false, reason: 'already-running' };
    const document = vscode.window.activeTextEditor?.document;
    if (!document || document.languageId !== 'embedlang' || document.uri.scheme !== 'file') {
      vscode.window.showWarningMessage('Open a saved .emb source first.');
      return { ok: false, reason: 'not-file' };
    }
    if (!vscode.extensions.getExtension('marus25.cortex-debug')) {
      vscode.window.showErrorMessage('Install Cortex-Debug (marus25.cortex-debug) before starting local EmbedLang debugging.');
      return { ok: false, reason: 'adapter-missing' };
    }
    starting = true;
    try {
      if (document.isDirty && !(await document.save())) return { ok: false, reason: 'save-failed' };
      const version = document.version;
      const folder = vscode.workspace.getWorkspaceFolder(document.uri);
      if (!folder) throw new Error('Open the source folder as a workspace first.');
      const root = folder.uri.fsPath;
      const config = vscode.workspace.getConfiguration('embedlang', document.uri);
      const toolchainDirectory = config.get('localDebug.toolchainDirectory') || '';
      const elf = await local.build({ workspaceRoot: root, source: document.uri.fsPath,
        compilerDirectory: config.get('compilerDirectory'), javaPath: config.get('javaPath'), toolchainDirectory });
      if (!vscode.workspace.isTrusted || document.isClosed || document.isDirty || document.version !== version)
        throw new Error('Source or workspace trust changed during build. Save and start again.');
      owned = await local.startTarget({ elf, repositoryDirectory: path.resolve(root, config.get('localDebug.repositoryDirectory') || '.'),
        pythonPath: config.get('localDebug.pythonPath'), pythonModulePath: config.get('localDebug.pythonModulePath'), output });
      const debug = local.configuration({ workspaceRoot: root, elf, endpoint: owned.endpoint, toolchainDirectory });
      debug.__embedlangLocal = owned.endpoint;
      if (!(await vscode.debug.startDebugging(folder, debug))) { cleanup(); return { ok: false, reason: 'launch-failed' }; }
      output.appendLine(`Local emulator connected through Cortex-Debug: ${owned.endpoint}`);
      return { ok: true, elf, endpoint: owned.endpoint };
    } catch (error) {
      cleanup(); output.appendLine(String(error));
      vscode.window.showErrorMessage(`EmbedLang local debug: ${error.message}`);
      return { ok: false, reason: 'process-error' };
    } finally { starting = false; }
  }));
}
module.exports = { register };
