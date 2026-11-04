from collections import Counter
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

XmlElement = etree._Element  # pyright: ignore[reportPrivateUsage]
MUSICXML_PARSER = etree.XMLParser(remove_blank_text=True)


def merge_mxl_files(mxl_paths: list[Path]) -> str:
    roots = [_parse_musicxml_root(path) for path in mxl_paths]
    merged = _merge_roots(roots)

    # validate
    if not merged.strip():
        raise ValueError('Generated MusicXML is empty')
    if not etree.fromstring(merged, parser=MUSICXML_PARSER).findall('.//note'):
        raise ValueError('Generated MusicXML does not contain any note elements')

    return merged.decode('utf-8')


def _parse_musicxml_root(path: Path) -> XmlElement:
    if path.suffix.lower() == '.mxl':
        with ZipFile(path) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(('.musicxml', '.xml'))]
            if not names:
                raise ValueError(f'No MusicXML file found inside archive: {path}')
            xml_bytes = archive.read(names[0])
    else:
        xml_bytes = path.read_bytes()

    return etree.fromstring(xml_bytes, parser=MUSICXML_PARSER)


def _merge_roots(roots: list[XmlElement]) -> bytes:
    """Appends each page's measures to the part of the same name; empty measures keep parts aligned.

    Measures are renumbered from 1: Audiveris numbers each page's from 1.
    """
    if not roots:
        raise ValueError('No MusicXML documents were provided for merge')

    merged_root = deepcopy(roots[0])
    merged_part_list = _get_or_create_part_list(merged_root)
    part_by_name = _part_by_name(merged_root)
    for root in roots[1:]:
        score_part_by_id = {score_part.get('id'): score_part for score_part in root.iter('score-part')}
        page_part_by_name = _part_by_name(root)

        # add parts still not in the merged dict
        for name, part in page_part_by_name.items():
            if name not in part_by_name:
                part_by_name[name] = _add_part(merged_root, merged_part_list, score_part_by_id[part.get('id')])
        _pad_with_empty_measures(list(part_by_name.values()))

        # add measures to the parts
        for name, part in page_part_by_name.items():
            part_by_name[name].extend(deepcopy(measure) for measure in part.iter('measure'))
        _pad_with_empty_measures(list(part_by_name.values()))

    for part in merged_root.iter('part'):
        for number, measure in enumerate(part.iter('measure'), start=1):
            measure.set('number', str(number))
    return etree.tostring(merged_root, encoding='utf-8', pretty_print=True, xml_declaration=True)


def _part_by_name(root: XmlElement) -> dict[str, XmlElement]:
    """The parts, keyed like `Voice #1`: Audiveris calls every single-staff part Voice and numbers ids per page."""
    part_name_by_id = {
        score_part.get('id'): score_part.findtext('part-name') or '' for score_part in root.iter('score-part')
    }
    seen: Counter[str] = Counter()
    part_by_name: dict[str, XmlElement] = {}
    for part in root.iter('part'):
        name = part_name_by_id.get(part.get('id'), '')
        seen[name] += 1
        part_by_name[f'{name} #{seen[name]}'] = part
    return part_by_name


def _add_part(root: XmlElement, part_list: XmlElement, score_part: XmlElement) -> XmlElement:
    """Adds an empty part described by a copy of `score_part`, under the next free id."""
    part_id = f'P{len(root.findall("part")) + 1}'
    new_score_part = deepcopy(score_part)
    new_score_part.set('id', part_id)
    part_list.append(new_score_part)
    return etree.SubElement(root, 'part', id=part_id)


def _pad_with_empty_measures(parts: list[XmlElement]) -> None:
    lengths = [len(part.findall('measure')) for part in parts]
    for part, length in zip(parts, lengths, strict=True):
        part.extend(etree.Element('measure') for _ in range(max(lengths) - length))


def _get_or_create_part_list(root: XmlElement) -> XmlElement:
    part_list = root.find('part-list')
    if part_list is not None:
        return part_list

    part_list = etree.Element('part-list')
    root.insert(0, part_list)
    return part_list
