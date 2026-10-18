'use strict';
// Reuse the editor-independent, tested CLI adapter; no VS Code APIs are loaded.
const { invocation, runCompiler } = require('../vscode/src/compiler');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

async function main(mode, env = process.env, root = process.cwd()) {
  if (mode === 'build') {
    const windows = process.platform === 'win32';
    const child = spawnSync(windows ? (env.ComSpec || 'cmd.exe') : './gradlew', windows
      ? ['/d', '/s', '/c', 'gradlew.bat --no-daemon :compiler:installDist']
      : ['--no-daemon', ':compiler:installDist'],
    { cwd: root, env, stdio: 'inherit', windowsHide: true, timeout: 300000, shell: false });
    if (child.error) throw child.error;
    return child.status ?? 2;
  }
  const source = env.ZED_FILE;
  if (!source || !path.isAbsolute(source) || path.extname(source) !== '.emb') {
    throw new Error('Open and save a local .emb file first (ZED_FILE is required).');
  }
  const relative = path.relative(root, source);
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    throw new Error('The source must be inside the EmbedLang worktree.');
  }
  const result = await runCompiler(invocation({ workspaceRoot: root, source, mode,
    compilerDirectory: env.EMBEDLANG_COMPILER_DIRECTORY || '', javaPath: env.EMBEDLANG_JAVA || '', env }));
  // Keep original file:line:column diagnostics intact for terminal navigation.
  process.stderr.write(result.stderr);
  if (result.code !== 0) return result.code;
  if (mode === 'validate') process.stdout.write(result.stdout);
  else {
    const output = path.join(root, 'build', 'zed', `${relative}.${mode === 'ir' ? 'ir' : 's'}`);
    fs.mkdirSync(path.dirname(output), { recursive: true });
    fs.writeFileSync(output, result.stdout, 'utf8');
    process.stdout.write(result.stdout);
    console.log(`\nGenerated: ${output}`);
  }
  return 0;
}

if (require.main === module) main(process.argv[2]).then(code => { process.exitCode = code; })
  .catch(error => { console.error(`EmbedLang task: ${error.message}`); process.exitCode = 2; });
module.exports = { main };
