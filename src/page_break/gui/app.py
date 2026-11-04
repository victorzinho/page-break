import logging
from collections.abc import Generator
from contextlib import contextmanager
from io import StringIO

import streamlit as st

from page_break.audiveris import AudiverisNotFoundError, Binarization
from page_break.gui.conversion import (
    ConversionCase,
    ConversionResult,
    ScoreInput,
    build_cases,
    convert,
)
from page_break.pages import SUPPORTED_IMAGE_SUFFIXES

UPLOAD_TYPES = ['pdf', *sorted(suffix.lstrip('.') for suffix in SUPPORTED_IMAGE_SUFFIXES)]
DPI_OPTIONS = [300, 400, 450, 600]
THRESHOLD_OPTIONS = [160, 180, 200, 225]
DPI_HELP = 'Resolution PDF pages are rendered at. 450 suits most scores; try 400 if recognition struggles.'
BINARIZATION_HELP = (
    'How Audiveris separates ink from paper: global uses one gray threshold for the whole page; '
    'adaptive adjusts across the page, for uneven lighting such as phone photos.'
)
THRESHOLD_HELP = 'Pixels darker than this count as ink. Lower it for gray backgrounds, raise it for faint print.'
URL_HELP = 'Only PDFs can be loaded from a URL. For an image, download it and upload the file instead.'
JOBS_HELP = 'Pages recognized at the same time. Lower it if the machine runs out of memory.'
FAILURE_HINT = 'Try other values in **Conversion options**. The logs below hold the cause Audiveris reported.'
LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s %(message)s'


def main() -> None:
    st.set_page_config(page_title='Page Break', layout='centered')
    st.title('Page Break')
    st.caption('Convert score PDFs and images into MusicXML.')

    score = _input_section()
    requested_output_name = st.text_input(
        'Output file name',
        placeholder=f'{score.stem}.musicxml' if score else '',
        # Keyed so that a changing placeholder doesn't reset a typed name.
        key='output_name',
    )
    cases = _options_section()
    logs_placeholder = st.empty()
    with st.expander('Troubleshooting'):
        jobs = int(st.number_input('Parallel jobs', min_value=1, max_value=16, value=4, step=1, help=JOBS_HELP))
        timeout = int(st.number_input('Per-page timeout (seconds)', min_value=30, max_value=1800, value=300, step=30))
        log_level = st.selectbox('Log level', ['INFO', 'WARNING', 'DEBUG'], index=0)

    if st.button('Convert', type='primary', disabled=score is None or not cases) and score:
        log_stream = StringIO()
        with _captured_logs(log_stream, log_level):
            try:
                with st.spinner('Converting score...'):
                    result = convert(score, requested_output_name, cases, jobs, timeout)
            except AudiverisNotFoundError as error:
                st.error(str(error))
            except Exception as error:
                st.error(f'Conversion failed: {error}\n\n{FAILURE_HINT}')
            else:
                _result_section(result)

        if log_output := log_stream.getvalue().strip():
            with logs_placeholder.container():
                st.caption('Logs')
                st.code(log_output, language='text')


def _input_section() -> ScoreInput | None:
    input_mode = st.radio('Input source', ['Upload a file', 'Direct PDF URL'], horizontal=True)
    if input_mode == 'Upload a file':
        uploaded_file = st.file_uploader('Choose a PDF or image', type=UPLOAD_TYPES)
        return ScoreInput(file_name=uploaded_file.name, data=uploaded_file.getvalue()) if uploaded_file else None
    url = st.text_input('PDF URL', placeholder='https://example.com/score.pdf', help=URL_HELP).strip()
    return ScoreInput(url=url) if url else None


def _options_section() -> list[ConversionCase]:
    """The selected combinations; empty, with a warning shown, if a setting has nothing selected."""
    with st.expander('Conversion options'):
        st.caption(
            'The defaults suit clean printed scores. Selecting several values runs every combination and returns '
            'a ZIP to compare them; failed combinations are listed in its failures.txt.'
        )
        st.markdown('**Render DPI**', help=DPI_HELP)
        dpis = _checkbox_row(DPI_OPTIONS, default=450)
        binarization = st.segmented_control(
            'Binarization', list(Binarization), default=Binarization.GLOBAL, required=True, help=BINARIZATION_HELP
        )
        assert binarization is not None
        st.markdown('**Global threshold values**', help=THRESHOLD_HELP)
        thresholds = _checkbox_row(THRESHOLD_OPTIONS, default=180, disabled=binarization != Binarization.GLOBAL)

    if not dpis:
        st.warning('Select at least one DPI option.')
        return []
    if binarization == Binarization.GLOBAL and not thresholds:
        st.warning('Select at least one global threshold option.')
        return []
    return build_cases(dpis, binarization, thresholds)


def _checkbox_row(values: list[int], default: int, disabled: bool = False) -> list[int]:
    columns = st.columns(len(values))
    return [
        value
        for column, value in zip(columns, values, strict=True)
        if column.checkbox(str(value), value=value == default, disabled=disabled)
    ]


def _result_section(result: ConversionResult) -> None:
    if result.all_failed:
        st.error('All selected combinations failed.')
    elif result.failures:
        st.warning('\n'.join(['Conversion complete with failures:', *(f'- {failure}' for failure in result.failures)]))
    else:
        st.success('Conversion complete')
    st.download_button(
        label='Download ZIP' if result.is_zip else 'Download MusicXML',
        data=result.data,
        file_name=result.file_name,
        mime=result.mime,
    )


@contextmanager
def _captured_logs(stream: StringIO, level: str) -> Generator[None]:
    """Sends root logging to `stream` at `level` while active."""
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger = logging.getLogger()
    original_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level, logging.INFO))
    try:
        yield
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)


if __name__ == '__main__':
    main()
