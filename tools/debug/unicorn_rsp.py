"""Bounded localhost GDB RSP proof of concept, not an STM32 board simulator.

Executes pure compiler-generated Thumb code with Unicorn. One client, no MMIO,
no Flash operations, no target/file writes, no general-purpose RSP compliance.
"""
import argparse
from pathlib import Path
import socket
import struct
import select
import time

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UcError, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn import arm_const as arm

RETURN_ADDRESS = 0x90000
INITIAL_SP = 0x20010000
REGISTERS = [getattr(arm, f'UC_ARM_REG_R{i}') for i in range(13)] + [
    arm.UC_ARM_REG_SP, arm.UC_ARM_REG_LR, arm.UC_ARM_REG_PC, arm.UC_ARM_REG_XPSR]
XML = ('<?xml version="1.0"?><!DOCTYPE target SYSTEM "gdb-target.dtd">'
       '<target><architecture>armv7e-m</architecture>'
       '<feature name="org.gnu.gdb.arm.m-profile">' + ''.join(
           f'<reg name="{name}" bitsize="32" regnum="{i}" type="{kind}"/>'
           for i, (name, kind) in enumerate(
               [(f'r{i}', 'uint32') for i in range(13)] + [('sp', 'data_ptr'),
               ('lr', 'uint32'), ('pc', 'code_ptr'), ('xpsr', 'uint32')]))
       + '</feature></target>')


class Target:
    def __init__(self, elf_path, entry, arguments=()):
        with Path(elf_path).open('rb') as stream:
            image = ELFFile(stream)
            if image['e_machine'] != 'EM_ARM' or not image.little_endian or image.elfclass != 32:
                raise ValueError('A little-endian ARM32 ELF is required')
            section = image.get_section_by_name('.text')
            symbols = image.get_section_by_name('.symtab')
            if section is None or symbols is None:
                raise ValueError('ELF requires .text and .symtab')
            matches = symbols.get_symbol_by_name(entry)
            if not matches:
                raise ValueError(f'No entry symbol: {entry}')
            address, code = section['sh_addr'], section.data()
            start = matches[0]['st_value'] & ~1
        # Deliberately restricted host test layout, not a firmware image loader.
        if address != 0x10000 or len(code) > 0x10000 or not address <= start < address + len(code):
            raise ValueError('PoC requires pure .text linked at 0x10000, at most 64 KiB')
        if len(arguments) > 4:
            raise ValueError('PoC accepts at most four register arguments')
        self.cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        self.cpu.ctl_set_cpu_model(arm.UC_CPU_ARM_CORTEX_M4)
        self.cpu.mem_map(address, 0x10000)
        self.cpu.mem_write(address, code)
        self.cpu.mem_map(0x20000000, 0x20000)
        self.cpu.mem_map(RETURN_ADDRESS, 4096)
        self.cpu.mem_write(RETURN_ADDRESS, b'\x00\xbf')
        self.cpu.reg_write(arm.UC_ARM_REG_SP, INITIAL_SP)
        self.cpu.reg_write(arm.UC_ARM_REG_LR, RETURN_ADDRESS | 1)
        self.cpu.reg_write(arm.UC_ARM_REG_PC, start)
        self.cpu.reg_write(arm.UC_ARM_REG_XPSR, 1 << 24)
        for index, value in enumerate(arguments):
            self.cpu.reg_write(REGISTERS[index], value & 0xffffffff)
        self.breakpoints = set()
        self.ignore_breakpoint = None
        self.stop = 'T05thread:1;'
        self.cpu.hook_add(UC_HOOK_CODE, self._instruction)

    def _instruction(self, cpu, address, size, _):
        skip = self.ignore_breakpoint
        self.ignore_breakpoint = None
        if address == RETURN_ADDRESS or (address in self.breakpoints and address != skip):
            self.stopped = True
            cpu.emu_stop()

    def resume(self, step=False, interrupt=None):
        pc = self.cpu.reg_read(arm.UC_ARM_REG_PC)
        self.ignore_breakpoint = pc
        self.stopped = False
        try:
            deadline = time.monotonic() + 30
            while True:
                self.cpu.emu_start(pc | 1, 0xffffffff, timeout=1000000,
                                   count=1 if step else (1000 if interrupt else 100000))
                if step or self.stopped or interrupt is None:
                    break
                if interrupt() or time.monotonic() >= deadline:
                    break
                pc = self.cpu.reg_read(arm.UC_ARM_REG_PC)
            # Budget exhaustion is an interrupt, never a claimed breakpoint hit.
            self.stop = 'T05thread:1;' if step or self.stopped else 'T02thread:1;'
        except UcError:
            self.stop = 'T0bthread:1;'  # invalid/unmapped execution, virtual SIGSEGV
        return self.stop

    def handle(self, packet):
        if packet.startswith('qSupported'):
            return 'PacketSize=4000;qXfer:features:read+'
        if packet.startswith('qXfer:features:read:target.xml:'):
            offset, size = (int(x, 16) for x in packet.rsplit(':', 1)[1].split(','))
            return ('l' if offset + size >= len(XML) else 'm') + XML[offset:offset + size]
        if packet == '?':
            return self.stop
        if packet == 'g':
            return b''.join(struct.pack('<I', self.cpu.reg_read(r)) for r in REGISTERS).hex()
        if packet.startswith('p'):
            index = int(packet[1:], 16)
            return struct.pack('<I', self.cpu.reg_read(REGISTERS[index])).hex() if index < len(REGISTERS) else 'E01'
        if packet.startswith('m'):
            address, size = (int(x, 16) for x in packet[1:].split(','))
            if size > 4096:
                return 'E01'
            try:
                return bytes(self.cpu.mem_read(address, size)).hex()
            except UcError:
                return 'E01'
        if packet.startswith(('Z0,', 'z0,')):
            _, address, kind = packet.split(',')
            address = int(address, 16) & ~1
            if kind not in ('2', '4'):
                return 'E01'
            if packet[0] == 'Z':
                self.breakpoints.add(address)
            else:
                self.breakpoints.discard(address)
            return 'OK'
        if packet == 'vCont?':
            return 'vCont;c;s'
        if packet in ('c', 's') or packet.startswith(('vCont;c', 'vCont;s')):
            return self.resume(packet == 's' or packet.startswith('vCont;s'))
        if packet.startswith('H') or packet == 'T1' or packet == 'qSymbol::':
            return 'OK'
        # Extended-remote attach handshake for existing adapters; no run/restart.
        return {'!': 'OK', 'qAttached': '1', 'qC': 'QC1', 'qfThreadInfo': 'm1',
                'qsThreadInfo': 'l', 'D': 'OK', 'qOffsets': 'Text=0;Data=0;Bss=0'}.get(packet, '')


