"""Recovered finite Blink: actual generated ARM/HAL/trace with synthetic MMIO.

Requires diagnostic_blink_recovered; never uploads or connects to cLAB.
"""
import hashlib
import json
import subprocess
import sys
import unittest

from clab_diagnostics import ROOT, BUILD, execute, verifier
from clab_init_checks import stages

IMAGE = 'diagnostic_blink_recovered'


class RecoveredBlinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = execute(IMAGE, init_scenario='warm_pll')

    def assert_denied(self, result):
        self.assertEqual(result['generated'], [])
        self.assertIn('SKIP_INIT_ERROR', result['messages'])
        self.assertNotIn('PLL_MATCH_RECOVERED', result['messages'])
        self.assertNotIn('BEFORE_GENERATED', result['messages'])
        self.assertEqual(result['delays'], [])

    def test_generated_main_gpio_mapping_delays_and_completion(self):
        result = self.result
        self.assertEqual(result['generated'], ['embed_program_main'])
        self.assertEqual(result['messages'][-4:], ['PLL_MATCH_RECOVERED',
                         'BEFORE_GENERATED', 'AFTER_GENERATED', 'TRACE_COMPLETE'])
        self.assertEqual(result['handler_calls'], 0)
        self.assertIn('INIT_ERRORS=0', result['messages'])
        osc = stages(result)['HAL_RCC_OscConfig']
        self.assertEqual((osc['HAL_STATUS'], osc['EFFECTIVE_STATUS'], osc['RETURN']),
                         ('1', '0', 'stm32f4xx_hal_rcc.c:549'))
        self.assertEqual(stages(result)['HAL_IWDG_Init']['HAL_STATUS'], '0')
        self.assertEqual(stages(result)['HAL_RCC_ClockConfig']['HAL_STATUS'], '0')
        self.assertEqual(result['delays'], [250] * 11)
        # Real official HAL starts, unlocks, and reloads the IWDG once.
        # There is no watchdog disable or repeated application refresh shim.
        self.assertEqual(result['watchdog_writes'], [0xCCCC, 0x5555, 0xAAAA])
        self.assertEqual(result['order'], ['HAL_Init', 'SystemClock_Config',
                         'MX_GPIO_Init', 'MX_IWDG_Init', 'MX_TRACE_Init',
                         'SDK_TRACE_Start', 'SDK_TRACE_Stop'])
        # Actual generated program calls the runtime; HAL hooks observe PD13.
        self.assertIn(('init', 0x40020C00, 1 << 13, 1), result['gpio_calls'])
        self.assertEqual([call for call in result['gpio_calls'] if call[0] == 'toggle'],
                         [('toggle', 0x40020C00, 1 << 13, None)] * 10)
        self.assertLess(result['stack_bytes_with_hardware_stubs'], 1024)
        print('Recovered Blink (synthetic hardware): stack=%d, trace=%d, print=%d bytes'
              % (result['stack_bytes_with_hardware_stubs'], result['trace_bytes'], result['print_bytes']))

    def test_official_trace_units_and_every_led_transition(self):
        events = [(time, event >> 8 & 255) for time, event in self.result['events'] if event & 255 == 1]
        self.assertEqual(events, [(0, 0)] + [(i * 250000, 1 - i % 2) for i in range(10)]
                         + [(2500000, 0)])
        # Synthetic delays advance DWT_CYCCNT; the real trace code divides by
        # 168 at 168 MHz. This validates raw microseconds, not physical timing.
        self.assertEqual(self.result['events'][-1][0], 2750000)

    def test_clean_hal_success_does_not_claim_recovery(self):
        result = execute(IMAGE, init_scenario='warm_pll', hal_overrides={'HAL_RCC_OscConfig': 0})
        self.assertEqual(result['generated'], ['embed_program_main'])
        self.assertNotIn('PLL_MATCH_RECOVERED', result['messages'])
        self.assertEqual(result['messages'][-1], 'TRACE_COMPLETE')

    def test_genuine_initialization_and_live_state_failures_skip_blink(self):
        for scenario in ('different_pll', 'lsi_timeout', 'iwdg_timeout'):
            with self.subTest(scenario=scenario):
                self.assert_denied(execute(IMAGE, init_scenario=scenario))
        for address, value in [(0xE000E014, 15999), (0x40003008, 2047)]:
            with self.subTest(register=address):
                self.assert_denied(execute(IMAGE, init_scenario='warm_pll', final_overrides={address: value}))

    def test_elf_binary_compiler_origin_and_preserved_hardware_artifacts(self):
        directory = BUILD / IMAGE
        report = verifier.verify(directory / 'firmware.elf', directory / 'firmware.bin')
        self.assertEqual(report['vector_address'], '0x2000d000')
        self.assertGreater(report['free_bytes_after_linker_reservations'], 0)
        metadata = json.loads((directory / 'verification.json').read_text())
        self.assertEqual(metadata['diagnostic'], 'blink-recovered')
        self.assertEqual(metadata['profile'], 'clab-reference')
        self.assertEqual(metadata['pll_recovery_policy'], 'pinned-hal-549-board-hse-25-336-2-4')
        self.assertNotIn('-DEMBED_DIAGNOSTIC_PROBE', metadata['c_flags'])
        source = ROOT / 'examples/remote_blink.emb'
        self.assertEqual(metadata['source_sha256'], hashlib.sha256(source.read_bytes()).hexdigest())
        assembly = (directory / 'program.s').read_text()
        self.assertEqual(metadata['assembly_sha256'], hashlib.sha256(assembly.encode()).hexdigest())
        for symbol in ('embed_gpio_mode', 'embed_gpio_write', 'embed_gpio_toggle', 'embed_delay_ms'):
            self.assertIn('bl ' + symbol, assembly)
        saved = json.loads((ROOT / '.tools/preserved-hardware-probe/manifest.json').read_text(encoding='utf-8-sig'))
        for name, digest in saved.items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest, name)

    def test_recovered_blink_rejects_unverified_size_profile(self):
        result = subprocess.run([sys.executable, str(ROOT / 'firmware/build.py'),
                                str(ROOT / 'examples/remote_blink.emb'), '--diagnostic',
                                'blink-recovered', '--profile', 'size'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('requires the verified clab-reference profile', result.stderr)


if __name__ == '__main__':
    unittest.main()
