import shutil
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

PDF_POINTS_PER_INCH = 72
SUPPORTED_IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.webp'}
DEFAULT_BLANK_PIXEL_THRESHOLD = 245
DEFAULT_BLANK_RATIO_THRESHOLD = 0.001


def convert_input_to_pngs(input_path: Path, output_dir: Path, dpi: int = 300) -> list[Path]:
    """Writes the input's pages as `page-NNN.png` files.

    Args:
        input_path: A PDF, or a single-page image with one of `SUPPORTED_IMAGE_SUFFIXES`.
        output_dir: Where the PNGs go; created if missing.
        dpi: Resolution PDF pages are rendered at. Images are kept as they are.

    Returns:
        The PNGs, in page order.

    Raises:
        ValueError: The file type is unsupported, the PDF isn't readable, or it has no pages.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = input_path.suffix.lower()
    if suffix == '.pdf':
        return _render_pdf_pages(input_path, output_dir, dpi)
    if suffix in SUPPORTED_IMAGE_SUFFIXES:
        return [_copy_image_to_png(input_path, output_dir)]
    raise ValueError(f'Unsupported input type: {input_path.suffix or input_path.name}')


def get_blank_page_numbers(
    image_paths: list[Path],
    pixel_threshold: int = DEFAULT_BLANK_PIXEL_THRESHOLD,
    blank_ratio_threshold: float = DEFAULT_BLANK_RATIO_THRESHOLD,
) -> list[int]:
    """Drops pages with almost no ink.

    Args:
        image_paths: The pages, in order.
        pixel_threshold: Gray level (0-255) below which a pixel counts as ink.
        blank_ratio_threshold: Fraction of ink pixels below which a page is blank.

    Returns:
        The 1-based numbers of the dropped pages.
    """
    return [
        page_number for page_number, image_path in enumerate(image_paths, start=1)
        if _is_blank_image(image_path, pixel_threshold=pixel_threshold, blank_ratio_threshold=blank_ratio_threshold)
    ]


def _is_blank_image(
    image_path: Path,
    pixel_threshold: int = DEFAULT_BLANK_PIXEL_THRESHOLD,
    blank_ratio_threshold: float = DEFAULT_BLANK_RATIO_THRESHOLD,
) -> bool:
    with Image.open(image_path) as image:
        grayscale_image = image.convert('L')
        histogram = grayscale_image.histogram()
        total_pixels = grayscale_image.size[0] * grayscale_image.size[1]

    dark_pixels = sum(histogram[:pixel_threshold])
    dark_ratio = dark_pixels / total_pixels
    return dark_ratio < blank_ratio_threshold


def _render_pdf_pages(pdf_path: Path, output_dir: Path, dpi: int) -> list[Path]:
    try:
        pdf = pdfium.PdfDocument(pdf_path)
    except pdfium.PdfiumError as error:
        raise ValueError(f'Not a readable PDF: {pdf_path}') from error

    image_paths: list[Path] = []
    try:
        for index in range(len(pdf)):
            output_path = output_dir / f'page-{index + 1:03d}.png'
            pdf[index].render(scale=dpi / PDF_POINTS_PER_INCH).to_pil().save(output_path, 'PNG')
            image_paths.append(output_path)
    finally:
        pdf.close()

    if not image_paths:
        raise ValueError(f'No pages were rendered from PDF: {pdf_path}')
    return image_paths


def _copy_image_to_png(input_path: Path, output_dir: Path) -> Path:
    output_path = output_dir / 'page-001.png'
    if input_path.suffix.lower() == '.png':
        shutil.copy2(input_path, output_path)
    else:
        with Image.open(input_path) as image:
            image.save(output_path, 'PNG')
    return output_path
