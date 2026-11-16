import '~/.config/bosun/recipes/python-uv.just'

# Open the GUI in the browser
start:
    uv run --locked page-break gui

# Convert one score, e.g. `just convert score.pdf score.musicxml --dpi 450`
convert *args:
    uv run --locked page-break convert {{args}}
