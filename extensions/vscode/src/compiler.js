'use strict';
const path = require('node:path');
const fs = require('node:fs');
const { execFile } = require('node:child_process');

function invocation({ workspaceRoot, compilerDirectory = '', javaPath = '', mode = 'validate', source,
  env = process.env, platform = process.platform }) {
  const flags = { validate: [], ir: ['--emit-ir'], asm: ['--emit-asm'] };
  if (!Object.hasOwn(flags, mode)) throw new Error(`Unknown compiler mode: ${mode}`);
  if (!workspaceRoot || !path.isAbsolute(source)) throw new Error('A workspace and an absolute saved source path are required.');
  const distribution = path.resolve(workspaceRoot, compilerDirectory || 'compiler/build/install/embedlang');
  if (!fs.existsSync(path.join(distribution, 'lib', 'compiler.jar'))) {
    throw new Error('EmbedLang distribution not found. Run :compiler:installDist or configure embedlang.compilerDirectory.');
  }
  const executable = javaPath || (env.JAVA_HOME
    ? path.join(env.JAVA_HOME, 'bin', platform === 'win32' ? 'java.exe' : 'java') : 'java');
  return { executable, args: ['-cp', path.join(distribution, 'lib', '*'), 'embedlang.MainKt', ...flags[mode], source], cwd: workspaceRoot };
}

function runCompiler(spec, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    // No shell and no .bat interpolation: spaces and shell metacharacters stay arguments.
    execFile(spec.executable, spec.args, {
      cwd: spec.cwd, timeout: timeoutMs, maxBuffer: 4 * 1024 * 1024,
      windowsHide: true, encoding: 'utf8', shell: false
    }, (error, stdout, stderr) => {
      if (error && (typeof error.code !== 'number' || error.killed)) {
        reject(new Error(error.killed ? 'EmbedLang compiler timed out.' : `Cannot run EmbedLang: ${error.message}`));
      } else resolve({ code: error ? error.code : 0, stdout, stderr });
    });
  });
}

function parseDiagnostics(stderr) {
  const items = [];
  for (const line of stderr.split(/\r?\n/)) {
    const match = /^(.*):([1-9]\d*):([1-9]\d*): (syntax|semantic) error \[([A-Z0-9_]+)\]: (.*)$/.exec(line);
    if (match) items.push({ file: match[1], line: Number(match[2]), column: Number(match[3]),
      kind: match[4], code: match[5], message: match[6] });
  }
  return items;
}

function diagnosticRange(item, lines) {
  const line = Math.max(0, Math.min(item.line - 1, lines.length - 1));
  const points = Array.from(lines[line]);
  // ANTLR's CodePointCharStream counts code points; VS Code uses UTF-16 offsets.
  const start = points.slice(0, item.column - 1).join('').length;
  const width = points[item.column - 1]?.length || 0;
  return { line, start, end: start + width };
}

module.exports = { invocation, runCompiler, parseDiagnostics, diagnosticRange };
