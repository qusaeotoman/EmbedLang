"""Build RAM firmware locally. Never uploads, flashes, or connects to cLAB."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

from tools.verify import API, CONSTANTS, verify

ROOT = Path(__file__).resolve().parent.parent
FW = ROOT / 'firmware'
VENDOR = FW / 'vendor/SDK_cLAB'


def run(command, **kwargs):
    return subprocess.run([str(x) for x in command], check=True, **kwargs)


def check_vendor():
    manifest = json.loads((FW / 'vendor/manifest.json').read_text(encoding='utf-8'))
    for name, digest in manifest['sha256'].items():
        data = (FW / 'vendor' / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f'Vendored source changed: {name}')
    return manifest['revisions']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--toolchain-bin', type=Path, help='Directory containing arm-none-eabi-gcc and binutils')
    parser.add_argument('--output', type=Path, help='Default: firmware/build/<source stem>')
    parser.add_argument('--profile', choices=('clab-reference', 'size'), default='clab-reference',
                        help='Default matches the hardware-tested reference flags; size is an experimental comparison')
    parser.add_argument('--diagnostic', choices=('probe', 'blink', 'init', 'probe-recovered', 'blink-recovered'),
                        help='Marked probe/Blink, or initialization-only stage/status/source reporting')
    args = parser.parse_args()
    if args.diagnostic in ('probe-recovered', 'blink-recovered') and args.profile != 'clab-reference':
        parser.error(args.diagnostic + ' requires the verified clab-reference profile')
    source = args.source.resolve()
    output_name = ('diagnostic_' + args.diagnostic.replace('-', '_') if args.diagnostic else source.stem)
    if args.profile == 'size':
        output_name += '_size'
    output = (args.output or FW / 'build' / output_name).resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Remove only stale success artifacts so a failed rebuild cannot look successful.
    for name in ('firmware.elf', 'firmware.bin', 'verification.json'):
        (output / name).unlink(missing_ok=True)
    revisions = check_vendor()

    def tool(name):
        executable = 'arm-none-eabi-' + name + ('.exe' if os.name == 'nt' else '')
        found = str(args.toolchain_bin.resolve() / executable) if args.toolchain_bin else shutil.which(executable)
        if not found or not Path(found).is_file():
            raise RuntimeError('Missing ' + executable + '; see docs/STM32_RUNTIME.md for installation')
        return found

    gcc, objcopy, nm, objdump = [tool(n) for n in ('gcc', 'objcopy', 'nm', 'objdump')]
    jars = sorted((ROOT / 'compiler/build/install/embedlang/lib').glob('*.jar'))
    if not jars:
        raise RuntimeError('Run gradlew :compiler:installDist first')
    java_home = os.environ.get('JAVA_HOME')
    java = str(Path(java_home) / 'bin' / ('java.exe' if os.name == 'nt' else 'java')) if java_home else 'java'
    assembly = run([java, '-cp', os.pathsep.join(map(str, jars)), 'embedlang.MainKt',
                    '--emit-asm', source], capture_output=True, text=True).stdout
    (output / 'program.s').write_text(assembly, encoding='utf-8')
    target = ['-mcpu=cortex-m4', '-mthumb', '-mfpu=fpv4-sp-d16', '-mfloat-abi=hard']
    includes = [VENDOR / 'Core/Inc', VENDOR / 'Drivers/STM32F4xx_HAL_Driver/Inc',
                VENDOR / 'Drivers/CMSIS/Include', VENDOR / 'Drivers/CMSIS/Device/ST/STM32F4xx/Include',
                FW / 'include']
    profile_flags = ['-O0', '-DDEBUG'] if args.profile == 'clab-reference' else ['-Os']
    flags = target + ['-std=gnu11', *profile_flags, '-g3', '-ffunction-sections', '-fdata-sections',
                      '-fstack-usage', '-Wall', '-Wextra', '-DSTM32F407xx', '-DUSE_HAL_DRIVER']
    flags += ['-I' + str(p) for p in includes]
    flags += ['-I' + str(VENDOR / 'Drivers/STM32F4xx_HAL_Driver/Inc/Legacy')]
    if args.diagnostic:
        flags.append('-DEMBED_CLAB_DIAGNOSTIC')
        if args.diagnostic in ('probe', 'probe-recovered'):
            flags.append('-DEMBED_DIAGNOSTIC_PROBE')
        if args.diagnostic in ('init', 'probe-recovered', 'blink-recovered'):
            flags.append('-DEMBED_DIAGNOSTIC_INIT')
        if args.diagnostic in ('probe-recovered', 'blink-recovered'):
            flags.append('-DEMBED_PLL_RECOVERY')
    sources = [FW / 'src/board_main.c', FW / 'src/embed_runtime.c']
    if args.diagnostic:
        sources.append(FW / 'src/clab_diagnostics.c')
    if args.diagnostic in ('init', 'probe-recovered', 'blink-recovered'):
        sources.append(FW / 'src/clab_init_detail.c')
    sources += [VENDOR / 'Core/Src' / (s + '.c') for s in
                ('gpio', 'iwdg', 'system_stm32f4xx', 'stm32f4xx_it', 'stm32f4xx_hal_msp',
                 'trace', 'crc32', 'sysmem', 'syscalls')]
    sources += [VENDOR / 'Drivers/STM32F4xx_HAL_Driver/Src' / ('stm32f4xx_hal' + s + '.c') for s in
                ('', '_gpio', '_rcc', '_rcc_ex', '_cortex', '_pwr', '_pwr_ex', '_flash', '_flash_ex', '_iwdg')]
    objects = []
    instrumented_sources = {}
    for index, src in enumerate(sources):
        obj = output / f'{index:02}_{src.stem}.o'
        compile_src = src
        extra_flags = []
        if args.diagnostic in ('init', 'probe-recovered', 'blink-recovered'):
            if src in (FW / 'src/board_main.c', VENDOR / 'Core/Src/iwdg.c'):
                extra_flags = ['-include', str(FW / 'include/clab_init_capture.h')]
            if src.name in ('stm32f4xx_hal.c', 'stm32f4xx_hal_rcc.c', 'stm32f4xx_hal_iwdg.c'):
                # Log failure returns in generated build-only copies. Keep vendor
                # bytes intact and preserve original file/line via #line.
                text = src.read_text(encoding='utf-8')
                text = re.sub(r'\breturn (HAL_ERROR|HAL_TIMEOUT|HAL_BUSY);',
                              r'{ embed_init_note_return(__func__, __FILE__, __LINE__, \1); return \1; }', text)
                relative = src.relative_to(ROOT).as_posix()
                text = '#include "clab_init_detail.h"\n#line 1 "' + relative + '"\n' + text
                compile_src = output / ('instrumented_' + src.name)
                compile_src.write_text(text, encoding='utf-8')
                instrumented_sources[relative] = hashlib.sha256(compile_src.read_bytes()).hexdigest()
        run([gcc, *flags, *extra_flags, '-c', compile_src, '-o', obj])
        objects.append(obj)
    startup = output / 'startup.o'
    run([gcc, *target, '-g3', '-c', VENDOR / 'Core/Startup/startup_stm32f407vgtx.s', '-o', startup])
    program = output / 'program.o'
    run([gcc, *target, '-c', output / 'program.s', '-o', program])
    run([objcopy, '--redefine-sym', 'main=embed_program_main', program])
    elf, binary = output / 'firmware.elf', output / 'firmware.bin'
    # Keep the entire public runtime ABI visible for validation, even for tiny programs.
    keep = ['-Wl,--undefined=embed_' + n for n in API]
    keep += ['-Wl,--undefined=embed_const_' + n for n in CONSTANTS]
    keep.append('-Wl,--undefined=embed_program_main')
    run([gcc, *target, '--specs=nano.specs', '--specs=nosys.specs', '-static',
         '-T' + str(VENDOR / 'STM32F407VGTX_RAM.ld'), '-Wl,--gc-sections',
         '-Wl,-Map=' + str(output / 'firmware.map'), *keep,
         startup, program, *objects, '-Wl,--start-group', '-lc', '-lm', '-Wl,--end-group', '-o', elf])
    run([objcopy, '-O', 'binary', elf, binary])
    report = verify(elf, binary)
    report['toolchain'] = run([gcc, '--version'], capture_output=True, text=True).stdout.splitlines()[0]
    report['upstream_revisions'] = revisions
    report['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    report['assembly_sha256'] = hashlib.sha256(assembly.encode()).hexdigest()
    report['profile'] = args.profile
    report['diagnostic'] = args.diagnostic
    report['pll_recovery_policy'] = ('pinned-hal-549-board-hse-25-336-2-4'
                                     if args.diagnostic in ('probe-recovered', 'blink-recovered') else None)
    report['instrumented_sources_sha256'] = instrumented_sources
    report['c_flags'] = flags
    report['integration_sources_sha256'] = {
        str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sources
    }
    report['stack_analysis'] = 'Link-time reservation only; see .su files and docs. Not a whole-program bound.'
    (output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    for executable, options, filename in ((nm, ['-n'], 'symbols.txt'), (objdump, ['-h', '-d'], 'disassembly.txt')):
        with (output / filename).open('w', encoding='utf-8') as stream:
            run([executable, *options, elf], stdout=stream)
    print(json.dumps(report, indent=2))
    print(f'ELF: {elf}\nBIN: {binary}')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f'Firmware build failed: {error}', file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr, file=sys.stderr)
        sys.exit(1)
