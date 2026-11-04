"""Runs the real pipeline on Le Cygne, with each Audiveris process replaced by one exporting its real first page."""

import shutil
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired

import pytest
from lxml import etree

from page_break.audiveris import AudiverisNotFoundError
from page_break.pipeline import convert_score

RESOURCES_DIR = Path(__file__).parent / 'resources'
SCORE_PDF = RESOURCES_DIR / 'pdf' / 'le_cygne.pdf'
SCORE_IMAGE = RESOURCES_DIR / 'images' / 'le_cygne_page1.jpg'
PAGE_MXL = RESOURCES_DIR / 'musicxml' / 'le_cygne_page1.mxl'
FAILURE_LOG = RESOURCES_DIR / 'audiveris' / 'blank_page_failure.log'
FAST_DPI = 72  # Audiveris is faked, so rendering resolution only costs time


class FakeAudiveris:
    """Stands in for `subprocess.run` of Audiveris: exports a fixed `.mxl`, or fails leaving a real failure log."""

    def __init__(self) -> None:
        self.failing_pages: tuple[int, ...] = ()
        self.timing_out_pages: tuple[int, ...] = ()

    def __call__(self, command: list[str], *, timeout: int, **_: object) -> CompletedProcess[str]:
        output_dir = Path(command[command.index('-output') + 1])
        image_path = Path(command[-1])
        page_number = int(image_path.stem.removeprefix('page-'))
        if page_number in self.timing_out_pages:
            raise TimeoutExpired(command, timeout)
        if page_number in self.failing_pages:
            shutil.copy(FAILURE_LOG, output_dir / f'{image_path.stem}.log')
            return CompletedProcess(command, returncode=1, stdout='', stderr='')
        shutil.copy(PAGE_MXL, output_dir / f'{image_path.stem}.mxl')
        return CompletedProcess(command, returncode=0, stdout='', stderr='')


def test_convert_score_merges_every_page(audiveris: FakeAudiveris, tmp_path: Path) -> None:
    # GIVEN
    output_path = tmp_path / 'output' / 'score.musicxml'

    # WHEN
    failed_pages = convert_score(str(SCORE_PDF), output_path, dpi=FAST_DPI)

    # THEN
    assert _measures_per_part(output_path) == {'P1': 24, 'P2': 24}
    assert failed_pages == []


def test_convert_score_converts_an_image(audiveris: FakeAudiveris, tmp_path: Path) -> None:
    # GIVEN
    output_path = tmp_path / 'score.musicxml'

    # WHEN
    failed_pages = convert_score(str(SCORE_IMAGE), output_path)

    # THEN
    assert _measures_per_part(output_path) == {'P1': 6, 'P2': 6}
    assert failed_pages == []


def test_convert_score_explains_missing_audiveris(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # GIVEN
    output_path = tmp_path / 'score.musicxml'
    monkeypatch.setenv('PATH', str(tmp_path / 'empty'))

    # WHEN / THEN
    with pytest.raises(AudiverisNotFoundError):
        convert_score(str(SCORE_PDF), output_path, dpi=FAST_DPI)
    assert not output_path.exists()


def test_convert_score_reports_audiveris_failures(
    audiveris: FakeAudiveris, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # GIVEN
    output_path = tmp_path / 'score.musicxml'
    audiveris.failing_pages = (1, 2, 3, 4)

    # WHEN / THEN
    with pytest.raises(RuntimeError, match='Audiveris failed for pages: 1, 2, 3, 4'):
        convert_score(str(SCORE_PDF), output_path, dpi=FAST_DPI)
    assert 'Error in reaching step PAGE' in caplog.text
    assert not output_path.exists()


def test_convert_score_merges_the_pages_that_succeed(
    audiveris: FakeAudiveris, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # GIVEN
    output_path = tmp_path / 'score.musicxml'
    audiveris.failing_pages = (2,)

    # WHEN
    failed_pages = convert_score(str(SCORE_PDF), output_path, dpi=FAST_DPI)

    # THEN
    assert _measures_per_part(output_path) == {'P1': 18, 'P2': 18}
    assert failed_pages == [2]
    assert 'Page 2 failed: Audiveris log tail:' in caplog.text


def test_convert_score_leaves_out_pages_that_time_out(
    audiveris: FakeAudiveris, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # GIVEN
    output_path = tmp_path / 'score.musicxml'
    audiveris.timing_out_pages = (3,)

    # WHEN
    failed_pages = convert_score(str(SCORE_PDF), output_path, dpi=FAST_DPI, timeout=10)

    # THEN
    assert _measures_per_part(output_path) == {'P1': 18, 'P2': 18}
    assert failed_pages == [3]
    assert 'Page 3 failed: Audiveris timed out after 10 seconds' in caplog.text


def _measures_per_part(output_path: Path) -> dict[str | None, int]:
    root = etree.fromstring(output_path.read_bytes())
    return {part.get('id'): len(part.findall('measure')) for part in root.findall('part')}


@pytest.fixture
def audiveris(monkeypatch: pytest.MonkeyPatch) -> FakeAudiveris:
    fake = FakeAudiveris()

    def which(name: str) -> str:
        return f'/usr/bin/{name}'

    monkeypatch.setattr('page_break.audiveris.shutil.which', which)
    monkeypatch.setattr('page_break.audiveris.subprocess.run', fake)
    return fake
