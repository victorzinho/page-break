# Convert one score, e.g. `just convert score.pdf score.musicxml --dpi 450`
convert *args:
    uv run --locked page-break convert {{args}}

check:
    uv run --locked ruff check
    uv run --locked basedpyright
    uv run --locked pytest --cov
