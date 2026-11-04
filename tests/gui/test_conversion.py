import io
from pathlib import Path
from zipfile import ZipFile

import pytest

from page_break.audiveris import Binarization
from page_break.gui.conversion import ScoreInput, build_cases, convert


def test_convert_zips_several_combinations_with_a_failure_report(monkeypatch: pytest.MonkeyPatch) -> None:
    # GIVEN
    outcomes: dict[str, list[int] | Exception] = {
        'dpi450-global160': [],
        'dpi450-global180': [2],
        'dpi450-global200': RuntimeError('Audiveris failed for pages: 1, 2'),
    }

    def fake_convert_score(*, output_path: Path, working_dir: Path, **_: object) -> list[int]:
        outcome = outcomes[working_dir.name]
        if isinstance(outcome, Exception):
            raise outcome
        output_path.write_text('<score-partwise/>', encoding='utf-8')
        return outcome

    monkeypatch.setattr('page_break.gui.conversion.convert_score', fake_convert_score)

    # WHEN
    cases = build_cases(dpis=[450], binarization=Binarization.GLOBAL, thresholds=[160, 180, 200])
    result = convert(ScoreInput(url='https://example.com/le_cygne.pdf'), '', cases, jobs=1, timeout=10)

    # THEN
    assert (result.file_name, result.all_failed) == ('le_cygne.zip', False)
    with ZipFile(io.BytesIO(result.data)) as archive:
        assert sorted(archive.namelist()) == [
            'failures.txt',
            'le_cygne-dpi450-global160.musicxml',
            'le_cygne-dpi450-global180.musicxml',
        ]
        assert archive.read('failures.txt').decode() == (
            'dpi450-global180: Audiveris failed on page(s) 2, which are left out of the score\n'
            'dpi450-global200: Audiveris failed for pages: 1, 2\n'
        )
