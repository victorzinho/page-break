import logging
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


def prepare_input_source(input_source: str, temp_dir: Path, timeout: int = 60) -> Path:
    if _is_url(input_source):
        return _download_file(input_source, temp_dir, timeout=timeout)

    input_path = Path(input_source).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f'Input file not found: {input_path}')
    if not input_path.is_file():
        raise ValueError(f'Input path is not a file: {input_path}')
    return input_path


def write_text_file(output_path: Path, content: str) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding='utf-8')
    return output_path


def _is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def _download_file(url: str, destination_dir: Path, timeout: int = 60) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)

    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with tempfile.NamedTemporaryFile(
            dir=destination_dir,
            suffix='.pdf',
            delete=False,
        ) as temp_file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                temp_file.write(chunk)
            return Path(temp_file.name)
