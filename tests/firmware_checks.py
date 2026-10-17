"""Local firmware integration tests. Requires a built remote_blink ELF, no board.

python tests/firmware_checks.py [--image firmware/build/remote_blink]
HAL/trace calls are intercepted during Cortex-M4 emulation: these are ABI and
runtime logic tests, not peripheral or hardware-execution evidence.
"""
import argparse
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import (UC_CPU_ARM_CORTEX_M4, UC_ARM_REG_R0, UC_ARM_REG_R1,
                               UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R12,
                               UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_PRIMASK,
                               UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                               UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11)

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('verify', ROOT / 'firmware/tools/verify.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
IMAGE = ROOT / 'firmware/build/remote_blink'


class FirmwareTests(unittest.TestCase):
    def setUp(self):
        self.cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        self.cpu.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M4)
        for address, size in [(0x20000000, 0x20000), (0x10000000, 0x10000),
                              (0x40000000, 0x30000), (0xE0000000, 0x100000)]:
            self.cpu.mem_map(address, size)
        with (IMAGE / 'firmware.elf').open('rb') as stream:
            elf = ELFFile(stream)
            for section in elf.iter_sections():
                if section['sh_flags'] & 2 and section['sh_type'] != 'SHT_NOBITS':
                    self.cpu.mem_write(section['sh_addr'], section.data())
            self.symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
        self.events, self.writes, self.configs, self.delays = [], [], [], []
        self.states = {}
        self.ticks = 123
        self.min_sp = 0x20020000
        self.hooks = {
            'HAL_GPIO_Init': self.configure,
            'HAL_GPIO_WritePin': self.write,
            'HAL_GPIO_ReadPin': lambda a, b, c: self.states.get((a, b), 0),
            'HAL_GPIO_TogglePin': self.toggle,
            'HAL_Delay': self.delay,
            'HAL_GetTick': lambda a, b, c: self.ticks,
            'SDK_TRACE_Timestamp': self.trace,
        }
        self.cpu.hook_add(UC_HOOK_CODE, self.instruction)

    def instruction(self, cpu, address, size, user):
        self.min_sp = min(self.min_sp, cpu.reg_read(UC_ARM_REG_SP))
        for name, handler in self.hooks.items():
            if address == self.symbols[name] & ~1:
                self.assertEqual(cpu.reg_read(UC_ARM_REG_SP) % 8, 0, name + ' stack alignment')
                result = handler(*(cpu.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)))
                cpu.reg_write(UC_ARM_REG_R0, result or 0)
                # Model caller-saved register destruction, not accidentally preserved values.
                for register in (UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R12):
                    cpu.reg_write(register, 0xDEADBEEF)
                cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
                return

    def configure(self, port, pointer, unused):
        self.configs.append((port, *struct.unpack('<IIIII', self.cpu.mem_read(pointer, 20))))

    def write(self, port, pin, value):
        self.states[(port, pin)] = value
        self.writes.append((port, pin, value))

    def toggle(self, port, pin, unused):
        self.states[(port, pin)] = 1 - self.states.get((port, pin), 0)

    def delay(self, ms, unused1, unused2):
        self.delays.append(ms)
        self.ticks += ms

    def trace(self, event, value, unused):
        self.events.append((event, value))
        size = struct.unpack('<I', self.cpu.mem_read(0x10000004, 4))[0]
        self.cpu.mem_write(0x10000004, struct.pack('<I', size + 8))

    def call(self, name, *args):
        saved = (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                 UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11)
        for index, register in enumerate(saved):
            self.cpu.reg_write(register, 0x12340000 + index)
        for register, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2), args):
            self.cpu.reg_write(register, value)
        self.cpu.reg_write(UC_ARM_REG_SP, 0x20020000)
        self.cpu.reg_write(UC_ARM_REG_LR, 0x20000001)
        self.cpu.emu_start(self.symbols[name] | 1, 0x20000000, count=100000)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PC), 0x20000000, 'Function did not return')
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_SP), 0x20020000)
        for index, register in enumerate(saved):
            self.assertEqual(self.cpu.reg_read(register), 0x12340000 + index)
        return self.cpu.reg_read(UC_ARM_REG_R0)

    def test_elf_symbols_vectors_layout_and_binary(self):
        report = verifier.verify(IMAGE / 'firmware.elf', IMAGE / 'firmware.bin')
        self.assertLess(report['binary_bytes'], 76 * 1024)
        self.assertGreater(report['free_bytes_after_linker_reservations'], 0)

    def test_corrupted_binary_is_rejected(self):
        data = bytearray((IMAGE / 'firmware.bin').read_bytes())
        data[4] ^= 1
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'bad.bin'
            binary.write_bytes(data)
            with self.assertRaisesRegex(ValueError, 'BIN'):
                verifier.verify(IMAGE / 'firmware.elf', binary)

    def test_led_mapping_and_trace(self):
        for handle, mask in [(1, 1 << 13), (2, 1 << 14), (3, 1 << 15)]:
            self.call('embed_gpio_write', handle, 1)
            self.assertEqual(self.writes[-1], (0x40020C00, mask, 1))
            self.assertEqual(self.events[-1], (handle, 1))
            self.call('embed_gpio_toggle', handle)
            self.assertEqual(self.events[-1], (handle, 0))

    def test_gpio_modes_and_button_mapping(self):
        self.call('embed_gpio_mode', 1, 1)
        self.assertEqual(self.configs[-1][:5], (0x40020C00, 1 << 13, 1, 0, 2))
        self.call('embed_gpio_mode', 4, 0)
        self.assertEqual(self.configs[-1][:4], (0x40020800, 1 << 15, 0, 0))
        self.states[(0x40020800, 1 << 15)] = 1
        self.assertEqual(self.call('embed_gpio_read', 4), 1)

    def test_invalid_pins_modes_and_button_writes_do_nothing(self):
        for handle in (0, 4, 0xFFFFFFFF):
            self.call('embed_gpio_write', handle, 1)
            self.call('embed_gpio_toggle', handle)
            self.call('embed_gpio_mode', handle, 1)
        self.call('embed_gpio_mode', 1, 99)
        self.assertEqual(self.call('embed_gpio_read', 99), 0)
        self.assertEqual((self.writes, self.configs, self.events), ([], [], []))

    def test_trace_capacity_protects_print_region(self):
        capacity = (0x10005000 - 0x10000014) // 8 * 8
        self.cpu.mem_write(0x10000004, struct.pack('<I', capacity - 8))
        self.call('embed_gpio_toggle', 1)
        self.call('embed_gpio_toggle', 1)
        self.assertEqual(len(self.events), 1)

    def test_ticks_and_delays(self):
        self.assertEqual(self.call('embed_millis'), 123)
        self.call('embed_delay_ms', 250)
        self.assertEqual(self.delays, [250])
        self.assertEqual(self.call('embed_millis'), 373)

    def test_error_handler_preserves_official_return_behavior(self):
        self.call('Error_Handler')
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PRIMASK), 0)

    def test_official_system_init_relocates_vectors(self):
        self.call('SystemInit')
        self.assertEqual(struct.unpack('<I', self.cpu.mem_read(0xE000ED08, 4))[0], 0x2000D000)

    def test_official_systick_advances_millis(self):
        del self.hooks['HAL_GetTick']
        before = self.call('embed_millis')
        self.call('SysTick_Handler')
        self.assertEqual(self.call('embed_millis'), before + 1)

    def test_official_trace_preserves_task_id_and_finalizes_crc(self):
        del self.hooks['SDK_TRACE_Timestamp']
        self.hooks['HAL_RCC_GetHCLKFreq'] = lambda a, b, c: 168000000
        self.cpu.mem_write(0x10000004, struct.pack('<IIII', 100, 100, 100, 0x12345678))
        self.call('MX_TRACE_Init')
        self.assertEqual(struct.unpack('<IIII', self.cpu.mem_read(0x10000004, 16)), (0, 0, 0, 0x12345678))
        self.call('SDK_TRACE_Start')
        self.cpu.mem_write(0xE0001004, struct.pack('<I', 168000))
        self.call('SDK_TRACE_Timestamp', 1, 1)
        self.assertEqual(struct.unpack('<II', self.cpu.mem_read(0x10000014, 8)), (1000, 0x10101))
        # Official cLAB CRC complements after EACH byte, unlike standard CRC32.
        # Independent bitwise calculation instead of copying its lookup table.
        expected_crc = 0
        for byte in self.cpu.mem_read(0x10000004, 24):
            expected_crc ^= byte
            for _ in range(8):
                expected_crc = (expected_crc >> 1) ^ (0xEDB88320 if expected_crc & 1 else 0)
            expected_crc ^= 0xFFFFFFFF
        self.call('SDK_TRACE_Stop')
        self.assertEqual(struct.unpack('<I', self.cpu.mem_read(0x10000000, 4))[0], expected_crc)
        self.assertEqual(struct.unpack('<I', self.cpu.mem_read(0xE000ED0C, 4))[0], 0x05FA0004)

    def test_finite_blink_returns_and_traces_expected_sequence(self):
        self.call('embed_program_main')
        self.assertEqual(self.events, [(1, 0)] + [(1, 1 - i % 2) for i in range(10)] + [(1, 0)])
        self.assertEqual(self.delays, [250] * 10)
        self.assertLess(0x20020000 - self.min_sp, 1024)
        print(f'Finite Blink emulated stack high-water with HAL/trace stubs: {0x20020000 - self.min_sp} bytes')

    def test_board_wrapper_initialization_order(self):
        order = []
        for name in ('HAL_Init', 'SystemClock_Config', 'MX_GPIO_Init', 'MX_IWDG_Init',
                     'MX_TRACE_Init', 'SDK_TRACE_Start', 'embed_program_main'):
            self.hooks[name] = lambda a, b, c, n=name: order.append(n)
        def stop(a, b, c):
            order.append('SDK_TRACE_Stop')
            self.cpu.emu_stop()
        self.hooks['SDK_TRACE_Stop'] = stop
        self.cpu.reg_write(UC_ARM_REG_SP, 0x20020000)
        self.cpu.emu_start(self.symbols['main'] | 1, 0, count=100000)
        self.assertEqual(order, ['HAL_Init', 'SystemClock_Config', 'MX_GPIO_Init', 'MX_IWDG_Init',
                                 'MX_TRACE_Init', 'SDK_TRACE_Start', 'embed_program_main', 'SDK_TRACE_Stop'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', type=Path, default=IMAGE)
    args, rest = parser.parse_known_args()
    IMAGE = args.image.resolve()
    unittest.main(argv=[__file__, *rest])
