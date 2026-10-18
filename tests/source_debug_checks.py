"""Real ELF/GDB source-line tests over the existing localhost Unicorn RSP target."""
import argparse
import base64
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import unittest

from elftools.elf.elffile import ELFFile
import gdb_connection_checks as connection

ROOT = connection.ROOT
OUTPUT = ROOT / 'build/source-debug'
SOURCE = OUTPUT / 'source directory & spaces/source_debug.emb'
ELF = OUTPUT / 'mapped.elf'
TOOLS = None


def emit(source, debug=False, unicode_api=False):
    java_home = os.environ.get('JAVA_HOME')
    java = str(Path(java_home) / 'bin' / ('java.exe' if os.name == 'nt' else 'java')) if java_home else 'java'
    classpath = str(ROOT / 'compiler/build/install/embedlang/lib/*')
    if unicode_api:
        # The current Windows JDK launcher loses some non-ASCII argv characters.
        # This separate API test sends only base64 ASCII arguments, then reads
        # the actual Unicode source file and its IR source path inside the JVM.
        return subprocess.run([java, '-cp', classpath, str(ROOT / 'tests/fixtures/EmitDebugLines.java'),
            base64.b64encode(source.as_posix().encode('utf-8')).decode('ascii')],
            cwd=ROOT, check=True, capture_output=True, text=True).stdout
    args = [java, '-cp', classpath, 'embedlang.MainKt', '--emit-asm']
    if debug:
        args += ['--debug-lines']
    # Relative input deliberately resolves from compiler cwd, not assembler cwd.
    args += [str(source.relative_to(ROOT))]
    return subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True).stdout


def assemble(source, name, debug=False, unicode_api=False):
    assembly = OUTPUT / f'{name}.s'
    assembly.write_text(emit(source, debug, unicode_api), encoding='utf-8')
    obj, elf = OUTPUT / f'{name}.o', OUTPUT / f'{name}.elf'
    subprocess.run([TOOLS.assembler, '-mcpu=cortex-m4', '-mthumb', '-g', '--gdwarf-4',
                    '-o', str(obj), str(assembly)], cwd=OUTPUT, check=True)
    subprocess.run([TOOLS.linker, '-Ttext=0x10000', '-e', 'main', '-o', str(elf), str(obj)],
                   cwd=OUTPUT, check=True)
    return elf


def text_bytes(elf):
    with elf.open('rb') as stream:
        return ELFFile(stream).get_section_by_name('.text').data()


def rows(elf):
    result = []
    with elf.open('rb') as stream:
        image = ELFFile(stream)
        dwarf = image.get_dwarf_info()
        for unit in dwarf.iter_CUs():
            lines = dwarf.line_program_for_CU(unit)
            if not lines:
                continue
            for entry in lines.get_entries():
                state = entry.state
                if state is None or state.end_sequence:
                    continue
                file = lines['file_entry'][state.file - 1]
                directory = lines['include_directory'][file.dir_index - 1].decode('utf-8') if file.dir_index else ''
                result.append((Path(directory) / file.name.decode('utf-8'), state))
    return result


class SourceDebugChecks(unittest.TestCase):
    def test_original_absolute_path_lines_columns_and_non_statement_rows(self):
        mapped = rows(ELF)
        self.assertTrue(mapped)
        self.assertEqual({file for file, _ in mapped}, {SOURCE})
        self.assertEqual({state.line for _, state in mapped if state.is_stmt}, {2, 3, 4, 5, 6, 10})
        self.assertTrue(all(state.column == 5 for _, state in mapped if state.is_stmt))
        self.assertEqual({state.line for _, state in mapped if not state.is_stmt}, {1, 9})

    def test_debug_and_plain_machine_code_is_identical(self):
        self.assertEqual(text_bytes(ELF), text_bytes(OUTPUT / 'plain.elf'))

    def test_full_arm_regression_fixture_retains_identical_machine_code(self):
        fixture = ROOT / 'tests/fixtures/arm_execution.emb'
        plain = assemble(fixture, 'arm-plain')
        mapped = assemble(fixture, 'arm-mapped', debug=True)
        self.assertEqual(text_bytes(plain), text_bytes(mapped))

    def test_utf8_IR_source_filename_survives_elf_mapping(self):
        source = SOURCE.parent / 'source_Ω.emb'
        source.write_text(SOURCE.read_text(encoding='utf-8'), encoding='utf-8')
        mapped = assemble(source, 'unicode-mapped', debug=True, unicode_api=True)
        self.assertEqual({file for file, _ in rows(mapped)}, {source})

    def test_real_gdb_file_line_breakpoint_and_source_steps(self):
        process = subprocess.Popen([sys.executable, str(ROOT / 'tools/debug/unicorn_rsp.py'),
            '--elf', str(ELF), '--entry', 'main', '--port', '0'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ready = queue.Queue()
            threading.Thread(target=lambda: ready.put(process.stdout.readline()), daemon=True).start()
            greeting = ready.get(timeout=15).strip()
            self.assertTrue(greeting.startswith('RSP_READY 127.0.0.1:'), greeting)
            script = ['set pagination off', 'set confirm off', 'set auto-load off', 'set remotetimeout 5',
                      f'file "{ELF.as_posix()}"', f'target remote {greeting.split()[1]}',
                      f'break "{SOURCE.as_posix()}":2', 'continue',
                      'echo SOURCE_STOP_2\\n', 'info line *$pc']
            for line in range(3, 7):
                script += ['step', f'echo SOURCE_STOP_{line}\\n', 'info line *$pc']
            script += ['delete breakpoints', f'break *{connection.rsp.RETURN_ADDRESS:#x}', 'continue',
                       f'if $r0 != 42 || $sp != {connection.rsp.INITIAL_SP:#x}', '  quit 1', 'end',
                       'printf "SOURCE_RESULT=%u SP=0x%x\\n", $r0, $sp', 'detach', 'quit']
            command_file = OUTPUT / 'source-checks.gdb'
            command_file.write_text('\n'.join(script) + '\n', encoding='utf-8')
            result = subprocess.run([TOOLS.gdb, '-nx', '-nh', '-batch', '-x', str(command_file)],
                capture_output=True, text=True, timeout=45)
            (OUTPUT / 'source-gdb-session.log').write_text(result.stdout + result.stderr, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for line in range(2, 7):
                self.assertRegex(result.stdout, rf'SOURCE_STOP_{line}\nLine {line} of ".*source_debug\.emb"')
            self.assertIn('SOURCE_RESULT=42 SP=0x20010000', result.stdout)
            process.wait(timeout=5)
            self.assertEqual(process.returncode, 0, process.stderr.read())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
            process.stderr.close()


def main():
    global TOOLS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assembler', default='arm-none-eabi-as')
    parser.add_argument('--linker', default='arm-none-eabi-ld')
    parser.add_argument('--gdb', default='arm-none-eabi-gdb')
    TOOLS = parser.parse_args()
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    SOURCE.write_text((ROOT / 'tests/fixtures/source_debug.emb').read_text(encoding='utf-8'), encoding='utf-8')
    assemble(SOURCE, 'plain')
    assemble(SOURCE, 'mapped', debug=True)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SourceDebugChecks))
    (OUTPUT / 'result.json').write_text(json.dumps({'tests': result.testsRun, 'failures': len(result.failures),
        'errors': len(result.errors), 'skipped': len(result.skipped), 'hardware': False,
        'typed_locals': False, 'editor_debugging': False}, indent=2), encoding='utf-8')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