def frame(payload):
    data = payload.encode('ascii')
    return b'$' + data + b'#' + f'{sum(data) & 255:02x}'.encode('ascii')


def session(connection, target, interactive=False):
    """Acknowledged ASCII subset. Unknown operations return an empty reply."""
    connection.settimeout(300 if interactive else 30)
    connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    def interrupted():
        if select.select([connection], [], [], 0)[0]:
            value = connection.recv(1, socket.MSG_PEEK)
            if value == b'\x03':
                connection.recv(1)
                return True
            if not value:
                return True
        return False
    last_reply = b''
    while True:
        marker = connection.recv(1)
        if not marker:
            return
        if marker == b'-':
            connection.sendall(last_reply)
        elif marker == b'\x03':
            last_reply = frame('T02thread:1;')
            connection.sendall(last_reply)
        elif marker == b'$':
            payload = bytearray()
            while True:
                value = connection.recv(1)
                if not value:
                    return
                if value == b'#':
                    break
                payload.extend(value)
                if len(payload) > 0x4000:
                    return
            checksum = bytearray()
            while len(checksum) < 2:
                value = connection.recv(2 - len(checksum))
                if not value:
                    return
                checksum.extend(value)
            try:
                valid = int(checksum, 16) == (sum(payload) & 255)
            except ValueError:
                valid = False
            connection.sendall(b'+' if valid else b'-')
            if not valid:
                continue
            packet = ''
            try:
                packet = payload.decode('ascii')
                if packet == 'k':
                    return
                if interactive and (packet in ('c', 's') or packet.startswith(('vCont;c', 'vCont;s'))):
                    response = target.resume(packet == 's' or packet.startswith('vCont;s'), interrupted)
                else:
                    response = target.handle(packet)
            except (ValueError, IndexError, UnicodeDecodeError):
                response = 'E01'
            last_reply = frame(response)
            connection.sendall(last_reply)
            if packet == 'D':
                return


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', type=Path, required=True)
    parser.add_argument('--entry', default='embed_fn_diagnostic_probe')
    parser.add_argument('--arg', type=lambda value: int(value, 0), action='append', default=[])
    parser.add_argument('--port', type=int, default=3333)
    parser.add_argument('--interactive', action='store_true', help='Poll for GDB interrupt; each continue is bounded to 30 seconds')
    args = parser.parse_args()
    target = Target(args.elf, args.entry, args.arg)
    with socket.socket() as server:
        server.bind(('127.0.0.1', args.port))
        server.listen(1)
        server.settimeout(60)
        print(f'RSP_READY 127.0.0.1:{server.getsockname()[1]}', flush=True)
        connection, _ = server.accept()
        with connection:
            session(connection, target, args.interactive)


if __name__ == '__main__':
    main()
