'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const local = require('../src/local-debug');

test('debug configuration uses existing external DAP adapter without loading or monitor commands', () => {
  const config = local.configuration({ workspaceRoot: '/workspace', elf: '/workspace/build/program.elf',
    endpoint: '127.0.0.1:3333', toolchainDirectory: '/arm/bin' });
  assert.equal(config.type, 'cortex-debug'); assert.equal(config.request, 'attach');
  assert.equal(config.servertype, 'external'); assert.deepEqual(config.loadFiles, []);
  assert.deepEqual(config.overrideAttachCommands, []); assert.deepEqual(config.overrideRestartCommands, []);
  assert.ok(config.gdbPath.includes('arm-none-eabi-gdb'));
  assert.equal(config.executable, '/workspace/build/program.elf');
});
test('debug configuration rejects remote, invalid and non TCP local endpoints', () => {
  for (const endpoint of ['192.0.2.1:3333', '0.0.0.0:3333', 'localhost:3333', '127.0.0.1:0', '127.0.0.1:65536', '127.0.0.1:3333;echo bad']) {
    assert.throws(() => local.configuration({ endpoint }), /loopback/);
  }
});
test('missing repository target reports configuration error before spawning a process', async () => {
  await assert.rejects(local.startTarget({ repositoryDirectory: path.resolve(__dirname, 'not-a-repository'), elf: 'none' }), /repositoryDirectory/);
});
