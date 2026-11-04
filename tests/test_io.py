from collections.abc import Iterator
from pathlib import Path

import pytest
import requests

from page_break.io import prepare_input_source

SCORE_URL = 'https://imslp.org/files/score.php?id=1'
SCORE_PDF = Path(__file__).parent / 'resources' / 'pdf' / 'le_cygne.pdf'


def test_prepare_input_source_downloads_a_url_as_pdf(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # GIVEN
    pdf_bytes = SCORE_PDF.read_bytes()
    get = FakeGet(FakeResponse([pdf_bytes[:1000], b'', pdf_bytes[1000:]]))
    monkeypatch.setattr('page_break.io.requests.get', get)

    # WHEN
    downloaded = prepare_input_source(SCORE_URL, tmp_path / 'downloads', timeout=5)

    # THEN
    assert get.calls == [(SCORE_URL, {'stream': True, 'timeout': 5})]
    assert downloaded.parent == tmp_path / 'downloads'
    assert downloaded.suffix == '.pdf'
    assert downloaded.read_bytes() == pdf_bytes


def test_prepare_input_source_raises_on_http_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # GIVEN
    monkeypatch.setattr('page_break.io.requests.get', FakeGet(FakeResponse([], status_code=404)))

    # WHEN / THEN
    with pytest.raises(requests.HTTPError, match='404'):
        prepare_input_source(SCORE_URL, tmp_path / 'downloads')
    assert not list((tmp_path / 'downloads').iterdir())


class FakeResponse:
    """Stands in for a streamed `requests` response."""

    def __init__(self, chunks: list[bytes], status_code: int = 200) -> None:
        self.chunks = chunks
        self.status_code = status_code

    def __enter__(self) -> 'FakeResponse':
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f'{self.status_code} Client Error')

    def iter_content(self, chunk_size: int) -> Iterator[bytes]:
        return iter(self.chunks)


class FakeGet:
    """Stands in for `requests.get`, recording its calls."""

    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object]]] = []

    def __call__(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append((url, kwargs))
        return self.response
