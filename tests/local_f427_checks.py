"""STM32F427VIT6 Flash integration; synthetic execution, no physical writes."""
import hashlib
import json
import struct
import unittest

from elftools.elf.elffile import ELFFile
from local_firmware_checks import ROOT, execute, verify

IMAGE = ROOT / 'firmware/build/local_blink_f427'


class F427Tests(unittest.TestCase):
    def run_image(self, **kwargs):
        return execute(image=IMAGE, ram_end=0x20030000, **kwargs)

    def test_f427_flash_sram_vectors_and_profile(self):
        r = verify(IMAGE / 'firmware.elf', IMAGE / 'firmware.bin', mcu='stm32f427vit6')
        self.assertEqual((r['flash_end'], r['ram_end'], r['initial_sp'], r['vector_bytes']),
                         ('0x8200000', '0x20030000', '0x20030000', 428))
        m = json.loads((IMAGE / 'verification.json').read_text())
        self.assertEqual(m['mcu'], 'stm32f427vit6')
        self.assertIn('-DSTM32F427xx', m['c_flags'])
        self.assertNotIn('-DSTM32F407xx', m['c_flags'])
        self.assertFalse(m['pll_recovery'])
        with (IMAGE / 'firmware.elf').open('rb') as f:
            elf = ELFFile(f)
            symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
            vectors = elf.get_section_by_name('.isr_vector').data()
            for irq, name in ((48, 'FMC_IRQHandler'), (82, 'UART7_IRQHandler'), (90, 'DMA2D_IRQHandler')):
                self.assertEqual(struct.unpack_from('<I', vectors, (16 + irq) * 4)[0], symbols[name])

    def test_real_f427_hal_cold_start_generated_blink(self):
        r = self.run_image()
        self.assertEqual((r['status'], r['error'], r['generated']), (2, 0, [True]))
        self.assertEqual((r['vtor'], r['hclk'], r['pll'], r['systick']), (0x08000000, 168000000, 0x04405419, 167999))
        self.assertEqual(r['pwr_cr'] & 0xC000, 0xC000)  # F427's two-bit VOS scale 1.
        self.assertEqual(r['flash_acr'] & 15, 5)
        self.assertEqual(r['cfgr'] & 0xFCF0, 0x9400)  # AHB /1, APB1 /4, APB2 /2.
        self.assertEqual(r['systick_ctrl'] & 7, 7)
        self.assertEqual(r['cpacr'] & 0x00F00000, 0x00F00000)
        self.assertEqual(r['delays'], [250] * 10)
        self.assertEqual([call for call in r['gpio'] if call[0] == 'toggle'],
                         [('toggle', 0x40020C00, 1 << 13, 1 - i % 2) for i in range(10)])
        self.assertEqual(r['gpio'][-1], ('write', 0x40020C00, 1 << 13, 0))
        self.assertFalse([x for x in r['writes'] if x[0] == 0x40003000])
        self.assertTrue(all(not (v & 4) for a, v in r['writes'] if a == 0xE000ED0C))
        self.assertLess(r['stack'], 1024)
        print('F427 cold-start synthetic stack high-water:', r['stack'])

    def test_fatal_initialization_errors_and_no_warm_pll_recovery(self):
        for options in ({'hse_ready': False}, {'warm_pll': True},
                        {'overrides': {'HAL_RCC_ClockConfig': 1}}, {'overrides': {'HAL_SYSTICK_Config': 1}}):
            with self.subTest(options=options):
                r = self.run_image(**options)
                self.assertTrue(r['status'] & 0x80000000)
                self.assertEqual(r['generated'], [])

    def test_f407_and_f427_images_are_not_interchangeable(self):
        old = ROOT / 'firmware/build/local_blink'
        with self.assertRaises(ValueError):
            verify(old / 'firmware.elf', old / 'firmware.bin', mcu='stm32f427vit6')
        with self.assertRaises(ValueError):
            verify(IMAGE / 'firmware.elf', IMAGE / 'firmware.bin')

    def test_generated_assembly_is_unchanged_and_old_firmware_preserved(self):
        self.assertEqual((IMAGE / 'program.s').read_text(),
                         (ROOT / 'firmware/build/local_blink/program.s').read_text())
        for path, digest in {
            'firmware/build/local_blink/firmware.bin': 'b5bafeac1e63a477f6a52477672e93c257eff236c564ce52df2d8696a8492853',
            'firmware/build/diagnostic_blink_recovered/firmware.bin': 'cc1875ee45bd5eed052b75dfbd8c98bc5b8f55f23fb6690e6bb1d964fd4c3fb5',
            'firmware/build/diagnostic_probe_recovered/firmware.bin': 'fb5ec379f307a3e29477563233df78548e5de0bb16153883611e8b98142f3ea6',
        }.items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()
