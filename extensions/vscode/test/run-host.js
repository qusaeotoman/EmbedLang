'use strict';
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');

const executable = process.argv[2];
const untrusted = process.argv.includes('--untrusted');
if (!executable || !fs.existsSync(executable)) throw new Error('Usage: node test/run-host.js <absolute Code executable> [--untrusted]');
const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'embedlang-vscode-tests-'));
const workspace = path.join(folder, 'workspace with spaces & chars');
const userData = path.join(folder, 'user-data');
fs.mkdirSync(workspace);
fs.mkdirSync(path.join(userData, 'User'), { recursive: true });
fs.writeFileSync(path.join(userData, 'User/settings.json'), JSON.stringify({
  'security.workspace.trust.startupPrompt': 'never',
  'security.workspace.trust.emptyWindow': false,
  'telemetry.telemetryLevel': 'off',
  'update.mode': 'none',
  'extensions.autoUpdate': false,
  'workbench.startupEditor': 'none'
}));
const resultFile = path.join(folder, 'results.json');
const args = [workspace, '--new-window', '--user-data-dir', userData,
  '--extensions-dir', path.join(folder, 'extensions'), '--disable-extensions',
  '--skip-welcome', '--skip-release-notes', '--disable-updates',
  `--extensionDevelopmentPath=${path.resolve(__dirname, '..')}`,
  `--extensionTestsPath=${path.resolve(__dirname, 'host', untrusted ? 'untrusted.js' : 'index.js')}`];
if (!untrusted) args.push('--disable-workspace-trust');
const env = { ...process.env, EMBEDLANG_HOST_RESULTS: resultFile };
delete env.ELECTRON_RUN_AS_NODE;
const child = spawn(executable, args, { env, windowsHide: true, stdio: 'inherit', shell: false });
const timer = setTimeout(() => child.kill(), 180000);
child.on('error', error => { clearTimeout(timer); console.error(error); process.exitCode = 1; });
child.on('exit', code => {
  clearTimeout(timer);
  if (code !== 0 || !fs.existsSync(resultFile)) {
    console.error(`VS Code Host tests failed (exit ${code}); no success claimed. Evidence: ${folder}`);
    process.exitCode = 1;
  } else {
    const results = JSON.parse(fs.readFileSync(resultFile));
    console.log(JSON.stringify(results, null, 2));
    console.log(`Isolated test evidence: ${folder}`);
  }
});
