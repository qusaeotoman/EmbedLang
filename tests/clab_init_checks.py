"""Initialization-only diagnostics with synthetic MMIO, never physical cLAB.

Exercises the actual pinned HAL rather than stubbing clock/watchdog init.
Requires firmware/build/diagnostic_init and the earlier official reference ELF.
"""
from pathlib import Path
import hashlib
import json
import unittest

from clab_diagnostics import BUILD, ROOT, execute, verifier


def stages(result):
    output = {}
    current = None
    for message in result['messages']:
        if message.startswith('STAGE='):
            current = message.split('=', 1)[1]
            output[current] = {}
        elif current and '=' in message:
            name, value = message.split('=', 1)
            output[current][name] = value
    return output


class InitTests(unittest.TestCase):
    def test_warm_pll_reproduces_spurious_hal_error_and_reports_line(self):
        result = execute('diagnostic_init', init_scenario='warm_pll')
        detail = stages(result)
        osc = detail['HAL_RCC_OscConfig']
        self.assertEqual(osc['HAL_STATUS'], '1')
        self.assertEqual(osc['RETURN'], 'stm32f4xx_hal_rcc.c:549')
        self.assertEqual(osc['RETURN_FN'], 'HAL_RCC_OscConfig')
        self.assertEqual(osc['HANDLER_CALLS'], '1')
        self.assertTrue(osc['CALL'].startswith('board_main.c:'))
        self.assertEqual(osc['PRE_PLL_MATCH'], '1')
        self.assertEqual(osc['PRE_SYSCLK_PLL'], '1')
        self.assertEqual(osc['PRE_PLL'], osc['POST_PLL'])
        self.assertEqual(detail['HAL_RCC_ClockConfig']['HAL_STATUS'], '0')
        self.assertEqual(detail['HAL_IWDG_Init']['HAL_STATUS'], '0')
        self.assertEqual(detail['HAL_IWDG_Init']['HCLK_VAR'], '168000000')
        self.assertEqual(detail['HAL_IWDG_Init']['SYSTICK_LOAD'], '167999')
        self.assertEqual(result['generated'], [])
        self.assertIn('RECOVERY_NOT_ASSUMED', result['messages'])
        self.assertEqual(result['messages'][-1], 'INIT_REPORT_ONLY')
        self.assertLess(result['stack_bytes_with_hardware_stubs'], 1024)

    def test_genuine_pll_mismatch_is_not_mislabeled_as_identical(self):
        result = execute('diagnostic_init', init_scenario='different_pll')
        self.assertEqual(stages(result)['HAL_RCC_OscConfig']['PRE_PLL_MATCH'], '0')
        self.assertEqual(result['generated'], [])

    def test_lsi_timeout_has_distinct_hal_status_and_return_line(self):
        result = execute('diagnostic_init', init_scenario='lsi_timeout')
        osc = stages(result)['HAL_RCC_OscConfig']
        self.assertEqual(osc['HAL_STATUS'], '3')
        self.assertEqual(osc['RETURN'], 'stm32f4xx_hal_rcc.c:368')
        self.assertEqual(result['generated'], [])

    def test_iwdg_timeout_identifies_original_call_site(self):
        result = execute('diagnostic_init', init_scenario='iwdg_timeout')
        iwdg = stages(result)['HAL_IWDG_Init']
        self.assertEqual(iwdg['HAL_STATUS'], '3')
        self.assertEqual(iwdg['CALL'], 'iwdg.c:36')
        self.assertEqual(iwdg['RETURN'], 'stm32f4xx_hal_iwdg.c:181')
        self.assertEqual(iwdg['HANDLER_CALLS'], '1')
        self.assertIn('INIT_ERRORS=2', result['messages'])
        self.assertEqual(result['generated'], [])

    def test_pristine_reference_encounters_same_warm_error_but_finishes(self):
        path = ROOT / '.tools/sdk-clab-reference-build/sdk_clab_reference.elf'
        if not path.is_file():
            self.skipTest('Build the pristine reference ELF for this optional comparison')
        result = execute('reference', init_scenario='warm_pll', elf_path=path)
        self.assertEqual(result['handler_calls'], 1)
        self.assertIn('LEDs Blink test', result['messages'])
        self.assertEqual(sum(result['delays']), 2500)
        self.assertEqual(result['dump_bytes'], 10)

    def test_elf_verification_and_preserved_artifacts(self):
        image = BUILD / 'diagnostic_init'
        verifier.verify(image / 'firmware.elf', image / 'firmware.bin')
        metadata = json.loads((image / 'verification.json').read_text())
        self.assertEqual(metadata['diagnostic'], 'init')
        self.assertEqual(len(metadata['instrumented_sources_sha256']), 3)
        saved = ROOT / '.tools/preserved-init-diagnostics/manifest.json'
        if saved.is_file():
            for name, digest in json.loads(saved.read_text()).items():
                self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest, name)


if __name__ == '__main__':
    unittest.main()
