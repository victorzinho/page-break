import argparse
import logging
import sys
from pathlib import Path

from page_break.audiveris import AudiverisOptions, Binarization
from page_break.pipeline import convert_score

LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
LOG_FORMAT = '%(levelname)s %(name)s: %(message)s'

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=args.log_level, format=LOG_FORMAT)
    try:
        failed_page_numbers = convert_score(
            input_source=args.input_source,
            output_path=args.output_path,
            working_dir=args.working_dir,
            options=AudiverisOptions(binarization=args.binarization, threshold=args.threshold),
            dpi=args.dpi,
            timeout=args.timeout,
            jobs=max(1, args.jobs),
            keep_temp=args.keep_temp,
        )
    except (OSError, ValueError, RuntimeError) as error:  # OSError covers requests' errors too
        logger.debug('Conversion failed', exc_info=True)
        print(f'page-break: error: {error}', file=sys.stderr)
        return 1

    if failed_page_numbers:
        failed_pages_text = ', '.join(str(page_number) for page_number in failed_page_numbers)
        print(f'Wrote {args.output_path} without page(s) {failed_pages_text}: Audiveris failed on them.')
    else:
        print(f'Wrote {args.output_path}')
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog='page-break', description='Convert score PDFs and images into MusicXML.')
    commands = parser.add_subparsers(dest='command', required=True)

    convert = commands.add_parser('convert', help='Convert one score')
    convert.add_argument('input_source', help='Local file path or direct URL')
    convert.add_argument('output_path', type=Path, help='Destination .musicxml path')
    convert.add_argument('--dpi', type=int, default=300, help='Render DPI for PDF inputs')
    convert.add_argument(
        '--binarization', type=Binarization, choices=list(Binarization),
        help="How Audiveris separates ink from paper (default: Audiveris's own)",
    )
    convert.add_argument('--threshold', type=int, help='Gray level threshold for global binarization')
    convert.add_argument('--timeout', type=int, default=300, help='Per-page Audiveris timeout in seconds')
    convert.add_argument('--jobs', type=int, default=2, help='Number of pages to process in parallel')
    convert.add_argument('--working-dir', type=Path, help='Directory for intermediate files')
    convert.add_argument('--keep-temp', action='store_true', help='Keep intermediate files')
    convert.add_argument(
        '--log-level', type=str.upper, choices=LOG_LEVELS, default='INFO',
        help='Logging level; DEBUG also prints the traceback of a failure',
    )

    args = parser.parse_args(argv)
    if args.threshold is not None and args.binarization != Binarization.GLOBAL:
        parser.error('--threshold needs --binarization global')
    return args
