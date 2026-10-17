"""Verify local Flash ELF/BIN independently of the cLAB SRAM verifier."""
import hashlib
import struct
from pathlib import Path
from elftools.elf.elffile import ELFFile
from tools.verify import API, CONSTANTS, require

FLASH, FLASH_END = 0x08000000, 0x08100000
RAM, RAM_END = 0x20000000, 0x20020000


def verify(elf_path, bin_path, *, mcu='stm32f407vgt6', oled=False):
    flash_end, ram_end, vector_bytes = {
        'stm32f407vgt6': (FLASH_END, RAM_END, 392),
        'stm32f427vit6': (0x08200000, 0x20030000, 428),
    }[mcu]
    binary = Path(bin_path).read_bytes()
    with Path(elf_path).open('rb') as stream:
        elf = ELFFile(stream)
        require(elf.elfclass == 32 and elf.little_endian and elf['e_machine'] == 'EM_ARM', 'Expected ARM ELF32')
        symbols = {s.name: s for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name}
        require(not [n for n, s in symbols.items() if s['st_shndx'] == 'SHN_UNDEF'], 'Unresolved symbols')
        for name in ('main', 'embed_program_main', 'Reset_Handler', 'SystemInit', 'SysTick_Handler',
                     'local_blink_finished', *('embed_' + n for n in API)):
            require(name in symbols and symbols[name]['st_info']['type'] == 'STT_FUNC', 'Missing function: ' + name)
        require('embed_init_osc' not in symbols and 'HAL_IWDG_Init' not in symbols, 'Unexpected recovery/watchdog code')
        if oled:
            require(mcu == 'stm32f427vit6', 'OLED profile requires F427')
            for name in ('embed_oled_init', 'embed_oled_clear', 'embed_oled_cursor',
                         'embed_oled_write_char', 'embed_oled_update', 'HAL_I2C_Init',
                         'HAL_I2C_Mem_Write', 'embed_oled_mem_write'):
                require(name in symbols and symbols[name]['st_info']['type'] == 'STT_FUNC', 'Missing OLED function: ' + name)
        for name, value in CONSTANTS.items():
            s = symbols['embed_const_' + name]
            sec = elf.get_section(s['st_shndx'])
            require(s['st_size'] == 4 and struct.unpack_from('<I', sec.data(), s['st_value'] - sec['sh_addr'])[0] == value,
                    'Wrong constant: ' + name)
        expected = bytearray()
        for segment in elf.iter_segments():
            if segment['p_type'] != 'PT_LOAD' or not segment['p_memsz']:
                continue
            v, p, mem, size = (segment[k] for k in ('p_vaddr', 'p_paddr', 'p_memsz', 'p_filesz'))
            require((FLASH <= v and v + mem <= flash_end) or (RAM <= v and v + mem <= ram_end), 'Invalid segment VMA')
            if size:
                require(FLASH <= p and p + size <= flash_end, 'Invalid load address')
                stop = p - FLASH + size
                expected.extend(b'\0' * max(0, stop - len(expected)))
                expected[p - FLASH:stop] = segment.data()
        sections = []
        for sec in elf.iter_sections():
            if sec['sh_flags'] & 2 and sec['sh_size']:
                a, size = sec['sh_addr'], sec['sh_size']
                require((FLASH <= a and a + size <= flash_end) or (RAM <= a and a + size <= ram_end), 'Section outside Flash/SRAM')
                sections.append({'name': sec.name, 'address': hex(a), 'bytes': size})
        require(binary == bytes(expected), 'BIN differs from ELF Flash load image')
        vectors = elf.get_section_by_name('.isr_vector')
        require(vectors['sh_addr'] == FLASH, 'Vectors must be at 0x08000000')
        require(vectors['sh_size'] == vector_bytes, 'Wrong device interrupt-vector table size')
        sp, reset = struct.unpack_from('<II', vectors.data())
        require(sp == ram_end and reset == symbols['Reset_Handler']['st_value'] and reset & 1, 'Invalid reset vectors')
        require(elf['e_entry'] == reset, 'Wrong entry point')
        require(struct.unpack_from('<I', vectors.data(), 60)[0] == symbols['SysTick_Handler']['st_value'], 'Wrong SysTick vector')
        require(symbols['_sdata']['st_value'] == RAM, 'Wrong .data VMA')
        require(FLASH <= symbols['_sidata']['st_value'] < flash_end, 'Missing Flash .data initializer')
        heap, stack = (symbols[n]['st_value'] for n in ('_Min_Heap_Size', '_Min_Stack_Size'))
        bss_end = symbols['_ebss']['st_value']
        require(stack >= 1024 and bss_end + heap + stack <= ram_end, 'Insufficient heap/stack RAM')
        return {'target': 'local-flash', 'binary_bytes': len(binary), 'binary_sha256': hashlib.sha256(binary).hexdigest(),
                'vector_address': hex(FLASH), 'initial_sp': hex(sp), 'reset_vector': hex(reset),
                'bss_end': hex(bss_end), 'reserved_heap_bytes': heap, 'minimum_stack_bytes': stack,
                'flash_end': hex(flash_end), 'ram_end': hex(ram_end), 'vector_bytes': vector_bytes,
                'unresolved_symbols': [], 'sections': sections}
