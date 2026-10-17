"""Actual Cortex-M4 HAL recovery gates under synthetic registers, never cLAB."""
import hashlib
import json
import unittest

from clab_diagnostics import ROOT, BUILD, execute, verifier
from clab_init_checks import stages

IMAGE = 'diagnostic_probe_recovered'
CR, PLL, CFGR, CSR = 0x40023800, 0x40023804, 0x40023808, 0x40023874


class RecoveryTests(unittest.TestCase):
    def run_image(self, **kwargs):
        return execute(IMAGE, init_scenario='warm_pll', **kwargs)

    def assert_denied(self, result):
        self.assertEqual(result['generated'], [])
        self.assertIn('SKIP_INIT_ERROR', result['messages'])
        self.assertNotIn('PLL_MATCH_RECOVERED', result['messages'])
        self.assertNotIn('BEFORE_GENERATED', result['messages'])

    def test_confirmed_branch_recovers_and_real_probe_returns_42(self):
        result = self.run_image()
        osc = stages(result)['HAL_RCC_OscConfig']
        self.assertEqual(osc['HAL_STATUS'], '1')
        self.assertEqual(osc['EFFECTIVE_STATUS'], '0')
        self.assertEqual(osc['RETURN'], 'stm32f4xx_hal_rcc.c:549')
        self.assertEqual(result['handler_calls'], 0)
        self.assertIn('INIT_ERRORS=0', result['messages'])
        self.assertEqual(result['messages'].count('PLL_MATCH_RECOVERED'), 1)
        self.assertLess(result['messages'].index('PLL_MATCH_RECOVERED'),
                        result['messages'].index('BEFORE_GENERATED'))
        self.assertIn('PROBE_RESULT=42', result['messages'])
        self.assertEqual(result['messages'][-1], 'TRACE_COMPLETE')
        self.assertEqual(result['generated'], ['embed_fn_diagnostic_probe'])
        self.assertEqual(result['delays'], [250])
        self.assertLess(result['stack_bytes_with_hardware_stubs'], 1024)

    def test_successful_hal_status_needs_no_recovery(self):
        result = self.run_image(hal_overrides={'HAL_RCC_OscConfig': 0})
        self.assertIn('PROBE_RESULT=42', result['messages'])
        self.assertNotIn('PLL_MATCH_RECOVERED', result['messages'])

    def test_each_pll_field_mismatch_is_fatal(self):
        for name, value in [('M', 0x04405418), ('N', 0x044053D9),
                            ('P', 0x04415419), ('Q', 0x05405419), ('source', 0x04005419)]:
            with self.subTest(field=name):
                self.assert_denied(self.run_image(register_overrides={PLL: value}))

    def test_requested_config_changes_are_not_accepted(self):
        # RCC_OscInitTypeDef has six uint32 oscillator fields then PLL fields;
        # offsets are its actual STM32F4 ABI, not a second configuration parser.
        for offset, value in [(36, 335), (44, 5), (4, 0x50000)]:
            with self.subTest(offset=offset):
                self.assert_denied(self.run_image(request_overrides={offset: value}))

    def test_enable_ready_and_bypass_conditions_are_required(self):
        for bit in (24, 25, 16, 17):  # PLLON, PLLRDY, HSEON, HSERDY
            with self.subTest(clear_bit=bit):
                self.assert_denied(self.run_image(register_overrides={CR: 0x03030003 & ~(1 << bit)}))
        self.assert_denied(self.run_image(register_overrides={CR: 0x03070003}))  # bypass != requested crystal
        self.assert_denied(self.run_image(register_overrides={CSR: 2}))  # ready but not enabled

    def test_non_pll_sysclk_is_not_recovered(self):
        self.assert_denied(self.run_image(register_overrides={CFGR: 0x00009406}))

    def test_timeout_busy_and_unproven_error_are_never_normalized(self):
        for status in (1, 2, 3):
            with self.subTest(status=status):
                # Matching registers alone are insufficient: this injected HAL
                # return lacks the confirmed instrumented return-site evidence.
                self.assert_denied(self.run_image(hal_overrides={'HAL_RCC_OscConfig': status}))

    def test_real_lsi_and_watchdog_timeouts_remain_fatal(self):
        for scenario in ('lsi_timeout', 'iwdg_timeout'):
            with self.subTest(scenario=scenario):
                self.assert_denied(execute(IMAGE, init_scenario=scenario))

    def test_other_hal_failures_and_nested_tick_failure_are_fatal(self):
        for name in ('HAL_Init', 'HAL_RCC_ClockConfig', 'HAL_IWDG_Init', 'HAL_SYSTICK_Config'):
            with self.subTest(function=name):
                self.assert_denied(self.run_image(hal_overrides={name: 1}))

    def test_live_state_is_rechecked_after_all_initialization(self):
        for key, value in [(PLL, 0x04405418), (CR, 0x01030003), (CSR, 1),
                           (CFGR, 0x0000900A), ('SystemCoreClock', 16000000),
                           (0xE000E014, 15999), ('PRIMASK', 1),
                           (0x40023C00, 4), (0x40007000, 0),
                           (0x40003004, 3), (0x40003008, 2047), (0x4000300C, 1)]:
            with self.subTest(register=key):
                self.assert_denied(self.run_image(final_overrides={key: value}))

    def test_fake_watchdog_ok_without_configuration_is_rejected(self):
        self.assert_denied(self.run_image(hal_overrides={'HAL_IWDG_Init': 0}))

    def test_elf_and_preserved_reference_diagnostics(self):
        directory = BUILD / IMAGE
        report = verifier.verify(directory / 'firmware.elf', directory / 'firmware.bin')
        self.assertGreater(report['free_bytes_after_linker_reservations'], 0)
        metadata = json.loads((directory / 'verification.json').read_text())
        self.assertEqual(metadata['diagnostic'], 'probe-recovered')
        self.assertEqual(metadata['profile'], 'clab-reference')
        for path, digest in json.loads((ROOT / '.tools/preserved-pll-recovery/manifest.json').read_text()).items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), digest, path)


if __name__ == '__main__':
    unittest.main()
