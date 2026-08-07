from PIL import Image, ImageDraw, ImageFont

from .models import BeadPalette, PatternGrid


def render_effect_preview(
    grid: PatternGrid, *, palette: BeadPalette, bead_pixels: int = 12
) -> Image.Image:
    if bead_pixels <= 0:
        raise ValueError("bead_pixels must be positive")

    colors = palette.by_code
    canvas = Image.new(
        "RGBA", (grid.width * bead_pixels, grid.height * bead_pixels), (255, 255, 255, 0)
    )
    draw = ImageDraw.Draw(canvas)
    inset = max(1, bead_pixels // 10)

    for y, row in enumerate(grid.cells):
        for x, code in enumerate(row):
            if code is None:
                continue
            red, green, blue = colors[code].rgb
            left = x * bead_pixels + inset
            top = y * bead_pixels + inset
            right = (x + 1) * bead_pixels - inset - 1
            bottom = (y + 1) * bead_pixels - inset - 1
            draw.ellipse((left, top, right, bottom), fill=(red, green, blue, 255))

    return canvas


def _text_color(rgb: tuple[int, int, int]) -> tuple[int, int, int, int]:
    red, green, blue = rgb
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return (25, 25, 25, 255) if luminance > 145 else (255, 255, 255, 255)


def render_grid_preview(
    grid: PatternGrid, *, palette: BeadPalette, cell_pixels: int = 28
) -> Image.Image:
    if cell_pixels < 12:
        raise ValueError("cell_pixels must be at least 12")

    colors = palette.by_code
    width = grid.width * cell_pixels + 1
    height = grid.height * cell_pixels + 1
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=max(8, cell_pixels // 4))

    for y, row in enumerate(grid.cells):
        for x, code in enumerate(row):
            left = x * cell_pixels
            top = y * cell_pixels
            right = left + cell_pixels
            bottom = top + cell_pixels
            if code is None:
                fill = (255, 255, 255, 255)
                text = ""
                text_fill = (25, 25, 25, 255)
            else:
                rgb = colors[code].rgb
                fill = (*rgb, 255)
                text = code.removeprefix("WPD-")
                text_fill = _text_color(rgb)
            draw.rectangle((left, top, right, bottom), fill=fill, outline=(90, 90, 90, 255))
            if text:
                draw.text(
                    ((left + right) / 2, (top + bottom) / 2),
                    text,
                    fill=text_fill,
                    font=font,
                    anchor="mm",
                )

    return canvas
