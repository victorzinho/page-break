"""Runs Audiveris on page images, one process per page."""

import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

HIGH_DPI = 600
HIGH_DPI_MAX_PIXELS = 40_000_000
LOG_TAIL_LINES = 300


class AudiverisNotFoundError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            'Audiveris not found on the PATH. Install it from https://github.com/Audiveris/audiveris/releases '
            'and add the folder holding its Audiveris executable to the PATH.'
        )


class Binarization(StrEnum):
    ADAPTIVE = 'adaptive'
    GLOBAL = 'global'


@dataclass(frozen=True, slots=True)
class AudiverisOptions:
    binarization: Binarization | None = None
    threshold: int | None = None  # gray level separating ink from paper, for global binarization
    max_pixels: int | None = None  # largest page image Audiveris accepts, in pixels

    def constants(self) -> list[str]:
        """The `-constant name=value` arguments for the settings that aren't `None`."""
        constants: list[str] = []
        if self.max_pixels is not None:
            constants += ['-constant', f'org.audiveris.omr.step.LoadStep.maxPixelCount={self.max_pixels}']
        if self.binarization is not None:
            constants += ['-constant', f'org.audiveris.omr.image.FilterDescriptor.defaultKind={self.binarization.name}']
        if self.threshold is not None:
            constants += ['-constant', f'org.audiveris.omr.image.GlobalDescriptor.defaultThreshold={self.threshold}']
        return constants


@dataclass(frozen=True, slots=True)
class AudiverisPageResult:
    page_number: int
    input_image_path: Path
    output_mxl_path: Path | None
    stdout: str = ''
    stderr: str = ''

    @property
    def succeeded(self) -> bool:
        return self.output_mxl_path is not None


def max_pixels_for_dpi(dpi: int) -> int | None:
    """The `max_pixels` a page rendered at `dpi` needs, or `None` if Audiveris's default suffices."""
    return HIGH_DPI_MAX_PIXELS if dpi >= HIGH_DPI else None


def run_audiveris_batch(
    pages: list[tuple[int, Path]],
    output_dir: Path,
    options: AudiverisOptions,
    timeout: int = 300,
    jobs: int = 1,
) -> list[AudiverisPageResult]:
    """Transcribes and exports each page to MusicXML.

    Args:
        pages: Page numbers and their images.
        output_dir: Where each page's output goes, in a `page-NNN` subfolder.
        options: Settings passed to Audiveris.
        timeout: Seconds allowed per page.
        jobs: Pages run at the same time.

    Returns:
        One result per page, in the order of `pages`.

    Raises:
        AudiverisNotFoundError: Audiveris isn't on the PATH.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [_find_audiveris(), *options.constants(), '-batch', '-transcribe', '-export']

    def run_page(page: tuple[int, Path]) -> AudiverisPageResult:
        page_number, image_path = page
        return _run_audiveris_page(page_number, image_path, output_dir / f'page-{page_number:03d}', command, timeout)

    with ThreadPoolExecutor(max_workers=max(1, min(jobs, len(pages)))) as executor:
        return list(executor.map(run_page, pages))


def _find_audiveris() -> str:
    for name in ('audiveris', 'Audiveris'):
        if found := shutil.which(name):
            return found
    raise AudiverisNotFoundError()


def _run_audiveris_page(
    page_number: int, image_path: Path, page_output_dir: Path, command: list[str], timeout: int
) -> AudiverisPageResult:
    page_output_dir.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            [*command, '-output', str(page_output_dir), str(image_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        stderr = _with_log_tail(f'Audiveris timed out after {timeout} seconds', page_output_dir)
        return AudiverisPageResult(page_number, image_path, output_mxl_path=None, stderr=stderr)

    if completed.returncode == 0:
        return AudiverisPageResult(
            page_number=page_number,
            input_image_path=image_path,
            output_mxl_path=_find_output(page_output_dir),
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    stderr = _with_log_tail(completed.stderr, page_output_dir)
    return AudiverisPageResult(
        page_number=page_number,
        input_image_path=image_path,
        output_mxl_path=None,
        stdout=completed.stdout,
        stderr=stderr,
    )


def _find_output(page_output_dir: Path) -> Path | None:
    for pattern in ('*.mxl', '*.musicxml', '*.xml'):
        if matches := sorted(page_output_dir.rglob(pattern)):
            return matches[0]
    return None


def _with_log_tail(stderr: str, page_output_dir: Path) -> str:
    """Appends the last lines of Audiveris's log, which usually holds the failure's cause."""
    log_paths = sorted(page_output_dir.glob('*.log'))
    if not log_paths:
        return stderr

    log_lines = log_paths[-1].read_text(encoding='utf-8', errors='replace').splitlines()
    if not log_lines:
        return stderr

    log_tail = 'Audiveris log tail:\n' + '\n'.join(log_lines[-LOG_TAIL_LINES:])
    if not stderr.strip():
        return log_tail
    return f'{stderr.rstrip()}\n\n{log_tail}'
