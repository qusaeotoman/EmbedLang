'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { inspectComponent } = require('../debugger/wasm-format');

test('real compiled Zed component has API 0.7.0 and exported debugger hooks', () => {
  const file = path.join(__dirname, '../debugger/target/wasm32-wasip2/release/embedlang_debugger.wasm');
  const { versions, exports: names } = inspectComponent(fs.readFileSync(file));
  assert.equal(versions.length, 1);
  assert.deepEqual(versions[0], [0, 0, 0, 7, 0, 0]);
  for (const hook of ['init-extension', 'get-dap-binary', 'dap-request-kind'])
    assert.ok(names.some(name => name === hook || name.endsWith(`#${hook}`)), `Missing ${hook}`);
});

test('Zed packager rejects a core WASM module instead of claiming runtime compatibility', () => {
  assert.throws(() => inspectComponent(Buffer.from([0, 97, 115, 109, 1, 0, 0, 0])), /requires a WASI component/);
});
