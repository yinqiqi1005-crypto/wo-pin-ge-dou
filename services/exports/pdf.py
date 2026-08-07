import os
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from services.image_processing.palette import DEFAULT_PALETTE

FONT_NAME = "WPD-CJK"


def _register_cjk_font():
    if FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return FONT_NAME, True
    candidates = [
        os.getenv("PDF_CJK_FONT_PATH", ""),
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            try:
                pdfmetrics.registerFont(TTFont(FONT_NAME, candidate, subfontIndex=0))
                return FONT_NAME, True
            except Exception:
                continue
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    return "STSong-Light", False


def _draw_header(pdf, font_name, title, subtitle):
    pdf.setFont(font_name, 15)
    pdf.drawString(36, A4[1] - 38, title)
    pdf.setFont(font_name, 9)
    pdf.setFillColor(colors.HexColor("#756b62"))
    pdf.drawRightString(A4[0] - 36, A4[1] - 36, subtitle)
    pdf.setFillColor(colors.black)


def _grid_pages(pdf, version, font_name):
    cells = version.grid_data["cells"]
    palette = {color.code: color.rgb for color in DEFAULT_PALETTE.colors}
    page_size = 35
    total = len(cells)
    pages = 0
    for start_y in range(0, total, page_size):
        for start_x in range(0, total, page_size):
            pages += 1
            _draw_header(
                pdf,
                font_name,
                f"{version.pattern.title} · 网格 v{version.version_number}",
                (
                    f"行 {start_y + 1}-{min(start_y + page_size, total)} / "
                    f"列 {start_x + 1}-{min(start_x + page_size, total)}"
                ),
            )
            available = min(page_size, total - start_x, total - start_y)
            cell_size = min(14.5, 500 / max(available, 1))
            origin_x = 48
            origin_y = A4[1] - 78
            pdf.setFont("Helvetica", max(4, min(6, cell_size * 0.42)))
            for local_y, row in enumerate(cells[start_y : start_y + page_size]):
                for local_x, code in enumerate(row[start_x : start_x + page_size]):
                    x = origin_x + local_x * cell_size
                    y = origin_y - (local_y + 1) * cell_size
                    if code:
                        red, green, blue = palette[code]
                        pdf.setFillColorRGB(red / 255, green / 255, blue / 255)
                        pdf.rect(x, y, cell_size, cell_size, fill=1, stroke=0)
                        luminance = (red * 299 + green * 587 + blue * 114) / 1000
                        pdf.setFillColor(colors.white if luminance < 120 else colors.black)
                        pdf.drawCentredString(x + cell_size / 2, y + cell_size * 0.3, code)
                    pdf.setStrokeColor(colors.HexColor("#8d8379"))
                    pdf.rect(x, y, cell_size, cell_size, fill=0, stroke=1)
            pdf.showPage()
    return pages


def render_pattern_pdf(version, *, guidance):
    font_name, embedded = _register_cjk_font()
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4, pageCompression=1)
    pdf.setTitle(f"{version.pattern.title} v{version.version_number}")

    _draw_header(pdf, font_name, version.pattern.title, f"拼豆制作图 v{version.version_number}")
    pdf.setFont(font_name, 11)
    pdf.drawString(
        42, A4[1] - 72, f"尺寸：{version.grid_data['width']}×{version.grid_data['height']}"
    )
    pdf.drawString(210, A4[1] - 72, f"颜色：{len(version.material_counts)} 色")
    pdf.drawString(370, A4[1] - 72, f"总用豆：{version.total_beads} 颗")
    if version.effect_preview:
        with version.effect_preview.open("rb") as preview:
            pdf.drawImage(
                ImageReader(BytesIO(preview.read())),
                72,
                180,
                width=450,
                height=450,
                preserveAspectRatio=True,
                anchor="c",
            )
    pdf.setFont(font_name, 10)
    pdf.drawString(42, 135, f"制作难度：{guidance['difficulty']}")
    pdf.drawString(42, 115, guidance["advice"])
    pdf.showPage()
    page_count = 1 + _grid_pages(pdf, version, font_name)

    _draw_header(pdf, font_name, "颜色编号与材料清单", f"共 {version.total_beads} 颗")
    pdf.setFont(font_name, 10)
    y = A4[1] - 75
    for index, (code, count) in enumerate(sorted(version.material_counts.items()), start=1):
        column = 0 if index <= 20 else 1
        row = (index - 1) % 20
        x = 54 + column * 250
        y = A4[1] - 75 - row * 30
        rgb = dict((item.code, item.rgb) for item in DEFAULT_PALETTE.colors)[code]
        pdf.setFillColorRGB(*(value / 255 for value in rgb))
        pdf.rect(x, y - 9, 15, 15, fill=1, stroke=1)
        pdf.setFillColor(colors.black)
        pdf.drawString(x + 24, y - 6, f"{code}  ·  {count} 颗")
    pdf.setFont(font_name, 9)
    pdf.drawString(54, 72, f"核对：材料合计 {sum(version.material_counts.values())} 颗")
    pdf.showPage()
    page_count += 1
    pdf.save()
    return output.getvalue(), page_count, {"font": font_name, "font_embedded": embedded}
