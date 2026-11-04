from pathlib import Path

from lxml import etree

from page_break.musicxml import merge_mxl_files

MUSICXML_DIR = Path(__file__).parent / 'resources' / 'musicxml'
PAGE_1_MXL = MUSICXML_DIR / 'le_cygne_page1.mxl'
PAGE_2_MXL = MUSICXML_DIR / 'le_cygne_page2.mxl'
SYSTEM_1_MXL = MUSICXML_DIR / 'le_cygne_system1.mxl'
# Audiveris calls the piano P1 here: the id the viola (named Voice) has when both are on the page.
SYSTEM_1_PIANO_ONLY_MXL = MUSICXML_DIR / 'le_cygne_system1_piano_only.mxl'


def test_merge_mxl_files_appends_the_measures_of_real_audiveris_pages() -> None:
    # WHEN
    merged = merge_mxl_files([PAGE_1_MXL, PAGE_2_MXL])

    # THEN
    root = etree.fromstring(merged.encode())
    assert [part.findtext('part-name') for part in root.findall('part-list/score-part')] == ['Voice', 'Piano']
    numbers = [str(number) for number in range(1, 15)]
    assert {part.get('id'): [m.get('number') for m in part.findall('measure')] for part in root.findall('part')} == {
        'P1': numbers,
        'P2': numbers,
    }


def test_merge_mxl_files_adds_a_part_that_enters_on_a_later_page() -> None:
    # WHEN
    merged = merge_mxl_files([SYSTEM_1_PIANO_ONLY_MXL, SYSTEM_1_MXL])

    # THEN
    assert _notes_per_measure(merged) == {'Piano': [36, 36, 36, 36], 'Voice': [0, 0, 1, 6]}


def test_merge_mxl_files_pads_a_part_missing_from_a_later_page() -> None:
    # WHEN
    merged = merge_mxl_files([SYSTEM_1_MXL, SYSTEM_1_PIANO_ONLY_MXL])

    # THEN
    assert _notes_per_measure(merged) == {'Voice': [1, 6, 0, 0], 'Piano': [36, 36, 36, 36]}


def _notes_per_measure(merged: str) -> dict[str | None, list[int]]:
    root = etree.fromstring(merged.encode())
    names = {score_part.get('id'): score_part.findtext('part-name') for score_part in root.iter('score-part')}
    return {
        names[part.get('id')]: [len(measure.findall('note')) for measure in part.findall('measure')]
        for part in root.findall('part')
    }
