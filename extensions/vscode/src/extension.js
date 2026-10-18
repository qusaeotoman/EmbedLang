'use strict';
const vscode = require('vscode');
const { invocation, runCompiler, parseDiagnostics, diagnosticRange } = require('./compiler');

function activate(context) {
  require('./debug-extension').register(context);
  const diagnostics = vscode.languages.createDiagnosticCollection('embedlang');
  const output = vscode.window.createOutputChannel('EmbedLang');
  const revisions = new Map();
  let disposed = false;
  const invalidate = document => {
    const key = document.uri.toString();
    revisions.set(key, (revisions.get(key) || 0) + 1);
    diagnostics.delete(document.uri);
  };

  async function compile(document, mode, automatic = false) {
    if (!vscode.workspace.isTrusted) {
      if (!automatic) vscode.window.showWarningMessage('Trust this workspace before running the EmbedLang compiler.');
      return { ok: false, reason: 'untrusted' };
    }
    if (!document || document.languageId !== 'embedlang' || document.uri.scheme !== 'file') {
      if (!automatic) vscode.window.showWarningMessage('Open a saved .emb file first.');
      return { ok: false, reason: 'not-file' };
    }
    if (document.isDirty && !(await document.save())) return { ok: false, reason: 'save-failed' };
    if (document.isClosed || document.isDirty) return { ok: false, reason: 'stale' };
    const key = document.uri.toString();
    const revision = (revisions.get(key) || 0) + 1;
    revisions.set(key, revision);
    const version = document.version;
    const current = () => !disposed && !document.isClosed && !document.isDirty && document.version === version && revisions.get(key) === revision;
    try {
      const folder = vscode.workspace.getWorkspaceFolder(document.uri);
      if (!folder) throw new Error('Open the source folder as a VS Code workspace first.');
      const config = vscode.workspace.getConfiguration('embedlang', document.uri);
      const spec = invocation({ workspaceRoot: folder.uri.fsPath, source: document.uri.fsPath, mode,
        compilerDirectory: config.get('compilerDirectory'), javaPath: config.get('javaPath') });
      const result = await runCompiler(spec, config.get('timeoutMs'));
      if (!current()) return { ok: false, reason: 'stale' };
      const items = parseDiagnostics(result.stderr);
      const lines = document.getText().split(/\r?\n/);
      const errors = items.map(item => {
        const range = diagnosticRange(item, lines);
        const entry = new vscode.Diagnostic(new vscode.Range(range.line, range.start, range.line, range.end),
          item.message, vscode.DiagnosticSeverity.Error);
        entry.code = item.code;
        entry.source = `EmbedLang (${item.kind})`;
        return entry;
      });
      diagnostics.set(document.uri, errors);
      output.appendLine(`[${mode}] ${document.uri.fsPath}\n${result.stdout}${result.stderr}`);
      if (result.code !== 0 || errors.length) {
        if (!automatic && !errors.length) vscode.window.showErrorMessage('EmbedLang failed without a source diagnostic. See the EmbedLang output channel.');
        return { ok: false, code: result.code, diagnostics: errors.length };
      }
      if (mode === 'validate') {
        if (!automatic) vscode.window.showInformationMessage('EmbedLang: validation passed.');
        return { ok: true, diagnostics: 0 };
      }
      const preview = await vscode.workspace.openTextDocument({ content: result.stdout, language: mode === 'asm' ? 'asm' : 'plaintext' });
      await vscode.window.showTextDocument(preview, { viewColumn: vscode.ViewColumn.Beside, preview: true });
      return { ok: true, outputUri: preview.uri };
    } catch (error) {
      if (current()) {
        diagnostics.delete(document.uri);
        output.appendLine(String(error.message || error));
        if (!automatic) vscode.window.showErrorMessage(String(error.message || error));
      }
      return { ok: false, reason: 'process-error' };
    }
  }

  context.subscriptions.push(diagnostics, output,
    { dispose() { disposed = true; revisions.clear(); } },
    ...[['embedlang.validate', 'validate'], ['embedlang.emitIr', 'ir'], ['embedlang.emitAsm', 'asm']].map(([id, mode]) =>
      vscode.commands.registerCommand(id, () => compile(vscode.window.activeTextEditor?.document, mode))),
    vscode.workspace.onDidSaveTextDocument(document => {
      if (document.languageId === 'embedlang' && vscode.workspace.getConfiguration('embedlang', document.uri).get('validateOnSave'))
        void compile(document, 'validate', true);
    }),
    vscode.workspace.onDidChangeTextDocument(event => { if (event.document.languageId === 'embedlang') invalidate(event.document); }),
    vscode.workspace.onDidCloseTextDocument(document => { invalidate(document); }),
    vscode.workspace.onDidChangeConfiguration(event => {
      if (event.affectsConfiguration('embedlang')) for (const document of vscode.workspace.textDocuments) invalidate(document);
    }));
}

module.exports = { activate };
