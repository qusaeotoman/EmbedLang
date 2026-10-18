"""Run self-contained public firmware checks after building the documented images.

Does not access hardware. Original historical-preservation tests are unchanged;
they need private fixtures or the original hardware-tested binaries.
"""
import unittest
from pathlib import Path

MODULES = ('firmware_checks', 'clab_diagnostics', 'clab_init_checks',
           'clab_recovery_checks', 'clab_blink_checks',
           'local_firmware_checks', 'local_f427_checks')
HISTORICAL = {
    'clab_recovery_checks.RecoveryTests.test_elf_and_preserved_reference_diagnostics':
        'requires the original private preservation manifest',
    'clab_blink_checks.RecoveredBlinkTests.test_elf_binary_compiler_origin_and_preserved_hardware_artifacts':
        'requires the original private preservation manifest',
    'local_f427_checks.F427Tests.test_generated_assembly_is_unchanged_and_old_firmware_preserved':
        'compares original hardware-tested BIN hashes, not fresh public builds',
}


def cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from cases(item)
        else:
            yield item


def main():
    tests = [test for module in MODULES
             for test in cases(unittest.defaultTestLoader.loadTestsFromName(module))]
    if not set(HISTORICAL).issubset({test.id() for test in tests}):
        raise RuntimeError('Historical test IDs changed; review the public test selection')
    for name, reason in HISTORICAL.items():
        print(f'Not applicable: {name}: {reason}', flush=True)
    # Preserve the assembly equality part of the combined historical F427 check.
    build = Path(__file__).resolve().parent.parent / 'firmware/build'
    if ((build / 'local_blink/program.s').read_bytes()
            != (build / 'local_blink_f427/program.s').read_bytes()):
        raise AssertionError('F407 and F427 must use identical generated Blink assembly')
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.TestSuite(test for test in tests if test.id() not in HISTORICAL))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
