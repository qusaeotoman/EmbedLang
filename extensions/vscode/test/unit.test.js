'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { invocation, runCompiler, parseDiagnostics, diagnosticRange } = require('../src/compiler');

function distribution(t) {
  const tempRoot = fs.realpathSync(os.tmpdir());
  const root = fs.mkdtempSync(path.join(tempRoot, 'embedlang-unit-'));
  fs.mkdirSync(path.join(root, 'compiler/build/install/embedlang/lib'), { recursive: true });
  fs.writeFileSync(path.join(root, 'compiler/build/install/embedlang/lib/compiler.jar'), 'fixture');
  t.after(() => {
    assert.equal(path.dirname(fs.realpathSync(root)), tempRoot);
    fs.rmSync(root, { recursive: true, force: true });
  });
  return root;
}
function node(args) { return { executable: process.execPath, args, cwd: os.tmpdir() }; }

test('Windows paths with drive colon and spaces retain source location', () => {
  assert.deepEqual(parseDiagnostics('C:\\work space\\a.emb:12:7: semantic error [TYPE_MISMATCH]: bad type'),
    [{ file: 'C:\\work space\\a.emb', line: 12, column: 7, kind: 'semantic', code: 'TYPE_MISMATCH', message: 'bad type' }]);
});
test('Unix paths, CRLF and multiple syntax errors parse without matching process errors', () => {
  const result = parseDiagnostics('/tmp/a.emb:1:1: syntax error [SYNTAX_ERROR]: missing fn\r\n/tmp/a.emb:2:4: semantic error [UNDEFINED_VARIABLE]: missing x\r\nCannot read source');
  assert.equal(result.length, 2);
  assert.equal(result[0].kind, 'syntax');
  assert.equal(result[1].line, 2);
});
test('invalid zero positions and unrelated stderr are not fabricated diagnostics', () => {
  assert.deepEqual(parseDiagnostics('x:0:1: syntax error [SYNTAX_ERROR]: nope\nx:1:0: semantic error [BAD]: nope\nUsage: embedlang'), []);
});
test('ANTLR code-point columns map to VS Code UTF-16 offsets', () => {
  assert.deepEqual(diagnosticRange({ line: 1, column: 3 }, ['a😀x']), { line: 0, start: 3, end: 4 });
  assert.deepEqual(diagnosticRange({ line: 1, column: 2 }, ['a😀x']), { line: 0, start: 1, end: 3 });
});
test('EOF and out-of-range locations clamp to a valid line endpoint', () => {
  assert.deepEqual(diagnosticRange({ line: 100, column: 200 }, ['abc', '']), { line: 1, start: 0, end: 0 });
  assert.deepEqual(diagnosticRange({ line: 1, column: 4 }, ['abc']), { line: 0, start: 3, end: 3 });
});
test('compiler invocation keeps a source with metacharacters as one argument', t => {
  const root = distribution(t), source = path.join(root, 'file & percent %.emb');
  const spec = invocation({ workspaceRoot: root, source, env: {} });
  assert.equal(spec.executable, 'java');
  assert.deepEqual(spec.args, ['-cp', path.join(root, 'compiler/build/install/embedlang/lib/*'), 'embedlang.MainKt', source]);
});
test('IR and assembly select the existing CLI flags', t => {
  const root = distribution(t);
  for (const [mode, flag] of [['ir', '--emit-ir'], ['asm', '--emit-asm']]) {
    const spec = invocation({ workspaceRoot: root, source: path.join(root, 'a.emb'), mode });
    assert.equal(spec.args[3], flag);
  }
});
test('configured Java and JAVA_HOME are resolved without command concatenation', t => {
  const root = distribution(t), options = { workspaceRoot: root, source: path.join(root, 'a.emb') };
  assert.equal(invocation({ ...options, javaPath: '/custom/java with spaces', env: {} }).executable, '/custom/java with spaces');
  assert.equal(invocation({ ...options, env: { JAVA_HOME: '/jdk' }, platform: 'win32' }).executable, path.join('/jdk', 'bin', 'java.exe'));
});
test('missing distribution fails with installation guidance', () => {
  assert.throws(() => invocation({ workspaceRoot: os.tmpdir(), source: path.join(os.tmpdir(), 'a.emb') }), /installDist/);
});
test('unknown mode is rejected before process execution', () => {
  assert.throws(() => invocation({ mode: 'flash' }), /Unknown compiler mode/);
});
test('process runner captures stdout without shell expansion', async () => {
  const literal = 'literal & echo injected %HOME% $(echo secret)';
  const result = await runCompiler(node(['-e', 'process.stdout.write(process.argv[1])', literal]));
  assert.equal(result.code, 0);
  assert.equal(result.stdout, literal);
});
test('compiler exit 1 preserves located stderr instead of treating it as a spawn failure', async () => {
  const result = await runCompiler(node(['-e', 'console.error("a.emb:2:3: semantic error [TYPE_MISMATCH]: bad");process.exit(1)']));
  assert.equal(result.code, 1);
  assert.equal(parseDiagnostics(result.stderr)[0].column, 3);
});
test('usage/file exit 2 remains a nonlocated compiler failure', async () => {
  const result = await runCompiler(node(['-e', 'console.error("Cannot read source");process.exit(2)']));
  assert.equal(result.code, 2);
  assert.deepEqual(parseDiagnostics(result.stderr), []);
});
test('missing executable produces a process error', async () => {
  await assert.rejects(runCompiler({ executable: path.join(os.tmpdir(), 'embedlang-missing-java-07102026'), args: [], cwd: os.tmpdir() }), /Cannot run EmbedLang/);
});
test('timeout terminates a hung process', async () => {
  await assert.rejects(runCompiler(node(['-e', 'setInterval(() => {}, 1000)']), 100), /timed out/);
});
test('manifest registers .emb, four commands and restricted executable settings', () => {
  const manifest = require('../package.json');
  assert.deepEqual(manifest.contributes.languages[0].extensions, ['.emb']);
  assert.equal(manifest.contributes.commands.length, 4);
  assert.equal(manifest.capabilities.untrustedWorkspaces.supported, 'limited');
  assert.ok(manifest.capabilities.untrustedWorkspaces.restrictedConfigurations.includes('embedlang.javaPath'));
  assert.ok(manifest.contributes.commands.every(command => command.enablement.includes('isWorkspaceTrusted')));
});
test('language configuration matches supported comments/brackets and excludes string autoclosing', () => {
  const config = require('../language-configuration.json');
  assert.equal(config.comments.lineComment, '//');
  assert.deepEqual(config.brackets, [['{', '}'], ['(', ')']]);
  assert.ok(!JSON.stringify(config.autoClosingPairs).includes('"open":"\\""'));
});
test('real TextMate tokenizer recognizes comments, types, builtins, functions and numbers', async () => {
  const textmate = require('vscode-textmate');
  const onig = require('vscode-oniguruma');
  const wasm = fs.readFileSync(require.resolve('vscode-oniguruma/release/onig.wasm'));
  await onig.loadWASM(wasm.buffer.slice(wasm.byteOffset, wasm.byteOffset + wasm.byteLength));
  const registry = new textmate.Registry({
    onigLib: Promise.resolve({ createOnigScanner: patterns => new onig.OnigScanner(patterns), createOnigString: value => new onig.OnigString(value) }),
    loadGrammar: async () => require('../syntaxes/embedlang.tmLanguage.json')
  });
  const grammar = await registry.loadGrammar('source.embedlang');
  const source = 'fn add(x: u32) -> bool { return gpio_read(BUTTON_1) && x >= 10 } // let fake: i32';
  const tokens = grammar.tokenizeLine(source).tokens;
  const has = (word, scope) => tokens.some(token => source.slice(token.startIndex, token.endIndex) === word && token.scopes.includes(scope));
  assert.ok(has('fn', 'keyword.control.embedlang'));
  assert.ok(has('add', 'entity.name.function.embedlang'));
  assert.ok(has('u32', 'storage.type.embedlang'));
  assert.ok(has('gpio_read', 'support.function.embedlang'));
  assert.ok(has('BUTTON_1', 'constant.other.embedlang'));
  assert.ok(has('10', 'constant.numeric.integer.embedlang'));
  assert.ok(tokens.filter(token => token.startIndex >= source.indexOf('//')).every(token => token.scopes.includes('comment.line.double-slash.embedlang')));
  assert.ok(grammar.tokenizeLine('oled_write_char(84)').tokens.some(token => token.scopes.includes('support.function.embedlang')));
  registry.dispose();
});
