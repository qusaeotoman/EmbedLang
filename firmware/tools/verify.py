"""Fail closed on a firmware image that violates the pinned cLAB RAM layout."""
import hashlib
import struct
from pathlib import Path
from elftools.elf.elffile import ELFFile

RAM_START, RAM_END = 0x2000D000, 0x20020000
API = ('gpio_mode', 'gpio_write', 'gpio_read', 'gpio_toggle', 'delay_ms', 'millis')
CONSTANTS = {'LED_GREEN': 1, 'LED_YELLOW': 2, 'LED_RED': 3, 'BUTTON_1': 4,
             'INPUT': 0, 'OUTPUT': 1, 'HIGH': 1, 'LOW': 0}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(elf_path, bin_path):
    binary = Path(bin_path).read_bytes()
    with Path(elf_path).open('rb') as stream:
        elf = ELFFile(stream)
        require(elf.elfclass == 32 and elf.little_endian and elf['e_machine'] == 'EM_ARM',
                'Expected little-endian ARM ELF32')
        symbols = {s.name: s for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name}
        undefined = [n for n, s in symbols.items() if s['st_shndx'] == 'SHN_UNDEF']
        require(not undefined, f'Unresolved symbols: {undefined}')
        for name in ['main', 'embed_program_main', 'Reset_Handler', 'SystemInit', 'SysTick_Handler',
                     'SDK_TRACE_Start', 'SDK_TRACE_Stop', 'SDK_TRACE_Timestamp'] + ['embed_' + n for n in API]:
            require(name in symbols and symbols[name]['st_info']['type'] == 'STT_FUNC',
                    f'Missing function: {name}')
        for name, expected in CONSTANTS.items():
            sym = symbols.get('embed_const_' + name)
            require(sym is not None and sym['st_size'] == 4, f'Missing uint32 constant {name}')
            sec = elf.get_section(sym['st_shndx'])
            offset = sym['st_value'] - sec['sh_addr']
            require(struct.unpack_from('<I', sec.data(), offset)[0] == expected, f'Wrong constant {name}')
        sections = []
        expected_binary = bytearray()
        end = RAM_START
        for sec in elf.iter_sections():
            if not sec['sh_flags'] & 2 or not sec['sh_size']:
                continue
            start, size = sec['sh_addr'], sec['sh_size']
            require(RAM_START <= start and start + size <= RAM_END,
                    f'Allocated section outside application RAM: {sec.name}')
            sections.append({'name': sec.name, 'address': hex(start), 'bytes': size})
            end = max(end, start + size)
            if sec['sh_type'] != 'SHT_NOBITS':
                stop = start - RAM_START + size
                if stop > len(expected_binary):
                    expected_binary.extend(b'\0' * (stop - len(expected_binary)))
                expected_binary[start - RAM_START:stop] = sec.data()
        for seg in elf.iter_segments():
            if seg['p_type'] == 'PT_LOAD' and seg['p_memsz']:
                require(RAM_START <= seg['p_paddr'] and seg['p_paddr'] + seg['p_memsz'] <= RAM_END,
                        'Load segment outside application RAM')
                require(seg['p_paddr'] == seg['p_vaddr'], 'Unexpected ROM-to-RAM load address')
        require(binary == bytes(expected_binary), 'BIN does not exactly match ELF loadable section bytes')
        vectors = elf.get_section_by_name('.isr_vector')
        require(vectors is not None and vectors['sh_addr'] == RAM_START, 'Wrong vector table address')
        sp, reset = struct.unpack_from('<II', vectors.data())
        require(sp == RAM_END and sp % 8 == 0, 'Wrong initial stack pointer')
        require(reset == symbols['Reset_Handler']['st_value'] and reset & 1, 'Wrong reset vector')
        require(elf['e_entry'] == reset, 'ELF entry differs from reset vector')
        systick = struct.unpack_from('<I', vectors.data(), 15 * 4)[0]
        require(systick == symbols['SysTick_Handler']['st_value'], 'Wrong SysTick vector')
        bss_end = symbols['_ebss']['st_value']
        heap = symbols['_Min_Heap_Size']['st_value']
        stack = symbols['_Min_Stack_Size']['st_value']
        require(stack >= 1024 and bss_end + heap + stack <= RAM_END, 'Insufficient heap/stack space')
        return {'binary_bytes': len(binary), 'binary_sha256': hashlib.sha256(binary).hexdigest(),
                'vector_address': hex(RAM_START), 'initial_sp': hex(sp), 'reset_vector': hex(reset),
                'reserved_heap_bytes': heap, 'minimum_stack_bytes': stack,
                'free_bytes_after_linker_reservations': RAM_END - end,
                'bss_end': hex(bss_end), 'sections': sections, 'unresolved_symbols': []}
