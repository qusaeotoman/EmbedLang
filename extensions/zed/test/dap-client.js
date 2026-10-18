'use strict';
const { spawn } = require('node:child_process');

// Test-only DAP client. Production protocol translation belongs to CDT, not this project.
class DapClient {
  constructor(adapter) {
    this.child = spawn(process.execPath, [adapter], { shell: false, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] });
    this.sequence = 0; this.pending = new Map(); this.events = []; this.trace = []; this.buffer = Buffer.alloc(0);
    this.child.stdout.on('data', data => {
      this.buffer = Buffer.concat([this.buffer, data]);
      while (true) {
        const end = this.buffer.indexOf('\r\n\r\n'); if (end < 0) break;
        const length = Number(/Content-Length: (\d+)/i.exec(this.buffer.subarray(0, end).toString())[1]);
        if (this.buffer.length < end + 4 + length) break;
        const message = JSON.parse(this.buffer.subarray(end + 4, end + 4 + length));
        this.buffer = this.buffer.subarray(end + 4 + length); this.trace.push(message);
        if (message.type === 'event') this.events.push(message);
        if (message.type === 'response') {
          const pending = this.pending.get(message.request_seq);
          if (pending) { clearTimeout(pending.timer); this.pending.delete(message.request_seq);
            if (message.success) pending.resolve(message.body || {});
            else pending.reject(new Error(`${message.command}: ${message.message} ${JSON.stringify(message.body)}`)); }
        }
      }
    });
    this.child.stderr.on('data', data => this.trace.push({ stderr: data.toString() }));
    this.child.on('error', error => this.fail(error));
    this.child.on('exit', code => this.fail(new Error(`Adapter exited: ${code}`)));
  }
  fail(error) { for (const pending of this.pending.values()) { clearTimeout(pending.timer); pending.reject(error); } this.pending.clear(); }
  request(command, args = {}) {
    const seq = ++this.sequence;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { this.pending.delete(seq); reject(new Error(`DAP timeout: ${command}`)); }, 20000);
      this.pending.set(seq, { resolve, reject, timer });
      const message = { seq, type: 'request', command, arguments: args }; this.trace.push(message);
      const body = Buffer.from(JSON.stringify(message));
      this.child.stdin.write(Buffer.concat([Buffer.from(`Content-Length: ${body.length}\r\n\r\n`), body]));
    });
  }
  async event(name, after = 0) {
    const deadline = Date.now() + 20000;
    while (Date.now() < deadline) {
      const found = this.events.slice(after).find(event => event.event === name); if (found) return found.body;
      await new Promise(resolve => setTimeout(resolve, 20));
    }
    throw new Error(`DAP event timeout: ${name}`);
  }
  stop() { this.child.kill(); this.fail(new Error('Test cleanup')); }
}
module.exports = { DapClient };
