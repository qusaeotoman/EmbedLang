"""Local GDB/RSP integration checks; no STM32 peripherals or editor debug UI.

Builds generated diagnostic_probe code into an isolated host-only ELF, then
drives real arm-none-eabi-gdb through localhost TCP against Unicorn.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading
import unittest

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('unicorn_rsp', ROOT / 'tools/debug/unicorn_rsp.py')
rsp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rsp)
OUTPUT = ROOT / 'build/gdb-poc'
ELF = OUTPUT / 'probe.elf'
GDB = None


def build(assembler, linker):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    java_home = os.environ.get('JAVA_HOME')
    java = str(Path(java_home) / 'bin' / ('java.exe' if os.name == 'nt' else 'java')) if java_home else 'java'
    jars = ROOT / 'compiler/build/install/embedlang/lib'
    generated = subprocess.run([java, '-cp', str(jars / '*'), 'embedlang.MainKt', '--emit-asm',
        str(ROOT / 'examples/diagnostic_probe.emb')], check=True, capture_output=True, text=True).stdout
    assembly = OUTPUT / 'probe.s'
    assembly.write_text(generated, encoding='utf-8')
    subprocess.run([assembler, '-mcpu=cortex-m4', '-mthumb', '-g', '-o', str(OUTPUT / 'probe.o'), str(assembly)], check=True)
    subprocess.run([linker, '-Ttext=0x10000', '-e', 'main', '-o', str(ELF), str(OUTPUT / 'probe.o')], check=True)


class ConnectionChecks(unittest.TestCase):
    def target(self):
        return rsp.Target(ELF, 'main')

    def test_generated_elf_has_function_symbols_and_assembly_lines_only(self):
        with ELF.open('rb') as stream:
            image = ELFFile(stream)
            self.assertEqual(image['e_machine'], 'EM_ARM')
            self.assertTrue(image.get_section_by_name('.symtab').get_symbol_by_name('embed_fn_diagnostic_probe'))
            files = []
            dwarf = image.get_dwarf_info()
            for cu in dwarf.iter_CUs():
                lines = dwarf.line_program_for_CU(cu)
                if lines:
                    files += [file.name.decode() for file in lines['file_entry']]
            self.assertTrue(any(file.endswith('probe.s') for file in files), files)
            self.assertFalse(any(file.endswith('.emb') for file in files))

    def test_target_description_is_cortex_m_and_readable(self):
        target = self.target()
        self.assertIn('armv7e-m', rsp.XML)
        self.assertIn('org.gnu.gdb.arm.m-profile', rsp.XML)
        self.assertEqual(len(bytes.fromhex(target.handle('g'))), 17 * 4)
        self.assertTrue(int.from_bytes(bytes.fromhex(target.handle('p10')), 'little') & (1 << 24))
        self.assertEqual(target.handle('qXfer:features:read:target.xml:0,ffff'), 'l' + rsp.XML)

    def test_unmapped_memory_and_oversize_reads_fail(self):
        target = self.target()
        self.assertEqual(target.handle('m40000000,4'), 'E01')
        self.assertEqual(target.handle('m10000,1001'), 'E01')

    def test_infinite_virtual_loop_stops_at_execution_budget(self):
        target = self.target()
        pc = target.cpu.reg_read(rsp.arm.UC_ARM_REG_PC)
        target.cpu.mem_write(pc, b'\xfe\xe7')  # Thumb branch to itself, test RAM only.
        self.assertEqual(target.resume(), 'T02thread:1;')
        self.assertEqual(target.cpu.reg_read(rsp.arm.UC_ARM_REG_PC), pc)

    def test_interactive_execution_polls_and_honors_interrupt(self):
        target = self.target()
        pc = target.cpu.reg_read(rsp.arm.UC_ARM_REG_PC)
        target.cpu.mem_write(pc, b'\xfe\xe7')
        polls = []
        def interrupt():
            polls.append(True)
            return len(polls) == 3
        self.assertEqual(target.resume(interrupt=interrupt), 'T02thread:1;')
        self.assertEqual(len(polls), 3)
        self.assertEqual(target.handle('!'), 'OK')

    def test_writes_flash_monitor_and_unsupported_commands_are_not_implemented(self):
        target = self.target()
        before = target.handle('m10000,10')
        for command in ['M10000,2:0000', 'P0=00000000', 'vFlashErase:08000000,4000',
                        'qRcmd,7265736574', 'vMustReplyEmpty']:
            self.assertEqual(target.handle(command), '')
        self.assertEqual(target.handle('m10000,10'), before)

    def test_loader_rejects_missing_entry_and_excess_arguments(self):
        with self.assertRaises(ValueError):
            rsp.Target(ELF, 'not_a_function')
        with self.assertRaises(ValueError):
            rsp.Target(ELF, 'main', [1, 2, 3, 4, 5])

    def test_bad_checksum_is_nacked_before_valid_request(self):
        # Real TCP packet framing, including a request split across writes.
        with socket.socket() as server:
            server.bind(('127.0.0.1', 0))
            server.listen(1)
            errors = []
            def serve():
                try:
                    connection, _ = server.accept()
                    with connection:
                        rsp.session(connection, self.target())
                except Exception as error:
                    errors.append(error)
            worker = threading.Thread(target=serve, daemon=True)
            worker.start()
            with socket.create_connection(server.getsockname(), timeout=5) as client:
                client.sendall(b'$?#00')
                self.assertEqual(client.recv(1), b'-')
                request = rsp.frame('?')
                for part in [request[:2], request[2:]]:
                    client.sendall(part)
                self.assertEqual(client.recv(1), b'+')
                received = bytearray()
                expected = rsp.frame('T05thread:1;')
                while len(received) < len(expected):
                    received.extend(client.recv(len(expected) - len(received)))
                self.assertEqual(received, expected)
            worker.join(5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [])

    def test_real_gdb_tcp_breakpoint_step_registers_memory_and_return_42(self):
        process = subprocess.Popen([sys.executable, str(ROOT / 'tools/debug/unicorn_rsp.py'),
            '--elf', str(ELF), '--entry', 'main', '--port', '0'], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        try:
            ready_queue = queue.Queue()
            threading.Thread(target=lambda: ready_queue.put(process.stdout.readline()), daemon=True).start()
            ready = ready_queue.get(timeout=15).strip()
            self.assertTrue(ready.startswith('RSP_READY 127.0.0.1:'), ready)
            address = ready.split()[1]
            commands = f'''set pagination off
set confirm off
set auto-load off
set remotetimeout 5
file "{ELF.as_posix()}"
target remote {address}
echo CONNECTED\\n
info registers r0 r1 r7 sp lr pc xpsr
break embed_fn_diagnostic_probe
continue
if $r0 != 6 || $r1 != 7
  echo BAD_ARGUMENTS\\n
  quit 1
end
echo BREAKPOINT_ARGUMENTS_OK\\n
x/4i $pc
x/2wx $sp
set $before_pc = $pc
stepi
if $pc == $before_pc
  echo STEP_DID_NOT_ADVANCE\\n
  quit 1
end
echo INSTRUCTION_STEP_OK\\n
delete breakpoints
break *{rsp.RETURN_ADDRESS:#x}
continue
if $pc != {rsp.RETURN_ADDRESS:#x} || $r0 != 42 || $sp != {rsp.INITIAL_SP:#x}
  echo BAD_RESULT_OR_STACK\\n
  quit 1
end
printf "RESULT=%u SP=0x%x\\n", $r0, $sp
echo RETURN_AND_STACK_OK\\n
detach
quit
'''
            script = OUTPUT / 'checks.gdb'
            script.write_text(commands, encoding='utf-8')
            result = subprocess.run([GDB, '-nx', '-nh', '-batch', '-x', str(script)],
                capture_output=True, text=True, timeout=30)
            (OUTPUT / 'gdb-session.log').write_text(result.stdout + result.stderr, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for marker in ['CONNECTED', 'BREAKPOINT_ARGUMENTS_OK', 'INSTRUCTION_STEP_OK',
                           'RESULT=42', 'RETURN_AND_STACK_OK']:
                self.assertIn(marker, result.stdout)
            process.wait(timeout=5)
            self.assertEqual(process.returncode, 0, process.stderr.read())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
            process.stderr.close()


def main():
    global GDB
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assembler', default='arm-none-eabi-as')
    parser.add_argument('--linker', default='arm-none-eabi-ld')
    parser.add_argument('--gdb', default='arm-none-eabi-gdb')
    args = parser.parse_args()
    GDB = args.gdb
    build(args.assembler, args.linker)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ConnectionChecks))
    (OUTPUT / 'result.json').write_text(json.dumps({'tests': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
        'hardware': False, 'emb_source_debugging': False}, indent=2), encoding='utf-8')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
