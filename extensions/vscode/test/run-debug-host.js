'use strict';
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const [executable, extensions] = process.argv.slice(2);
if (!executable || !extensions) throw new Error('Usage: node test/run-debug-host.js <Code executable> <isolated extensions directory>');
const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'embedlang-debug-host-'));
const workspace = path.join(folder, 'workspace with spaces & chars');
const userData = path.join(folder, 'profile');
fs.mkdirSync(workspace);
fs.mkdirSync(path.join(userData, 'User'), { recursive: true });
fs.writeFileSync(path.join(userData, 'User/settings.json'), JSON.stringify({
  'telemetry.telemetryLevel': 'off', 'update.mode': 'none', 'extensions.autoUpdate': false,
  'workbench.startupEditor': 'none', 'security.workspace.trust.startupPrompt': 'never',
  'debug.internalConsoleOptions': 'openOnSessionStart'
}));
const env = { ...process.env, EMBEDLANG_DEBUG_RESULTS: path.join(folder, 'results.json') };
delete env.ELECTRON_RUN_AS_NODE;
const child = spawn(executable, [workspace, '--new-window', '--user-data-dir', userData,
  '--extensions-dir', path.resolve(extensions), '--disable-workspace-trust', '--skip-welcome',
  '--skip-release-notes', '--disable-updates', `--extensionDevelopmentPath=${path.resolve(__dirname, '..')}`,
  `--extensionTestsPath=${path.join(__dirname, 'debug-host/index.js')}`],
{ env, windowsHide: true, shell: false, stdio: 'inherit' });
const timer = setTimeout(() => child.kill(), 180000);
child.on('error', error => { clearTimeout(timer); console.error(error); process.exitCode = 1; });
child.on('exit', code => {
  clearTimeout(timer);
  if (code !== 0 || !fs.existsSync(env.EMBEDLANG_DEBUG_RESULTS)) {
    console.error(`Debug Host failed (exit ${code}). Evidence: ${folder}`); process.exitCode = 1;
  } else console.log(fs.readFileSync(env.EMBEDLANG_DEBUG_RESULTS, 'utf8'));
});
