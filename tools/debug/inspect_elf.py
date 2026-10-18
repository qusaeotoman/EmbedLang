"""Report symbols and DWARF source coverage without executing an ELF."""
import argparse
import json
from pathlib import Path
from elftools.elf.elffile import ELFFile


def inspect(path):
    with path.open('rb') as stream:
        image = ELFFile(stream)
        symbols = image.get_section_by_name('.symtab')
        functions = [] if symbols is None else [
            {'name': symbol.name, 'address': hex(symbol['st_value']), 'size': symbol['st_size']}
            for symbol in symbols.iter_symbols()
            if symbol['st_info']['type'] == 'STT_FUNC' and (
                symbol.name.startswith('embed_fn_') or symbol.name == 'embed_program_main')]
        sources = set()
        if image.has_dwarf_info():
            dwarf = image.get_dwarf_info()
            for unit in dwarf.iter_CUs():
                lines = dwarf.line_program_for_CU(unit)
                if lines:
                    sources.update(file.name.decode(errors='replace') for file in lines['file_entry'])
        return {'elf': path.as_posix(), 'machine': image['e_machine'],
            'entry': hex(image['e_entry']), 'generated_functions': functions,
            'debug_sections': [section.name for section in image.iter_sections()
                               if section.name.startswith('.debug')],
            'assembly_sources': sorted(source for source in sources if source.endswith(('.s', '.S'))),
            'embedlang_sources': sorted(source for source in sources if source.endswith('.emb')),
            'source_count': len(sources)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('elf', type=Path, nargs='+')
    args = parser.parse_args()
    print(json.dumps([inspect(path) for path in args.elf], indent=2))
