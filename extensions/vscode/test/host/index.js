'use strict';
const vscode = require('vscode');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

async function waitFor(predicate) {
  const deadline = Date.now() + 10000;
  while (!predicate()) {
    if (Date.now() > deadline) throw new Error('Timed out waiting for VS Code diagnostics');
    await new Promise(resolve => setTimeout(resolve, 40));
  }
}

async function run() {
  const root = path.resolve(__dirname, '../../../..');
  const workspace = vscode.workspace.workspaceFolders[0].uri.fsPath;
  const config = vscode.workspace.getConfiguration('embedlang');
  await config.update('compilerDirectory', path.join(root, 'compiler/build/install/embedlang'), vscode.ConfigurationTarget.Workspace);
  await config.update('validateOnSave', false, vscode.ConfigurationTarget.Workspace);
  const results = [];
  async function check(name, action) { await action(); results.push(name); console.log(`PASS: ${name}`); }
  async function source(name, text) {
    const file = path.join(workspace, name);
    fs.writeFileSync(file, text);
    const document = await vscode.workspace.openTextDocument(vscode.Uri.file(file));
    await vscode.window.showTextDocument(document);
    return document;
  }
  async function replace(document, text) {
    const edit = new vscode.WorkspaceEdit();
    edit.replace(document.uri, new vscode.Range(document.positionAt(0), document.positionAt(document.getText().length)), text);
    assert.ok(await vscode.workspace.applyEdit(edit));
  }
  await check('.emb recognition and actual extension activation', async () => {
    const document = await source('recognition.emb', 'fn main() -> void {}');
    assert.equal(document.languageId, 'embedlang');
    await vscode.extensions.getExtension('qusaeotoman.embedlang').activate();
    assert.ok(vscode.extensions.getExtension('qusaeotoman.embedlang').isActive);
  });
  await check('all three compiler commands are registered', async () => {
    const commands = await vscode.commands.getCommands();
    for (const name of ['embedlang.validate', 'embedlang.emitIr', 'embedlang.emitAsm']) assert.ok(commands.includes(name));
  });
  await check('actual CLI validation and located Problems diagnostics', async () => {
    const document = await source('type mismatch & spaces.emb', 'fn main() -> void {\n    let x: bool = 10\n}');
    const result = await vscode.commands.executeCommand('embedlang.validate');
    assert.equal(result.ok, false);
    const diagnostics = vscode.languages.getDiagnostics(document.uri);
    assert.equal(diagnostics[0].code, 'TYPE_MISMATCH');
    assert.equal(diagnostics[0].range.start.line, 1);
    assert.equal(diagnostics[0].range.start.character, 18);
    assert.equal(diagnostics[0].severity, vscode.DiagnosticSeverity.Error);
  });
  await check('editing clears stale errors and manual validation saves current text', async () => {
    const document = vscode.window.activeTextEditor.document;
    await replace(document, 'fn main() -> void {}');
    await waitFor(() => vscode.languages.getDiagnostics(document.uri).length === 0);
    assert.ok(document.isDirty);
    const result = await vscode.commands.executeCommand('embedlang.validate');
    assert.ok(result.ok);
    assert.equal(document.isDirty, false);
    assert.equal(fs.readFileSync(document.uri.fsPath, 'utf8'), document.getText());
  });
  await check('real syntax error positions account for astral Unicode', async () => {
    const document = await source('unicode.emb', '😀 @');
    await vscode.commands.executeCommand('embedlang.validate');
    const errors = vscode.languages.getDiagnostics(document.uri);
    assert.ok(errors.some(item => item.range.start.character === 0 && item.range.end.character === 2));
    assert.ok(errors.some(item => item.range.start.character === 3));
  });
  await check('IR emission opens a separate output document', async () => {
    const document = await source('emit.emb', 'fn main() -> void { let x: i32 = 6 * 7 }');
    const result = await vscode.commands.executeCommand('embedlang.emitIr');
    assert.ok(result.ok);
    assert.notEqual(result.outputUri.toString(), document.uri.toString());
    const preview = await vscode.workspace.openTextDocument(result.outputUri);
    assert.match(preview.getText(), /main/);
    assert.match(preview.getText(), /i32/);
  });
  await check('assembly emission uses the unchanged ARM backend', async () => {
    await source('emit-asm.emb', 'fn main() -> void { gpio_toggle(LED_GREEN) }');
    const result = await vscode.commands.executeCommand('embedlang.emitAsm');
    assert.ok(result.ok);
    const preview = await vscode.workspace.openTextDocument(result.outputUri);
    assert.match(preview.getText(), /\.cpu cortex-m4/);
    assert.match(preview.getText(), /bl embed_gpio_toggle/);
  });
  await check('failed emission creates diagnostics and no partial preview', async () => {
    const document = await source('failed-emit.emb', 'fn main() -> void { missing() }');
    const result = await vscode.commands.executeCommand('embedlang.emitAsm');
    assert.equal(result.ok, false);
    assert.equal(result.outputUri, undefined);
    assert.equal(vscode.languages.getDiagnostics(document.uri)[0].code, 'UNDEFINED_FUNCTION');
    assert.equal(vscode.window.activeTextEditor.document.uri.toString(), document.uri.toString());
  });
  await check('validation on save updates Problems', async () => {
    await config.update('validateOnSave', true, vscode.ConfigurationTarget.Workspace);
    const document = await source('on-save.emb', 'fn main() -> void {}');
    await replace(document, 'fn main() -> void { missing() }');
    await document.save();
    await waitFor(() => vscode.languages.getDiagnostics(document.uri).some(item => item.code === 'UNDEFINED_FUNCTION'));
    await config.update('validateOnSave', false, vscode.ConfigurationTarget.Workspace);
  });
  await check('closing a source clears its Problems diagnostics', async () => {
    const uri = vscode.window.activeTextEditor.document.uri;
    await vscode.commands.executeCommand('workbench.action.closeActiveEditor');
    await waitFor(() => vscode.languages.getDiagnostics(uri).length === 0);
  });
  await check('missing compiler produces no invented source diagnostic', async () => {
    const document = await source('missing-tool.emb', 'fn main() -> void {}');
    await config.update('compilerDirectory', path.join(workspace, 'not-installed'), vscode.ConfigurationTarget.Workspace);
    const result = await vscode.commands.executeCommand('embedlang.validate');
    assert.equal(result.reason, 'process-error');
    assert.deepEqual(vscode.languages.getDiagnostics(document.uri), []);
    await config.update('compilerDirectory', path.join(root, 'compiler/build/install/embedlang'), vscode.ConfigurationTarget.Workspace);
  });
  await check('untitled buffers are not passed to the compiler', async () => {
    const document = await vscode.workspace.openTextDocument({ language: 'embedlang', content: 'fn main() -> void {}' });
    await vscode.window.showTextDocument(document);
    const result = await vscode.commands.executeCommand('embedlang.validate');
    assert.equal(result.reason, 'not-file');
  });
  fs.writeFileSync(process.env.EMBEDLANG_HOST_RESULTS, JSON.stringify({ passed: results.length, results, vscode: vscode.version }, null, 2));
}
module.exports = { run };
