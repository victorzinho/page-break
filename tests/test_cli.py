from pathlib import Path

import pytest

from page_break import cli
from page_break.audiveris import AudiverisOptions, Binarization


def test_convert_passes_options_to_the_pipeline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # GIVEN
    calls: list[dict[str, object]] = []
    def fake_convert_score(**kwargs: object) -> list[int]:
        calls.append(kwargs)
        return []

    monkeypatch.setattr('page_break.cli.convert_score', fake_convert_score)

    # WHEN
    exit_code = cli.main(
        ['convert', 'score.pdf', str(tmp_path / 'out.musicxml'), '--binarization', 'global', '--threshold', '180']
        + ['--dpi', '450', '--jobs', '0']
    )

    # THEN
    assert exit_code == 0
    assert calls == [{
            'input_source': 'score.pdf',
            'output_path': tmp_path / 'out.musicxml',
            'working_dir': None,
            'options': AudiverisOptions(binarization=Binarization.GLOBAL, threshold=180),
            'dpi': 450,
            'timeout': 300,
            'jobs': 1,
            'keep_temp': False,
    }]
    assert capsys.readouterr().out == f'Wrote {tmp_path / "out.musicxml"}\n'


def test_convert_summarizes_left_out_pages(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # GIVEN
    def fake_convert_score(**_: object) -> list[int]:
        return [2, 3]

    monkeypatch.setattr('page_break.cli.convert_score', fake_convert_score)

    # WHEN
    exit_code = cli.main(['convert', 'score.pdf', 'out.musicxml'])

    # THEN
    assert exit_code == 0
    assert capsys.readouterr().out == 'Wrote out.musicxml without page(s) 2, 3: Audiveris failed on them.\n'


def test_convert_rejects_threshold_without_global_binarization(capsys: pytest.CaptureFixture[str]) -> None:
    # WHEN
    with pytest.raises(SystemExit):
        cli.main(['convert', 'score.pdf', 'out.musicxml', '--threshold', '180'])

    # THEN
    assert '--threshold needs --binarization global' in capsys.readouterr().err


def test_gui_runs_streamlit_on_the_bundled_app(monkeypatch: pytest.MonkeyPatch) -> None:
    # GIVEN
    commands: list[list[str]] = []
    def fake_call(command: list[str]) -> int:
        commands.append(command)
        return 0

    monkeypatch.setattr('page_break.cli.subprocess.call', fake_call)

    # WHEN
    exit_code = cli.main(['gui', '--port', '9000'])

    # THEN
    assert exit_code == 0
    assert commands[0][1:5] == ['-m', 'streamlit', 'run', str(cli.GUI_APP_PATH)]
    assert commands[0][5:7] == ['--server.port', '9000']
    assert cli.GUI_APP_PATH.is_file()
