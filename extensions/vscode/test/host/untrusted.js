'use strict';
const vscode = require('vscode');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

async function run() {
  assert.equal(vscode.workspace.isTrusted, false, 'This test must use an isolated untrusted workspace');
  const file = path.join(vscode.workspace.workspaceFolders[0].uri.fsPath, 'restricted.emb');
  fs.writeFileSync(file, 'fn main() -> void {}');
  const document = await vscode.workspace.openTextDocument(vscode.Uri.file(file));
  await vscode.window.showTextDocument(document);
  assert.equal(document.languageId, 'embedlang');
  await vscode.extensions.getExtension('qusaeotoman.embedlang').activate();
  for (const command of ['embedlang.validate', 'embedlang.emitIr', 'embedlang.emitAsm', 'embedlang.startLocalDebug']) {
    const result = await vscode.commands.executeCommand(command);
    assert.equal(result.reason, 'untrusted');
  }
  assert.deepEqual(vscode.languages.getDiagnostics(document.uri), []);
  fs.writeFileSync(process.env.EMBEDLANG_HOST_RESULTS, JSON.stringify({ passed: 1, results: ['Restricted Mode retains language recognition and blocks all compiler commands'], vscode: vscode.version }, null, 2));
}
module.exports = { run };
