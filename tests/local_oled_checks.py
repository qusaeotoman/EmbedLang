"""Execute the compiled F427 OLED application/driver with synthetic I2C only.

No board connection. Startup, clocks, GPIO AF setup, I2C initialization, font
rasterization and generated application code execute on a Cortex-M4 emulator.
The blocking I2C transfer boundary is intercepted; electrical behavior is not
emulated or claimed.
"""
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import (UC_CPU_ARM_CORTEX_M4, UC_ARM_REG_R0, UC_ARM_REG_R1,
    UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_SP)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'firmware'))
from local.verify import verify

IMAGE = ROOT / 'firmware/build/local_oled_f427'


class Machine:
    def __init__(self, fail_transfer=None, fail_init=False, failure_status=1):
        self.cpu = cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        cpu.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M4)
        for address, size in ((0x08000000, 0x200000), (0x20000000, 0x30000),
                (0x10000000, 0x10000), (0x40000000, 0x30000),
                (0x42000000, 0x1000000), (0xE0000000, 0x100000)):
            cpu.mem_map(address, size)
        cpu.mem_write(0x20000000, b'\xA5' * 0x30000)
        with (IMAGE / 'firmware.elf').open('rb') as stream:
            elf = ELFFile(stream)
            for segment in elf.iter_segments():
                if segment['p_type'] == 'PT_LOAD' and segment['p_filesz']:
                    cpu.mem_write(segment['p_paddr'], segment.data())
            self.symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
        self.put(0x40023800, 0x83)
        self.put(0x40023804, 0x24003010)
        self.transfers, self.characters, self.delays, self.resets = [], [], [], []
        self.generated = False
        self.min_sp, self.tick = 0x20030000, 0
        self.stop = 0x080FF000

        def instruction(uc, address, size, user):
            cr = self.word(0x40023800)
            self.put(0x40023800, cr | (2 if cr & 1 else 0) |
                     (0x20000 if cr & 0x10000 else 0) | (0x2000000 if cr & 0x1000000 else 0))
            cfgr = self.word(0x40023808)
            self.put(0x40023808, (cfgr & ~12) | ((cfgr & 3) << 2))
            self.min_sp = min(self.min_sp, uc.reg_read(UC_ARM_REG_SP))
            if address in (self.stop, self.symbols['local_blink_finished'] & ~1):
                uc.emu_stop()
                return
            if address == self.symbols['embed_program_main'] & ~1:
                self.generated = True
            if address == self.symbols['embed_oled_write_char'] & ~1:
                self.characters.append(uc.reg_read(UC_ARM_REG_R0))
            result = None
            if address == self.symbols['HAL_I2C_Mem_Write'] & ~1:
                assert uc.reg_read(UC_ARM_REG_SP) % 8 == 0
                sp = uc.reg_read(UC_ARM_REG_SP)
                data, count, timeout = (self.word(sp + n) for n in (0, 4, 8))
                self.transfers.append((uc.reg_read(UC_ARM_REG_R1), uc.reg_read(UC_ARM_REG_R2),
                    uc.reg_read(UC_ARM_REG_R3), bytes(uc.mem_read(data, count)), timeout))
                result = failure_status if len(self.transfers) == fail_transfer else 0
            elif fail_init and address == self.symbols['HAL_I2C_Init'] & ~1:
                result = 1
            elif address == self.symbols['HAL_Delay'] & ~1:
                self.delays.append(uc.reg_read(UC_ARM_REG_R0))
                result = 0
            elif address == self.symbols['HAL_GetTick'] & ~1:
                self.tick += 1
                result = self.tick
            if result is not None:
                uc.reg_write(UC_ARM_REG_R0, result)
                uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

        def memory(uc, access, address, size, value, user):
            if 0x42000000 <= address < 0x43000000:
                offset = address - 0x42000000
                target, bit = 0x40000000 + offset // 32, (offset % 32) // 4
                old = uc.mem_read(target, 1)[0]
                uc.mem_write(target, bytes([old | (1 << bit) if value else old & ~(1 << bit)]))
            if address == 0xE000ED0C and value & 4:
                self.resets.append(value)
        cpu.hook_add(UC_HOOK_CODE, instruction)
        cpu.hook_add(UC_HOOK_MEM_WRITE, memory)
        cpu.reg_write(UC_ARM_REG_SP, 0x20030000)
        cpu.emu_start(self.symbols['Reset_Handler'] | 1, 0, count=2000000)
        assert self.word(self.symbols['local_blink_status']) == 2

    def word(self, address):
        return struct.unpack('<I', self.cpu.mem_read(address, 4))[0]

    def put(self, address, value):
        self.cpu.mem_write(address, struct.pack('<I', value))

    def value(self, name):
        return self.word(self.symbols[name])

    def call(self, name, *args):
        for reg, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1), args):
            self.cpu.reg_write(reg, value)
        self.cpu.reg_write(UC_ARM_REG_SP, 0x20030000)
        self.cpu.reg_write(UC_ARM_REG_LR, self.stop | 1)
        self.cpu.emu_start(self.symbols[name] | 1, 0, count=2000000)
        assert self.cpu.reg_read(UC_ARM_REG_PC) == self.stop
        return self.cpu.reg_read(UC_ARM_REG_R0)


