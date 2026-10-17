"""Local Flash image tests with synthetic clocks/GPIO, never physical hardware."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_CPU_ARM_CORTEX_M4, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_SP

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'firmware'))
from local.verify import verify

IMAGE = ROOT / 'firmware/build/local_blink'


def execute(overrides=None, hse_ready=True, warm_pll=False, image=IMAGE, ram_end=0x20020000):
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M4)
    for a, size in [(0x08000000, 0x200000), (0x20000000, ram_end - 0x20000000), (0x10000000, 0x10000),
                    (0x40000000, 0x30000), (0x42000000, 0x1000000), (0xE0000000, 0x100000)]:
        cpu.mem_map(a, size)
    cpu.mem_write(0x20000000, b'\xA5' * (ram_end - 0x20000000))
    with (image / 'firmware.elf').open('rb') as stream:
        elf = ELFFile(stream)
        for seg in elf.iter_segments():
            if seg['p_type'] == 'PT_LOAD' and seg['p_filesz']:
                cpu.mem_write(seg['p_paddr'], seg.data())
        symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
    word = lambda a: struct.unpack('<I', cpu.mem_read(a, 4))[0]
    put = lambda a, v: cpu.mem_write(a, struct.pack('<I', v))
    put(0x40023800, 0x83)  # Synthetic reset: HSI on/ready; HSE/PLL off.
    put(0x40023804, 0x24003010)
    if warm_pll:
        put(0x40023800, 0x03030083)
        put(0x40023804, 0x04405419)
        put(0x40023808, 0x940A)
    states, gpio, delays, generated, writes, done = {}, [], [], [], [], []
    min_sp, tick = [ram_end], [0]

    def gpio_init(port, config, unused):
        gpio.append(('init', port, *struct.unpack('<II', cpu.mem_read(config, 8))))

    def write(port, pin, value):
        states[(port, pin)] = value
        gpio.append(('write', port, pin, value))

    def toggle(port, pin, unused):
        states[(port, pin)] = 1 - states.get((port, pin), 0)
        gpio.append(('toggle', port, pin, states[(port, pin)]))

    def delay(ms, b, c):
        delays.append(ms)
        put(0xE0001004, word(0xE0001004) + ms * 168000)

    def ticks(a, b, c):
        tick[0] += 100
        return tick[0]

    hooks = {'HAL_GPIO_Init': gpio_init, 'HAL_GPIO_WritePin': write, 'HAL_GPIO_TogglePin': toggle,
             'HAL_GPIO_ReadPin': lambda a, b, c: states.get((a, b), 0), 'HAL_Delay': delay, 'HAL_GetTick': ticks}
    for name, status in (overrides or {}).items():
        hooks[name] = lambda a, b, c, value=status: value

    def instruction(uc, address, size, user):
        # Model hardware ready bits and source-switch acknowledgement, not HAL
        # success: the actual original HAL initialization executes in this CPU.
        cr = word(0x40023800)
        cr = (cr | 2) if cr & 1 else (cr & ~2)
        cr = (cr | 0x20000) if cr & 0x10000 and hse_ready else (cr & ~0x20000)
        cr = (cr | 0x2000000) if cr & 0x1000000 else (cr & ~0x2000000)
        put(0x40023800, cr)
        cfgr = word(0x40023808)
        put(0x40023808, (cfgr & ~12) | ((cfgr & 3) << 2))
        min_sp[0] = min(min_sp[0], uc.reg_read(UC_ARM_REG_SP))
        if address == symbols['embed_program_main'] & ~1:
            generated.append(True)
            assert uc.reg_read(UC_ARM_REG_SP) % 8 == 0
        if address == symbols['local_blink_finished'] & ~1 or bytes(uc.mem_read(address, 2)) == b'\x30\xbf':
            done.append(True)
            uc.emu_stop()
            return
        for name, handler in hooks.items():
            if address == symbols[name] & ~1:
                assert uc.reg_read(UC_ARM_REG_SP) % 8 == 0
                value = handler(*(uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)))
                uc.reg_write(UC_ARM_REG_R0, value or 0)
                uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
                return

    def memory_write(uc, access, address, size, value, user):
        if 0x42000000 <= address < 0x43000000:
            offset = address - 0x42000000
            destination, bit = 0x40000000 + offset // 32, (offset % 32) // 4
            old = uc.mem_read(destination, 1)[0]
            uc.mem_write(destination, bytes([(old | (1 << bit)) if value else (old & ~(1 << bit))]))
        if address in (0x40003000, 0xE000ED0C):
            writes.append((address, value))

    cpu.hook_add(UC_HOOK_CODE, instruction)
    cpu.hook_add(UC_HOOK_MEM_WRITE, memory_write)
    cpu.reg_write(UC_ARM_REG_SP, ram_end)
    cpu.emu_start(symbols['Reset_Handler'] | 1, 0, count=1000000)
    assert done, 'Did not reach completion/fatal idle'
    count = word(0x10000004)
    events = [struct.unpack('<II', cpu.mem_read(0x10000014 + i, 8)) for i in range(0, count, 8)]
    return dict(status=word(symbols['local_blink_status']), error=word(symbols['local_hal_error']),
                generated=generated, gpio=gpio, delays=delays, writes=writes, events=events,
                vtor=word(0xE000ED08), hclk=word(symbols['SystemCoreClock']),
                pll=word(0x40023804), systick=word(0xE000E014), stack=ram_end - min_sp[0],
                pwr_cr=word(0x40007000), flash_acr=word(0x40023C00), cfgr=word(0x40023808),
                systick_ctrl=word(0xE000E010), cpacr=word(0xE000ED88))


class LocalFirmwareTests(unittest.TestCase):
    def test_elf_flash_lma_ram_vma_and_vectors(self):
        report = verify(IMAGE / 'firmware.elf', IMAGE / 'firmware.bin')
        self.assertEqual(report['vector_address'], '0x8000000')
        self.assertEqual(report['initial_sp'], '0x20020000')
        self.assertEqual(report['unresolved_symbols'], [])
        meta = json.loads((IMAGE / 'verification.json').read_text())
        self.assertFalse(meta['pll_recovery'])

    def test_actual_cold_start_hal_generated_blink_and_final_low(self):
        r = execute()
        self.assertEqual((r['status'], r['error'], r['generated']), (2, 0, [True]))
        self.assertEqual((r['vtor'], r['hclk'], r['pll'], r['systick']), (0x08000000, 168000000, 0x04405419, 167999))
        self.assertEqual(r['delays'], [250] * 10)
        self.assertIn(('init', 0x40020C00, 1 << 13, 1), r['gpio'])
        self.assertEqual([entry for entry in r['gpio'] if entry[0] == 'toggle'],
                         [('toggle', 0x40020C00, 1 << 13, 1 - i % 2) for i in range(10)])
        self.assertEqual(r['gpio'][-1], ('write', 0x40020C00, 1 << 13, 0))
        self.assertEqual([event >> 8 & 255 for time, event in r['events']], [0] + [1 - i % 2 for i in range(10)] + [0])
        self.assertFalse([entry for entry in r['writes'] if entry[0] == 0x40003000])
        # HAL_Init writes AIRCR to select priority grouping, without SYSRESETREQ.
        self.assertTrue(all(not (value & 4) for address, value in r['writes'] if address == 0xE000ED0C))
        self.assertLess(r['stack'], 1024)
        print('Local cold-start synthetic stack high-water:', r['stack'])

    def test_hal_failures_remain_fatal_without_recovery(self):
        for i, name in enumerate(('HAL_Init', 'HAL_RCC_OscConfig', 'HAL_RCC_ClockConfig'), 1):
            with self.subTest(stage=name):
                r = execute({name: 1})
                self.assertEqual((r['status'], r['error']), (0x80000000 | i, 1))
                self.assertEqual(r['generated'], [])

    def test_real_hse_ready_timeout_denies_application(self):
        r = execute(hse_ready=False)
        self.assertEqual((r['status'], r['error']), (0x80000002, 3))
        self.assertEqual(r['generated'], [])

    def test_nested_tick_setup_failure_denies_application(self):
        r = execute({'HAL_SYSTICK_Config': 1})
        self.assertEqual(r['status'], 0x80000003)
        self.assertEqual(r['generated'], [])

    def test_warm_pll_false_error_is_not_recovered_locally(self):
        r = execute(warm_pll=True)
        self.assertEqual((r['status'], r['error']), (0x80000002, 1))
        self.assertEqual(r['generated'], [])

    def test_clab_ram_firmware_is_rejected(self):
        image = ROOT / 'firmware/build/diagnostic_blink_recovered'
        with self.assertRaises(ValueError):
            verify(image / 'firmware.elf', image / 'firmware.bin')

    def test_modified_bin_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'firmware/build') as tmp:
            binary = Path(tmp) / 'bad.bin'
            data = bytearray((IMAGE / 'firmware.bin').read_bytes())
            data[4] ^= 1
            binary.write_bytes(data)
            with self.assertRaises(ValueError):
                verify(IMAGE / 'firmware.elf', binary)


if __name__ == '__main__':
    unittest.main()
