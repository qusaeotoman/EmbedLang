'use strict';
// Read component sections and embedded core modules; do not mistake a core .wasm
// for the component expected by current Zed. Actual runtime loading is tested in Zed.
const COMPONENT = Buffer.from([0, 97, 115, 109, 13, 0, 1, 0]);
const CORE = Buffer.from([0, 97, 115, 109, 1, 0, 0, 0]);

function inspectComponent(bytes) {
  if (!bytes.subarray(0, 8).equals(COMPONENT)) throw new Error('Zed requires a WASI component; build with --target wasm32-wasip2.');
  const versions = [], exports = [];
  function scan(binary) {
    const component = binary.subarray(0, 8).equals(COMPONENT);
    if (!component && !binary.subarray(0, 8).equals(CORE)) throw new Error('Invalid embedded WASM header');
    if (!component) exports.push(...WebAssembly.Module.exports(new WebAssembly.Module(binary)).map(item => item.name));
    let offset = 8;
    function number() {
      let value = 0, shift = 0, next;
      do { if (offset >= binary.length || shift > 28) throw new Error('Invalid WASM length');
        next = binary[offset++]; value += (next & 127) * 2 ** shift; shift += 7;
      } while (next & 128);
      return value;
    }
    while (offset < binary.length) {
      const id = binary[offset++], length = number(), end = offset + length;
      if (end > binary.length) throw new Error('Truncated WASM section');
      if (id === 0) {
        const nameLength = number(), name = binary.subarray(offset, offset + nameLength).toString('utf8');
        offset += nameLength;
        if (name === 'zed:api-version') versions.push(Array.from(binary.subarray(offset, end)));
      } else if (component && (id === 1 || id === 4)) scan(binary.subarray(offset, end));
      offset = end;
    }
  }
  scan(bytes);
  return { versions, exports };
}
module.exports = { inspectComponent };
