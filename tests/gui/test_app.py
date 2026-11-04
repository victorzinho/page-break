from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from page_break.audiveris import AudiverisNotFoundError
from page_break.cli import GUI_APP_PATH

SCORE_URL = 'https://example.com/scores/le_cygne.pdf'
SCORE_PDF = Path(__file__).parent.parent / 'resources' / 'pdf' / 'le_cygne.pdf'


class FakeConvertScore:
    """Stands in for `convert_score`: writes a score and returns `outcome` as the left-out pages, or raises it."""

    def __init__(self) -> None:
        self.outcome: list[int] | Exception = []
        self.input_sources: list[str] = []

    def __call__(self, *, input_source: str, output_path: Path, **_: object) -> list[int]:
        self.input_sources.append(input_source)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        output_path.write_text('<score-partwise/>', encoding='utf-8')
        return self.outcome


def test_app_converts_a_url(convert_score: FakeConvertScore) -> None:
    # GIVEN
    app = _app_with_url()

    # WHEN
    _convert(app)

    # THEN
    assert convert_score.input_sources == [SCORE_URL]
    assert app.success[0].value == 'Conversion complete'
    assert app.download_button[0].proto.label == 'Download MusicXML'


def test_app_converts_an_uploaded_file(convert_score: FakeConvertScore) -> None:
    # GIVEN
    app = AppTest.from_file(str(GUI_APP_PATH)).run()
    app.file_uploader[0].set_value(('le_cygne.pdf', SCORE_PDF.read_bytes(), 'application/pdf')).run()

    # WHEN
    _convert(app)

    # THEN
    [input_source] = convert_score.input_sources
    assert Path(input_source).name == 'le_cygne.pdf'
    assert app.success[0].value == 'Conversion complete'


def test_app_warns_about_left_out_pages(convert_score: FakeConvertScore) -> None:
    # GIVEN
    convert_score.outcome = [2]
    app = _app_with_url()

    # WHEN
    _convert(app)

    # THEN
    assert app.warning[0].value == (
        'Conversion complete with failures:\n- Audiveris failed on page(s) 2, which are left out of the score'
    )
    assert app.download_button[0].proto.label == 'Download MusicXML'


def test_app_explains_how_to_install_missing_audiveris(convert_score: FakeConvertScore) -> None:
    # GIVEN
    convert_score.outcome = AudiverisNotFoundError()
    app = _app_with_url()

    # WHEN
    _convert(app)

    # THEN
    assert app.error[0].value == str(AudiverisNotFoundError())


def test_app_shows_conversion_failures_with_a_hint(convert_score: FakeConvertScore) -> None:
    # GIVEN
    convert_score.outcome = RuntimeError('Audiveris failed for pages: 1, 2')
    app = _app_with_url()

    # WHEN
    _convert(app)

    # THEN
    assert app.error[0].value.startswith('Conversion failed: Audiveris failed for pages: 1, 2\n\nTry other values')
    assert not app.download_button


def test_app_keeps_a_typed_output_name_when_the_input_changes(convert_score: FakeConvertScore) -> None:
    # GIVEN
    app = _app_with_url()
    app.text_input[1].set_value('mine').run()

    # WHEN
    app.text_input[0].set_value('https://example.com/scores/other.pdf').run()

    # THEN
    assert app.text_input[1].value == 'mine'
    assert app.text_input[1].placeholder == 'other.musicxml'


@pytest.fixture
def convert_score(monkeypatch: pytest.MonkeyPatch) -> FakeConvertScore:
    fake = FakeConvertScore()
    monkeypatch.setattr('page_break.gui.conversion.convert_score', fake)
    return fake


def _app_with_url() -> AppTest:
    app = AppTest.from_file(str(GUI_APP_PATH)).run()
    app.radio[0].set_value('Direct PDF URL').run()
    app.text_input[0].set_value(SCORE_URL).run()
    return app


def _convert(app: AppTest) -> AppTest:
    return app.button[0].click().run()
