'use strict';
const { test, before } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { Parser, Language, Query } = require('web-tree-sitter');
const root = path.resolve(__dirname, '..');
let parser, language;
before(async () => {
  await Parser.init();
  language = await Language.load(path.join(root, 'build/embedlang/grammars/embedlang.wasm'));
  parser = new Parser();
  parser.setLanguage(language);
});
test('parser module exports its language and has no application or WASI startup imports', () => {
  const module = new WebAssembly.Module(fs.readFileSync(path.join(root, 'build/embedlang/grammars/embedlang.wasm')));
  assert.ok(WebAssembly.Module.exports(module).some(item => item.name === 'tree_sitter_embedlang'));
  assert.ok(!WebAssembly.Module.exports(module).some(item => item.name === '_start'));
  assert.ok(WebAssembly.Module.imports(module).every(item => item.module !== 'wasi_snapshot_preview1' && item.name !== 'main'));
});

for (const file of fs.readdirSync(path.join(root, '../../examples')).filter(name => name.endsWith('.emb'))) {
  test(`real WASM parser accepts example ${file}`, () => {
    const tree = parser.parse(fs.readFileSync(path.join(root, '../../examples', file), 'utf8'));
    assert.equal(tree.rootNode.hasError, false, tree.rootNode.toString());
    tree.delete();
  });
}
for (const name of ['highlights', 'brackets', 'indents', 'outline']) {
  test(`Zed ${name} query compiles and captures actual nodes`, () => {
    const query = new Query(language, fs.readFileSync(path.join(root, `languages/embedlang/${name}.scm`), 'utf8'));
    const tree = parser.parse('fn main() -> void {\n gpio_toggle(LED_GREEN)\n}');
    assert.ok(query.captures(tree.rootNode).length > 0);
    query.delete(); tree.delete();
  });
}
test('highlight queries recognize actual builtins, types, comments and operators', () => {
  const query = new Query(language, fs.readFileSync(path.join(root, 'languages/embedlang/highlights.scm'), 'utf8'));
  const tree = parser.parse('fn main() -> void { // test\n let ready: bool = true\n gpio_mode(LED_GREEN, OUTPUT)\n oled_cursor(0, 0)\n let x: i32 = 6 * 7\n}');
  const captures = query.captures(tree.rootNode);
  for (const [name, text] of [['keyword', 'fn'], ['function', 'main'], ['type.builtin', 'bool'],
    ['boolean', 'true'], ['number', '6'], ['operator', '*'], ['comment', '// test'],
    ['constant.builtin', 'LED_GREEN'], ['function.builtin', 'oled_cursor']]) {
    assert.ok(captures.some(c => c.name === name && c.node.text === text), `${name}: ${text}`);
  }
  query.delete(); tree.delete();
});
test('editor grammar retains compiler precedence and unary nesting', () => {
  const tree = parser.parse('fn main() -> void { let x: i32 = -1 + 2 * 3 }');
  assert.equal(tree.rootNode.hasError, false);
  const expression = tree.rootNode.descendantsOfType('binary_expression')[0];
  assert.equal(expression.childForFieldName('operator').text, '+');
  assert.equal(expression.childForFieldName('right').childForFieldName('operator').text, '*');
  tree.delete();
});
test('incomplete buffers recover while strings remain unsupported', () => {
  for (const source of ['fn main() -> void {', 'fn main() -> void { oled_write_char("text") }']) {
    const tree = parser.parse(source);
    assert.equal(tree.rootNode.hasError, true);
    tree.delete();
  }
});
test('every builtin in the real Kotlin semantic table is highlighted', () => {
  const source = fs.readFileSync(path.join(root, '../../compiler/src/main/kotlin/embedlang/semantic/Builtins.kt'), 'utf8');
  const functions = [...source.matchAll(/"(\w+)" to FunctionSignature/g)].map(match => match[1]);
  const constants = [...source.split('val constants:')[1].matchAll(/"(\w+)" to Type/g)].map(match => match[1]);
  const query = new Query(language, fs.readFileSync(path.join(root, 'languages/embedlang/highlights.scm'), 'utf8'));
  const tree = parser.parse(`fn main() -> void {\n${functions.map(name => `${name}()`).join('\n')}\n${constants.map(name => `gpio_toggle(${name})`).join('\n')}\n}`);
  const captures = query.captures(tree.rootNode);
  for (const [names, capture] of [[functions, 'function.builtin'], [constants, 'constant.builtin']]) {
    for (const name of names) assert.ok(captures.some(c => c.name === capture && c.node.text === name), name);
  }
  query.delete(); tree.delete();
});
