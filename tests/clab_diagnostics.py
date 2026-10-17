"""Execute diagnostic ELFs through real startup/libc/trace, with hardware hooks.

Build the probe, Blink, size-comparison Blink and ordinary remote_blink first.
These are local ARM integration tests, not evidence of physical board behavior.
"""
import importlib.util
import json
from pathlib import Path
import struct
import unittest

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import (UC_CPU_ARM_CORTEX_M4, UC_ARM_REG_R0, UC_ARM_REG_R1,
                               UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R12,
                               UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_PRIMASK)

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / 'firmware/build'
spec = importlib.util.spec_from_file_location('verify', ROOT / 'firmware/tools/verify.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def execute(image, init_error=False, wrong_probe=False, full_buffers=False,
            init_scenario=None, elf_path=None, register_overrides=None,
            final_overrides=None, hal_overrides=None, request_overrides=None):
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M4)
    for addr, size in [(0x20000000, 0x20000), (0x10000000, 0x10000),
                       (0x40000000, 0x30000), (0x42000000, 0x1000000),
                       (0xE0000000, 0x100000)]:
        cpu.mem_map(addr, size)
    with (elf_path or BUILD / image / 'firmware.elf').open('rb') as stream:
        elf = ELFFile(stream)
        for section in elf.iter_sections():
            if section['sh_flags'] & 2 and section['sh_type'] != 'SHT_NOBITS':
                cpu.mem_write(section['sh_addr'], section.data())
        symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
    states, order, delays, generated = {}, [], [], []
    gpio_calls = []
    watchdog_writes = []
    handler_calls = []
    reset, min_sp = [], [0x20020000]
    trace_started = [False]
    cpu.mem_write(0x10000010, struct.pack('<I', 0x13572468))  # synthetic loader task_id

    def delay(ms, b, c):
        delays.append(ms)
        old = struct.unpack('<I', cpu.mem_read(0xE0001004, 4))[0]
        cpu.mem_write(0xE0001004, struct.pack('<I', (old + ms * 168000) & 0xFFFFFFFF))

    def write(port, pin, value):
        gpio_calls.append(('write', port, pin, value))
        states[(port, pin)] = value

    def toggle(port, pin, unused):
        gpio_calls.append(('toggle', port, pin, None))
        states[(port, pin)] = 1 - states.get((port, pin), 0)

    def gpio_init(port, config, unused):
        pin, mode = struct.unpack('<II', cpu.mem_read(config, 8))
        gpio_calls.append(('init', port, pin, mode))

    hooks = {'HAL_GPIO_Init': gpio_init, 'HAL_GPIO_WritePin': write,
             'HAL_GPIO_TogglePin': toggle,
             'HAL_GPIO_ReadPin': lambda a, b, c: states.get((a, b), 0),
             'HAL_Delay': delay, 'HAL_RCC_GetHCLKFreq': lambda a, b, c: 168000000}
    if init_scenario is None:
        for name in ('HAL_Init', 'SystemClock_Config', 'MX_GPIO_Init', 'MX_IWDG_Init'):
            hooks[name] = lambda a, b, c, n=name: order.append(n)
    else:
        # Synthetic warm-loader register state, NOT measurements from cLAB.
        # Decode: HSE, M=25, N=336, P=2, Q=4; PLL SYSCLK, APB1 /4, APB2 /2.
        cpu.mem_write(0x40023800, struct.pack('<III', 0x03030003, 0x04405419, 0x0000940A))
        cpu.mem_write(0x40023874, struct.pack('<I', 3))  # LSI on/ready
        if init_scenario == 'different_pll':
            cpu.mem_write(0x40023804, struct.pack('<I', 0x04405418))  # M=24, real mismatch
        if init_scenario == 'lsi_timeout':
            cpu.mem_write(0x40023874, struct.pack('<I', 0))
        if init_scenario == 'iwdg_timeout':
            cpu.mem_write(0x4000300C, struct.pack('<I', 1))
        tick = [0]
        def get_tick(a, b, c):
            tick[0] += 100
            return tick[0]
        hooks['HAL_GetTick'] = get_tick
        del hooks['HAL_RCC_GetHCLKFreq']
    for address, value in (register_overrides or {}).items():
        cpu.mem_write(address, struct.pack('<I', value))
    for name, status in (hal_overrides or {}).items():
        hooks[name] = lambda a, b, c, s=status: s
    if wrong_probe:
        hooks['embed_fn_diagnostic_probe'] = lambda a, b, c: 41

    def instruction(uc, address, size, user):
        min_sp[0] = min(min_sp[0], uc.reg_read(UC_ARM_REG_SP))
        for name in ('MX_TRACE_Init', 'SDK_TRACE_Start', 'SDK_TRACE_Stop'):
            if address == symbols[name] & ~1:
                order.append(name)
                if name == 'SDK_TRACE_Start':
                    assert 'MX_TRACE_Init' in order
                    trace_started[0] = True
        for name in ('SDK_TRACE_Print', 'SDK_TRACE_Timestamp'):
            if name in symbols and address == symbols[name] & ~1:
                assert trace_started[0], 'Trace emission before trace initialization/start'
        if init_scenario is not None:
            for name in ('HAL_Init', 'SystemClock_Config', 'MX_GPIO_Init', 'MX_IWDG_Init'):
                if address == symbols[name] & ~1:
                    order.append(name)
        if address == symbols['Error_Handler'] & ~1:
            handler_calls.append(True)
        if request_overrides and address == symbols.get('embed_init_osc', 0) & ~1:
            pointer = uc.reg_read(UC_ARM_REG_R0)
            for offset, value in request_overrides.items():
                uc.mem_write(pointer + offset, struct.pack('<I', value))
        if final_overrides and address == symbols.get('embed_diagnostic_run', 0) & ~1:
            for key, value in final_overrides.items():
                if key == 'PRIMASK':
                    uc.reg_write(UC_ARM_REG_PRIMASK, value)
                else:
                    destination = symbols[key] if isinstance(key, str) else key
                    uc.mem_write(destination, struct.pack('<I', value))
        for name in ('embed_program_main', 'embed_fn_diagnostic_probe'):
            if name in symbols and address == symbols[name] & ~1:
                generated.append(name)
                assert uc.reg_read(UC_ARM_REG_SP) % 8 == 0, name
        if full_buffers and address == symbols.get('embed_diagnostic_run', 0) & ~1:
            uc.mem_write(0x10000004, struct.pack('<III', 20456, 20480, 0))
        for name, handler in hooks.items():
            if address != symbols[name] & ~1:
                continue
            if init_error and name == 'SystemClock_Config':
                order.append(name)
                # Execute the real returning error handler/counter with the caller's LR.
                uc.reg_write(UC_ARM_REG_PC, symbols['Error_Handler'])
                return
            assert uc.reg_read(UC_ARM_REG_SP) % 8 == 0, name
            value = handler(*(uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)))
            uc.reg_write(UC_ARM_REG_R0, value or 0)
            for register in (UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R12):
                uc.reg_write(register, 0xDEADBEEF)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
            return

    def memory_write(uc, access, address, size, value, user):
        if address == 0x40003000:
            watchdog_writes.append(value)
        if address == 0xE000ED0C and value == 0x05FA0004:
            reset.append(True)
            uc.emu_stop()

    cpu.hook_add(UC_HOOK_CODE, instruction)
    cpu.hook_add(UC_HOOK_MEM_WRITE, memory_write)
    cpu.reg_write(UC_ARM_REG_SP, 0x20020000)
    cpu.emu_start(symbols['Reset_Handler'] | 1, 0, count=4000000)
    assert reset, 'Did not reach official trace finalization/reset request'
    trace_size, print_size, dump_size, task_id = struct.unpack('<IIII', cpu.mem_read(0x10000004, 16))
    assert task_id == 0x13572468
    assert 0 <= trace_size <= 0x10005000 - 0x10000014
    assert 0 <= print_size <= 0x5000
    crc = 0
    for byte in cpu.mem_read(0x10000004, 16 + trace_size):
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xEDB88320 if crc & 1 else 0)
        crc ^= 0xFFFFFFFF
    assert struct.unpack('<I', cpu.mem_read(0x10000000, 4))[0] == crc
    assert struct.unpack('<I', cpu.mem_read(0xE000ED08, 4))[0] == 0x2000D000
    messages = []
    if not full_buffers:
        offset = 0
        while offset < print_size:
            length = cpu.mem_read(0x10005000 + offset + 4, 1)[0]
            messages.append(bytes(cpu.mem_read(0x10005000 + offset + 5, length)).decode('ascii'))
            offset += 5 + length
        assert offset == print_size
    events = [struct.unpack('<II', cpu.mem_read(0x10000014 + i, 8)) for i in range(0, trace_size, 8)]
    return {'messages': messages, 'events': events, 'delays': delays, 'order': order,
            'generated': generated, 'handler_calls': len(handler_calls),
            'dump_bytes': dump_size, 'gpio_calls': gpio_calls,
            'trace_bytes': trace_size, 'print_bytes': print_size,
            'watchdog_writes': watchdog_writes,
            'stack_bytes_with_hardware_stubs': 0x20020000 - min_sp[0]}