class OledTests(unittest.TestCase):
    def test_elf_bin_profile_and_compiler_provenance(self):
        report = verify(IMAGE / 'firmware.elf', IMAGE / 'firmware.bin', mcu='stm32f427vit6', oled=True)
        self.assertEqual(report['initial_sp'], '0x20030000')
        self.assertEqual(report['vector_address'], '0x8000000')
        meta = json.loads((IMAGE / 'verification.json').read_text())
        self.assertTrue(meta['oled'])
        self.assertIn('-DSTM32F427xx', meta['c_flags'])
        self.assertIn('-DHAL_I2C_MODULE_ENABLED', meta['c_flags'])
        self.assertEqual(meta['source_sha256'], hashlib.sha256((ROOT / 'examples/oled_group.emb').read_bytes()).hexdigest())

    def test_generated_text_and_exact_rendered_frame(self):
        m = Machine()
        self.assertTrue(m.generated)
        self.assertEqual(bytes(m.characters), b'THE BEST GROUP')
        self.assertEqual(m.value('embed_oled_status'), 2)
        self.assertEqual(m.value('embed_oled_hal_status'), 0)
        self.assertEqual(m.value('local_hal_error'), 0)
        self.assertEqual(m.value('SystemCoreClock'), 168000000)
        self.assertEqual(m.delays, [100])
        self.assertFalse(m.resets)
        self.assertLess(0x20030000 - m.min_sp, 1024)
        self.assertTrue(all(address == 0x78 and memory_size == 1 for address, memory, memory_size, data, timeout in m.transfers))
        pages = [data for address, memory, memory_size, data, timeout in m.transfers if memory == 0x40]
        self.assertEqual(len(pages), 16)  # Initial blank frame plus final text frame.
        self.assertEqual(b''.join(pages[:8]), bytes(1024))
        expected = bytearray(1024)
        font = m.symbols['Font7x10']
        for index, char in enumerate(b'THE BEST GROUP'):
            for y in range(10):
                row = struct.unpack('<H', m.cpu.mem_read(font + ((char - 32) * 10 + y) * 2, 2))[0]
                for x in range(7):
                    if row & (0x8000 >> x):
                        px, py = 15 + index * 7 + x, 27 + y
                        expected[px + (py // 8) * 128] |= 1 << (py % 8)
        self.assertEqual(b''.join(pages[8:]), bytes(expected))
        self.assertTrue(any(expected))
        print('OLED synthetic stack high-water:', 0x20030000 - m.min_sp)

    def test_original_initialization_sequence_and_bus_configuration(self):
        m = Machine()
        commands = bytes(data[0] for _, memory, _, data, _ in m.transfers if memory == 0)
        self.assertTrue(commands.startswith(bytes.fromhex('ae 20 10 b0 c8 00 10 40 81 ff a1 a6 a8 3f a4 d3 00 d5 f0 d9 22 da 12 db 20 8d 14 af')))
        self.assertEqual(m.word(0x40020400) & 0xF0000, 0xA0000)  # PB8/9 alternate.
        self.assertEqual(m.word(0x40020404) & 0x300, 0x300)  # Open drain.
        self.assertEqual(m.word(0x4002040C) & 0xF0000, 0x50000)  # Pullups.
        self.assertEqual(m.word(0x40020424) & 0xFF, 0x44)  # AF4 on both pins.
        self.assertTrue(m.word(0x40023840) & (1 << 21))  # I2C1 clock enabled.
        self.assertEqual(m.word(0x40005404) & 0x3F, 42)  # APB1 = 42 MHz.
        self.assertEqual(m.word(0x4000541C) & 0xCFFF, 0x8023)  # Fast mode, duty 2, CCR=35.

    def test_init_failure_skips_generated_text(self):
        m = Machine(fail_init=True)
        self.assertEqual(m.value('embed_oled_status'), 0x80000001)
        self.assertEqual(m.value('embed_oled_hal_status'), 1)
        self.assertEqual((m.characters, m.transfers), ([], []))

    def test_transfer_errors_are_sticky_and_stop_traffic(self):
        for status in (1, 2, 3):  # HAL_ERROR, HAL_BUSY, HAL_TIMEOUT.
            for failure in (1, 30, 61):  # First command, initial frame, final text frame.
                with self.subTest(status=status, failure=failure):
                    m = Machine(fail_transfer=failure, failure_status=status)
                    self.assertEqual(m.value('embed_oled_status'), 0x80000002)
                    self.assertEqual(m.value('embed_oled_hal_status'), status)
                    self.assertEqual(len(m.transfers), failure)
                    self.assertEqual(m.call('embed_oled_update'), 0)
                    self.assertEqual(len(m.transfers), failure)

    def test_ascii_cursor_bounds_and_full_line_are_safe(self):
        m = Machine()
        for char in (0, 31, 127, 256, 0xFFFFFFFF):
            self.assertEqual(m.call('embed_oled_write_char', char), 0)
        for x, y in ((121, 0), (0, 54), (256, 0), (0, 0xFFFFFFFF)):
            self.assertEqual(m.call('embed_oled_cursor', x, y), 0)
        self.assertEqual(m.call('embed_oled_cursor', 120, 53), 1)
        self.assertEqual(m.call('embed_oled_write_char', 65), 1)
        self.assertEqual(m.call('embed_oled_write_char', 66), 0)

    def test_successful_blink_images_remain_unchanged(self):
        for path, digest in {
            'firmware/build/local_blink_f427/firmware.bin': '90f5028e93c9cfad412a3e4ae87a7eac7737437928ba949b10e905f69c4d8deb',
            'firmware/build/diagnostic_blink_recovered/firmware.bin': 'cc1875ee45bd5eed052b75dfbd8c98bc5b8f55f23fb6690e6bb1d964fd4c3fb5',
        }.items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()
