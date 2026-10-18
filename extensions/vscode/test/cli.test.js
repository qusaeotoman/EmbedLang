'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { invocation, runCompiler, parseDiagnostics } = require('../src/compiler');
const root = path.resolve(__dirname, '../../..');

async function compile(t, text, mode = 'validate') {
  const tempRoot = fs.realpathSync(os.tmpdir());
  const dir = fs.mkdtempSync(path.join(tempRoot, 'embedlang-cli-'));
  t.after(() => {
    assert.equal(path.dirname(fs.realpathSync(dir)), tempRoot);
    fs.rmSync(dir, { recursive: true, force: true });
  });
  const source = path.join(dir, 'file with spaces & %.emb');
  fs.writeFileSync(source, text);
  return runCompiler(invocation({ workspaceRoot: root, source, mode }));
}
test('real CLI validates a source whose filename contains spaces and metacharacters', async t => {
  const result = await compile(t, 'fn main() -> void {}');
  assert.equal(result.code, 0);
  assert.match(result.stdout, /OK:/);
});
test('real CLI semantic error retains original source line/column', async t => {
  const result = await compile(t, 'fn main() -> void {\n    let x: bool = 10\n}');
  assert.equal(result.code, 1);
  const error = parseDiagnostics(result.stderr)[0];
  assert.equal(error.line, 2);
  assert.equal(error.column, 19);
  assert.equal(error.code, 'TYPE_MISMATCH');
});
test('real syntax diagnostics are recognized', async t => {
  const result = await compile(t, 'fn main() -> void { @ }');
  assert.equal(result.code, 1);
  assert.ok(parseDiagnostics(result.stderr).every(item => item.kind === 'syntax'));
  assert.ok(parseDiagnostics(result.stderr).length);
});
test('real CLI emits typed IR', async t => {
  const result = await compile(t, 'fn main() -> void { let x: i32 = 6 * 7 }', 'ir');
  assert.equal(result.code, 0);
  assert.match(result.stdout, /main/);
  assert.match(result.stdout, /i32/);
});
test('real CLI emits ARM assembly', async t => {
  const result = await compile(t, 'fn main() -> void { gpio_toggle(LED_GREEN) }', 'asm');
  assert.equal(result.code, 0);
  assert.match(result.stdout, /\.cpu cortex-m4/);
  assert.match(result.stdout, /bl embed_gpio_toggle/);
});
test('failed emission yields no partial preview content', async t => {
  for (const mode of ['ir', 'asm']) {
    const result = await compile(t, 'fn main() -> void { missing() }', mode);
    assert.equal(result.code, 1);
    assert.equal(result.stdout, '');
    assert.equal(parseDiagnostics(result.stderr)[0].code, 'UNDEFINED_FUNCTION');
  }
});
