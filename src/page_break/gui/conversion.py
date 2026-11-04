import io
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZipFile

from page_break.audiveris import AudiverisNotFoundError, AudiverisOptions, Binarization
from page_break.pipeline import convert_score

FAILURE_REPORT_NAME = 'failures.txt'


@dataclass(frozen=True, slots=True)
class ScoreInput:
    """A URL, or an uploaded file's name and bytes."""

    url: str = ''
    file_name: str = ''
    data: bytes | None = None

    @property
    def stem(self) -> str:
        return Path(self.file_name or urlparse(self.url).path).stem or 'score'


@dataclass(frozen=True, slots=True)
class ConversionCase:
    dpi: int
    binarization: Binarization
    threshold: int | None

    @property
    def suffix(self) -> str:
        if self.binarization == Binarization.ADAPTIVE:
            return f'dpi{self.dpi}-adaptive'
        return f'dpi{self.dpi}-global{self.threshold}'


@dataclass(frozen=True, slots=True)
class ConversionResult:
    """The file to download: the MusicXML for a single case, else a ZIP of every case's output."""

    file_name: str
    data: bytes
    n_cases: int
    failures: list[str] = field(default_factory=list[str])
    all_failed: bool = False

    @property
    def is_zip(self) -> bool:
        return self.n_cases > 1

    @property
    def mime(self) -> str:
        return 'application/zip' if self.is_zip else 'application/vnd.recordare.musicxml+xml'


def build_cases(dpis: list[int], binarization: Binarization, thresholds: list[int]) -> list[ConversionCase]:
    case_thresholds: list[int | None] = [*sorted(set(thresholds))] if binarization == Binarization.GLOBAL else [None]
    return [ConversionCase(dpi, binarization, threshold) for dpi in sorted(set(dpis)) for threshold in case_thresholds]


def convert(
    score: ScoreInput, requested_output_name: str, cases: list[ConversionCase], jobs: int, timeout: int,
) -> ConversionResult:
    """Runs every case. A single case raises its failure; with several, failed cases are reported in the ZIP."""
    stem = requested_output_name.strip().removesuffix('.musicxml') or score.stem
    with tempfile.TemporaryDirectory(prefix='page-break-gui-') as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        if score.data is None:
            input_source = score.url
        else:
            upload_path = temp_dir / Path(score.file_name).name
            upload_path.write_bytes(score.data)
            input_source = str(upload_path)

        def run(case: ConversionCase, output_path: Path) -> list[int]:
            return convert_score(
                input_source=input_source,
                output_path=output_path,
                working_dir=temp_dir / 'work' / case.suffix,
                options=AudiverisOptions(binarization=case.binarization, threshold=case.threshold),
                dpi=case.dpi,
                jobs=jobs,
                timeout=timeout,
            )

        if len(cases) == 1:
            output_path = temp_dir / f'{stem}.musicxml'
            failed_page_numbers = run(cases[0], output_path)
            return ConversionResult(
                output_path.name,
                output_path.read_bytes(),
                n_cases=1,
                failures=[_left_out_message(failed_page_numbers)] if failed_page_numbers else [],
            )

        failures: list[str] = []
        n_failed_cases = 0
        buffer = io.BytesIO()
        with ZipFile(buffer, 'w') as archive:
            for case in cases:
                output_path = temp_dir / f'{stem}-{case.suffix}.musicxml'
                try:
                    failed_page_numbers = run(case, output_path)
                except AudiverisNotFoundError:
                    raise
                except Exception as error:
                    failures.append(f'{case.suffix}: {error}')
                    n_failed_cases += 1
                    continue
                archive.write(output_path, arcname=output_path.name)
                if failed_page_numbers:
                    failures.append(f'{case.suffix}: {_left_out_message(failed_page_numbers)}')
            if failures:
                archive.writestr(FAILURE_REPORT_NAME, '\n'.join(failures) + '\n')
        return ConversionResult(
            f'{stem}.zip',
            buffer.getvalue(),
            n_cases=len(cases),
            failures=failures,
            all_failed=n_failed_cases == len(cases),
        )


def _left_out_message(failed_page_numbers: list[int]) -> str:
    return f"Audiveris failed on page(s) {', '.join(map(str, failed_page_numbers))}, which are left out of the score"
