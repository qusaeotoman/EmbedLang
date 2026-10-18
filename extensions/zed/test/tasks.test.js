'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '../../..');
fs.mkdirSync(path.join(root, 'build'), { recursive: true });
const folder = fs.mkdtempSync(path.join(root, 'build/zed-tests-'));
const runner = path.join(root, 'extensions/zed/task.js');
function source(name, text) { const file = path.join(folder, name); fs.writeFileSync(file, text); return file; }
function run(mode, file, overrides = {}) {
  return spawnSync(process.execPath, [runner, mode], { cwd: root,
    env: { ...process.env, ZED_FILE: file || '', ...overrides }, encoding: 'utf8', windowsHide: true });
}
test('real task validates a saved source with spaces and shell metacharacters', () => {
  const result = run('validate', source('spaces & chars.emb', 'fn main() -> void {}'));
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /OK:/);
});
test('real task preserves semantic file/line/column and failure exit status', () => {
  const file = source('bad.emb', 'fn main() -> void {\n let x: bool = 10\n}');
  const result = run('validate', file);
  assert.equal(result.status, 1);
  assert.ok(result.stderr.includes(`${file}:2:16: semantic error [TYPE_MISMATCH]`), result.stderr);
});
test('real task preserves syntax diagnostics', () => {
  const result = run('validate', source('syntax.emb', 'fn main( -> void {}'));
  assert.equal(result.status, 1);
  assert.match(result.stderr, /:1:\d+: syntax error/);
});
for (const [mode, suffix, expected] of [['ir', 'ir', /func @main/], ['asm', 's', /\.cpu cortex-m4/]]) {
  test(`real ${mode} task emits a generated file identical to compiler stdout`, () => {
    const file = source(`${mode}.emb`, 'fn main() -> void { gpio_toggle(LED_GREEN) }');
    const result = run(mode, file);
    assert.equal(result.status, 0, result.stderr);
    const output = path.join(root, 'build/zed', `${path.relative(root, file)}.${suffix}`);
    const content = fs.readFileSync(output, 'utf8');
    assert.match(content, expected);
    assert.ok(result.stdout.startsWith(content));
  });
}
test('failed emission creates no misleading partial artifact', () => {
  const file = source('invalid-emit.emb', 'fn main() -> void { missing() }');
  const result = run('asm', file);
  assert.equal(result.status, 1);
  assert.equal(fs.existsSync(path.join(root, 'build/zed', `${path.relative(root, file)}.s`)), false);
});
test('missing source, unsupported mode, missing Java and missing distribution fail clearly', () => {
  const file = source('valid.emb', 'fn main() -> void {}');
  for (const [mode, sourceFile, env] of [['validate', '', {}], ['unknown', file, {}],
    ['validate', file, { EMBEDLANG_JAVA: path.join(folder, 'absent-java') }],
    ['validate', file, { EMBEDLANG_COMPILER_DIRECTORY: path.join(folder, 'absent-compiler') }]]) {
    const result = run(mode, sourceFile, env);
    assert.equal(result.status, 2, result.stderr);
    assert.match(result.stderr, /EmbedLang task:/);
  }
});
test('task template uses supported Zed fields and passes filenames through the environment', () => {
  const tasks = JSON.parse(fs.readFileSync(path.join(root, '.zed/tasks.json'), 'utf8'));
  assert.equal(tasks.length, 4);
  for (const task of tasks) {
    assert.equal(task.command, 'node');
    assert.equal(task.cwd, '$ZED_WORKTREE_ROOT');
    assert.equal(task.allow_concurrent_runs, false);
    assert.ok(!JSON.stringify(task.args).includes('$ZED_FILE'));
    assert.ok(!('problemMatcher' in task));
    assert.ok(['all', 'current'].includes(task.save));
  }
});
test('external-worktree and non-EmbedLang inputs are rejected', () => {
  for (const file of [path.resolve(root, '../external.emb'), path.join(folder, 'file.txt')]) {
    const result = run('validate', file);
    assert.equal(result.status, 2);
    assert.match(result.stderr, /EmbedLang task:/);
  }
});
test('CLI unreadable-file failure remains exit 2 without invented source diagnostics', () => {
  const result = run('validate', path.join(folder, 'not-present.emb'));
  assert.equal(result.status, 2);
  assert.ok(!result.stderr.includes('semantic error'));
});
