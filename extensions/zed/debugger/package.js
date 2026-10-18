'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { inspectComponent } = require('./wasm-format');
// Package an already-built module. External adapters/toolchains are not bundled.
const destination = path.join(__dirname, '../build/embedlang-debugger');
const wasm = path.join(__dirname, 'target/wasm32-wasip2/release/embedlang_debugger.wasm');
if (!fs.existsSync(wasm)) throw new Error('Build the debugger with cargo --target wasm32-wasip2 --release first.');
inspectComponent(fs.readFileSync(wasm));
fs.mkdirSync(destination, { recursive: true });
fs.copyFileSync(wasm, path.join(destination, 'extension.wasm'));
fs.copyFileSync(path.join(__dirname, 'extension.toml'), path.join(destination, 'extension.toml'));
fs.copyFileSync(path.join(__dirname, 'THIRD_PARTY.md'), path.join(destination, 'THIRD_PARTY.md'));
fs.cpSync(path.join(__dirname, 'licenses'), path.join(destination, 'licenses'), { recursive: true });
fs.cpSync(path.join(__dirname, 'debug_adapter_schemas'), path.join(destination, 'debug_adapter_schemas'), { recursive: true });
console.log(`Unpacked local Zed debugger: ${destination}`);
