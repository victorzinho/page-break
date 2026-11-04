import logging
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path

from page_break.audiveris import AudiverisOptions, max_pixels_for_dpi, run_audiveris_batch
from page_break.io import prepare_input_source, write_text_file
from page_break.musicxml import merge_mxl_files
from page_break.pages import convert_input_to_pngs, get_blank_page_numbers

logger = logging.getLogger(__name__)


def convert_score(
    input_source: str,
    output_path: Path,
    working_dir: Path | None = None,
    options: AudiverisOptions | None = None,
    dpi: int = 300,
    timeout: int = 300,
    jobs: int = 2,
    keep_temp: bool = False,
) -> list[int]:
    """Converts a score PDF or image, from a path or URL, into one MusicXML file at `output_path`.

    Pages Audiveris fails on are left out of the score.

    Returns:
        The numbers of the pages left out.

    Raises:
        RuntimeError: No page could be converted.
    """
    options = replace(options or AudiverisOptions(), max_pixels=max_pixels_for_dpi(dpi))
    cleanup_dir = False
    if working_dir is None:
        working_dir = Path(tempfile.mkdtemp(prefix='page-break-'))
        cleanup_dir = not keep_temp
    else:
        working_dir.mkdir(parents=True, exist_ok=True)

    downloads_dir = working_dir / 'downloads'
    images_dir = working_dir / 'images'
    audiveris_dir = working_dir / 'audiveris'

    try:
        prepared_input = prepare_input_source(input_source, downloads_dir)
        image_paths = convert_input_to_pngs(prepared_input, images_dir, dpi=dpi)
        blank_page_numbers = get_blank_page_numbers(image_paths)
        for page_number in blank_page_numbers:
            logger.warning('Page %s skipped by pre-check as blank', page_number)

        page_inputs = [
            (page_number, image_path)
            for page_number, image_path in enumerate(image_paths, start=1)
            if page_number not in blank_page_numbers
        ]
        results = run_audiveris_batch(
            pages=page_inputs,
            output_dir=audiveris_dir,
            options=options,
            timeout=timeout,
            jobs=jobs,
        )

        failed_pages: list[int] = []
        mxl_paths: list[Path] = []
        for result in results:
            if result.succeeded and result.output_mxl_path is not None:
                logger.info('Page %s converted: %s', result.page_number, result.output_mxl_path)
                mxl_paths.append(result.output_mxl_path)
            else:
                logger.error(
                    'Page %s failed: %s', result.page_number, result.stderr or result.stdout or 'unknown error'
                )
                failed_pages.append(result.page_number)

        if not mxl_paths:
            if failed_pages:
                failed_pages_text = ', '.join(str(page_number) for page_number in failed_pages)
                raise RuntimeError(f'Audiveris failed for pages: {failed_pages_text}')
            raise RuntimeError('Audiveris did not generate any MusicXML output')

        write_text_file(output_path, merge_mxl_files(mxl_paths))
        return failed_pages
    finally:
        if cleanup_dir and working_dir.exists():
            shutil.rmtree(working_dir)

