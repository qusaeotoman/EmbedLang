"""Optional real ARM execution validation, separate from the portable JUnit suite.

Requires installDist, GNU arm-none-eabi-as/ld, unicorn and pyelftools.
Only test artifacts are assembled/linked; the compiler still emits text only.
No linker script, startup code, hardware runtime, or board access is introduced.
"""
import argparse
import os
from pathlib import Path
import struct
import subprocess

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS
from unicorn.arm_const import (
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_R7, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
    UC_CPU_ARM_CORTEX_M4,
)

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--assembler', default='arm-none-eabi-as')
    parser.add_argument('--linker', default='arm-none-eabi-ld')
    args = parser.parse_args()
    output = ROOT / '.tools' / 'arm-execution'
    output.mkdir(parents=True, exist_ok=True)
    jars = sorted((ROOT / 'compiler/build/install/embedlang/lib').glob('*.jar'))
    if not jars:
        raise RuntimeError('Run gradlew :compiler:installDist first')
    java_home = os.environ.get('JAVA_HOME')
    java = str(Path(java_home) / 'bin' / ('java.exe' if os.name == 'nt' else 'java')) if java_home else 'java'
    emitted = subprocess.run([
        java, '-cp', os.pathsep.join(map(str, jars)), 'embedlang.MainKt',
        '--emit-asm', str(ROOT / 'tests/fixtures/arm_execution.emb'),
    ], check=True, capture_output=True, text=True).stdout
    assembly = output / 'checks.s'
    assembly.write_text(emitted, encoding='utf-8')
    obj, elf = output / 'checks.o', output / 'checks.elf'
    subprocess.run([args.assembler, '-mcpu=cortex-m4', '-mthumb', '-o', str(obj), str(assembly)], check=True)
    # Built-in linker layout for a host-only test; no project linker script.
    subprocess.run([args.linker, '-Ttext=0x10000', '-e', 'main', '-o', str(elf), str(obj)], check=True)
    with elf.open('rb') as stream:
        image = ELFFile(stream)
        text = image.get_section_by_name('.text')
        code, base = text.data(), text['sh_addr']
        symbols = {s.name: s['st_value'] for s in image.get_section_by_name('.symtab').iter_symbols()}

    cases = [
        ('add', [10, 20], 30), ('sum6', [1, 2, 3, 4, 5, 6], 21),
        ('nested', [10], 44), ('factorial', [6], 720), ('countdown', [10], 55),
        ('byte_wrap', [], 0), ('signed_div', [], -2), ('signed_mod', [], -1),
        ('unsigned_div', [], 1431655765), ('unsigned_mod', [], 3),
        ('unsigned_compare', [], 1), ('signed_compare', [], 1),
        ('negation', [], -12), ('short_circuit', [], 1), ('bool_parameter', [2], 1),
    ]
    for name, arguments, expected in cases:
        cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        cpu.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M4)
        cpu.mem_map(base, (len(code) + 4095) // 4096 * 4096)
        cpu.mem_write(base, code)
        cpu.mem_map(0x20000000, 0x20000)
        sentinel = 0x90000
        cpu.mem_map(sentinel, 4096)
        initial_sp, initial_r7 = 0x20010000, 0x12345678
        cpu.reg_write(UC_ARM_REG_SP, initial_sp)
        cpu.reg_write(UC_ARM_REG_R7, initial_r7)
        cpu.reg_write(UC_ARM_REG_LR, sentinel | 1)
        registers = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3]
        for index, argument in enumerate(arguments):
            if index < 4:
                cpu.reg_write(registers[index], argument & 0xffffffff)
            else:
                cpu.mem_write(initial_sp + (index - 4) * 4, struct.pack('<I', argument & 0xffffffff))
        cpu.emu_start(symbols['embed_fn_' + name] | 1, sentinel, count=100000)
        assert cpu.reg_read(UC_ARM_REG_PC) == sentinel, f'{name}: did not return (short-circuit/loop failure)'
        actual = cpu.reg_read(UC_ARM_REG_R0)
        assert actual == expected & 0xffffffff, f'{name}: expected {expected}, got {actual}'
        assert cpu.reg_read(UC_ARM_REG_SP) == initial_sp, f'{name}: stack not restored'
        assert cpu.reg_read(UC_ARM_REG_R7) == initial_r7, f'{name}: callee-saved r7 corrupted'
        print(f'{name}: passed')
    print(f'{len(cases)} ARM execution checks passed; stack and r7 restored in every case')


if __name__ == '__main__':
    main()
