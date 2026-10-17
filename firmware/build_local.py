"""Build local SDK-1.1M Flash firmware; never connects, erases or programs a board."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from build import ROOT, FW, VENDOR, run, check_vendor
from local.verify import verify
from tools.verify import API, CONSTANTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--toolchain-bin', type=Path, required=True)
    parser.add_argument('--mcu', choices=('stm32f407vgt6', 'stm32f427vit6'), default='stm32f407vgt6')
    parser.add_argument('--oled', action='store_true', help='Link the local OLED runtime (F427 only); separate output')
    args = parser.parse_args()
    is_f427 = args.mcu == 'stm32f427vit6'
    if args.oled and not is_f427:
        parser.error('--oled requires --mcu stm32f427vit6')
    if args.oled:
        required = ('Core/Src/oled.c', 'Core/Src/fonts.c', 'Core/Inc/oled.h', 'Core/Inc/fonts.h')
        driver_root = FW / 'vendor/SDK-1.1M/SDK_OLED'
        if any(not (driver_root / name).is_file() for name in required):
            raise RuntimeError('Public snapshot excludes unlicensed OLED/font files; see PUBLICATION_NOTES.md. Supply separately permitted copies before building OLED.')
    output = FW / ('build/local_oled_f427' if args.oled else 'build/local_blink_f427' if is_f427 else 'build/local_blink')
    output.mkdir(parents=True, exist_ok=True)
    for name in ('firmware.elf', 'firmware.bin', 'verification.json'):
        (output / name).unlink(missing_ok=True)
    revisions = check_vendor()
    sdk = FW / 'vendor/SDK-1.1M/SDK_EXTI'
    cmsis = FW / 'vendor/ST-CMSIS-F4'
    startup_source = (cmsis / 'Source/Templates/gcc/startup_stm32f427xx.s' if is_f427
                      else sdk / 'Core/Startup/startup_stm32f407vgtx.s')
    linker = (FW / 'local/STM32F427VITX_FLASH.ld' if is_f427 else sdk / 'STM32F407VGTX_FLASH.ld')
    tool = lambda name: args.toolchain_bin.resolve() / ('arm-none-eabi-' + name + ('.exe' if os.name == 'nt' else ''))
    gcc, objcopy = tool('gcc'), tool('objcopy')
    jars = sorted((ROOT / 'compiler/build/install/embedlang/lib').glob('*.jar'))
    if not jars:
        raise RuntimeError('Build :compiler:installDist first')
    java = Path(os.environ['JAVA_HOME']) / 'bin/java.exe' if os.name == 'nt' and os.environ.get('JAVA_HOME') else 'java'
    assembly = run([java, '-cp', os.pathsep.join(map(str, jars)), 'embedlang.MainKt',
                    '--emit-asm', args.source.resolve()], capture_output=True, text=True).stdout
    (output / 'program.s').write_text(assembly, encoding='utf-8')
    target = ['-mcpu=cortex-m4', '-mthumb', '-mfpu=fpv4-sp-d16', '-mfloat-abi=hard']
    flags = target + ['-std=gnu11', '-O0', '-g3', '-DDEBUG',
                      '-DSTM32F427xx' if is_f427 else '-DSTM32F407xx', '-DUSE_HAL_DRIVER',
                      '-ffunction-sections', '-fdata-sections', '-fstack-usage', '-Wall', '-Wextra']
    flags += ['-I' + str(VENDOR / p) for p in ('Core/Inc', 'Drivers/STM32F4xx_HAL_Driver/Inc',
              'Drivers/STM32F4xx_HAL_Driver/Inc/Legacy', 'Drivers/CMSIS/Include',
              'Drivers/CMSIS/Device/ST/STM32F4xx/Include')]
    flags += ['-I' + str(FW / 'include')]
    if is_f427:
        flags += ['-I' + str(cmsis / 'Include')]
    oled = FW / 'vendor/SDK-1.1M/SDK_OLED'
    if args.oled:
        flags += ['-DHAL_I2C_MODULE_ENABLED', '-I' + str(oled / 'Core/Inc'),
                  '-I' + str(oled / 'Drivers/STM32F4xx_HAL_Driver/Inc')]
    sources = [FW / 'local/main.c', FW / 'src/embed_runtime.c', sdk / 'Core/Src/system_stm32f4xx.c']
    sources += [VENDOR / 'Core/Src' / (n + '.c') for n in ('stm32f4xx_it', 'stm32f4xx_hal_msp', 'trace', 'crc32', 'sysmem', 'syscalls')]
    sources += [VENDOR / 'Drivers/STM32F4xx_HAL_Driver/Src' / ('stm32f4xx_hal' + n + '.c')
                for n in ('', '_gpio', '_rcc', '_rcc_ex', '_cortex', '_pwr', '_pwr_ex', '_flash', '_flash_ex')]
    if args.oled:
        sources += [FW / 'local/oled/embed_oled.c', oled / 'Core/Src/oled.c', oled / 'Core/Src/fonts.c',
                    oled / 'Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_i2c.c',
                    VENDOR / 'Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_dma.c']
    objects = []
    for i, source in enumerate(sources):
        obj = output / f'{i:02}_{source.stem}.o'
        extra = ['-DHAL_I2C_Mem_Write=embed_oled_mem_write'] if source == oled / 'Core/Src/oled.c' else []
        run([gcc, *flags, *extra, '-c', source, '-o', obj])
        objects.append(obj)
    startup, program = output / 'startup.o', output / 'program.o'
    run([gcc, *target, '-g3', '-c', startup_source, '-o', startup])
    run([gcc, *target, '-g3', '-c', output / 'program.s', '-o', program])
    run([objcopy, '--redefine-sym', 'main=embed_program_main', program])
    elf, binary = output / 'firmware.elf', output / 'firmware.bin'
    keep = ['-Wl,--undefined=embed_' + n for n in API]
    keep += ['-Wl,--undefined=embed_const_' + n for n in CONSTANTS]
    run([gcc, *target, '--specs=nano.specs', '--specs=nosys.specs', '-static',
         '-T' + str(linker), '-Wl,--gc-sections', '-Wl,-Map=' + str(output / 'firmware.map'),
         *keep, startup, program, *objects, '-Wl,--start-group', '-lc', '-lm', '-Wl,--end-group', '-o', elf])
    run([objcopy, '-O', 'binary', elf, binary])
    report = verify(elf, binary, mcu=args.mcu, oled=args.oled)
    report.update(upstream_revisions=revisions, c_flags=flags,
                  source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
                  assembly_sha256=hashlib.sha256(assembly.encode()).hexdigest(),
                  toolchain=run([gcc, '--version'], capture_output=True, text=True).stdout.splitlines()[0],
                  watchdog='not started in software; inspect hardware option bytes before deployment',
                  pll_recovery=False, oled=args.oled, mcu=args.mcu, linker_script=str(linker), startup_source=str(startup_source),
                  integration_sources_sha256={str(p.relative_to(ROOT)).replace('\\', '/'):
                      hashlib.sha256(p.read_bytes()).hexdigest() for p in [*sources, startup_source, linker]})
    (output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    for name, options, filename in [('nm', ['-n'], 'symbols.txt'), ('objdump', ['-h', '-d'], 'disassembly.txt')]:
        with (output / filename).open('w', encoding='utf-8') as stream:
            run([tool(name), *options, elf], stdout=stream)
    print(json.dumps(report, indent=2))
    print(f'ELF: {elf}\nBIN: {binary}')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as error:
        print('Local build failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