class DiagnosticTests(unittest.TestCase):
    def test_all_elfs_and_profiles(self):
        for image in ('diagnostic_probe', 'diagnostic_blink', 'diagnostic_blink_size', 'remote_blink'):
            with self.subTest(image=image):
                report = verifier.verify(BUILD / image / 'firmware.elf', BUILD / image / 'firmware.bin')
                self.assertLess(report['binary_bytes'], 76 * 1024)
                metadata = json.loads((BUILD / image / 'verification.json').read_text())
                self.assertIn('-Os' if image.endswith('_size') else '-O0', metadata['c_flags'])

    def check_lifecycle(self, result):
        self.assertEqual(result['order'], ['HAL_Init', 'SystemClock_Config', 'MX_GPIO_Init',
                         'MX_IWDG_Init', 'MX_TRACE_Init', 'SDK_TRACE_Start', 'SDK_TRACE_Stop'])
        self.assertLess(result['stack_bytes_with_hardware_stubs'], 1024)

    def test_probe_arguments_return_markers_crc_and_reset(self):
        result = execute('diagnostic_probe')
        self.check_lifecycle(result)
        self.assertEqual(result['generated'], ['embed_fn_diagnostic_probe'])
        self.assertEqual(result['messages'], ['INIT_ERRORS=0', 'BEFORE_GENERATED', 'PROBE_RESULT=42',
                                             'AFTER_GENERATED', 'TRACE_COMPLETE'])
        self.assertEqual(result['delays'], [250])

    def test_blink_and_size_comparison_have_same_behavior(self):
        results = []
        for image in ('diagnostic_blink', 'diagnostic_blink_size'):
            result = execute(image)
            self.check_lifecycle(result)
            self.assertEqual(result['generated'], ['embed_program_main'])
            self.assertEqual(result['messages'], ['INIT_ERRORS=0', 'BEFORE_GENERATED',
                                                 'AFTER_GENERATED', 'TRACE_COMPLETE'])
            self.assertEqual(result['delays'], [250] * 11)
            led = [(event & 255, event >> 8 & 255) for _, event in result['events'] if event & 255 == 1]
            self.assertEqual(led, [(1, 0)] + [(1, 1 - i % 2) for i in range(10)] + [(1, 0)])
            results.append(result)
        self.assertEqual(results[0]['events'], results[1]['events'])

    def test_init_error_is_reported_and_generated_code_is_skipped(self):
        for image in ('diagnostic_probe', 'diagnostic_blink'):
            result = execute(image, init_error=True)
            self.check_lifecycle(result)
            self.assertEqual(result['generated'], [])
            self.assertEqual(result['messages'], ['INIT_ERRORS=1', 'SKIP_INIT_ERROR'])
            self.assertEqual(result['delays'], [])

    def test_wrong_return_value_is_reported(self):
        result = execute('diagnostic_probe', wrong_probe=True)
        self.assertIn('PROBE_RESULT=41', result['messages'])
        self.assertIn('PROBE_MISMATCH', result['messages'])
        self.assertEqual(result['messages'][-1], 'TRACE_COMPLETE')

    def test_full_buffers_do_not_overflow_markers(self):
        result = execute('diagnostic_probe', full_buffers=True)
        self.assertEqual(result['generated'], ['embed_fn_diagnostic_probe'])
        self.assertEqual(result['messages'], [])
        self.assertEqual(result['events'], [(0, 0)] * (20456 // 8))


if __name__ == '__main__':
    unittest.main()
