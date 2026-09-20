"""
Binary renderers for generated reports.

The report bodies are authored once as Markdown in routers/reports.py; this
module turns that same content into PDF and XLSX so a board pack does not have
to be reformatted by hand. Both return raw bytes, which the router base64-encodes.

Only the small Markdown subset the reports actually emit is handled — headings,
bullets, pipe tables, rules and paragraphs. It is a renderer for our own output,
not a general Markdown implementation.
"""

from __future__ import annotations

import io
import re
from typing import List, Tuple

# Brand palette, mirroring frontend/src/index.css. Print needs an ink-on-paper
# inversion of the dark UI, so the surface is white and the text is near-black.
INK = "#1a1a1a"
MUTED = "#5c6478"
ACCENT = "#7f8caa"
RULE = "#d8dbe2"


def _is_table_row(line: str) -> bool:
    return line.startswith("|") and line.endswith("|")


def _split_row(line: str) -> List[str]:
    return [c.strip() for c in line.strip("|").split("|")]


def _is_separator(cells: List[str]) -> bool:
    """The `|---|---|` line under a Markdown table header."""
    return bool(cells) and all(set(c) <= set("-: ") and "-" in c for c in cells)


def _parse(markdown: str) -> List[Tuple[str, object]]:
    """
    Flattens Markdown into ('kind', payload) blocks.

    Kinds: h1, h2, h3, bullet, table (list of rows), rule, para.
    """
    blocks: List[Tuple[str, object]] = []
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            i += 1
            continue
        if _is_table_row(line):
            rows = []
            while i < len(lines) and _is_table_row(lines[i].rstrip()):
                cells = _split_row(lines[i].rstrip())
                if not _is_separator(cells):
                    rows.append(cells)
                i += 1
            if rows:
                blocks.append(("table", rows))
            continue
        if line.startswith("### "):
            blocks.append(("h3", line[4:]))
        elif line.startswith("## "):
            blocks.append(("h2", line[3:]))
        elif line.startswith("# "):
            blocks.append(("h1", line[2:]))
        elif line.startswith("- "):
            blocks.append(("bullet", line[2:]))
        elif set(line) <= {"-", "_"} and len(line) >= 3:
            blocks.append(("rule", ""))
        else:
            blocks.append(("para", line))
        i += 1
    return blocks


def _plain(text: str) -> str:
    """Strips the bold/italic/code marks the reports use."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    return text.replace("`", "")


def _inline(text: str) -> str:
    """Markdown emphasis to ReportLab's inline markup."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"_(.+?)_", r"<i>\1</i>", text)
    return text.replace("`", "")


def to_pdf(markdown: str, title: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=title, author="RISHFORGEAI",
    )

    base = getSampleStyleSheet()
    styles = {
        "h1": ParagraphStyle("h1", parent=base["Title"], fontSize=19, leading=24,
                             textColor=colors.HexColor(INK), alignment=TA_LEFT,
                             spaceAfter=4),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=13, leading=17,
                             textColor=colors.HexColor(INK), spaceBefore=12, spaceAfter=5),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontSize=11, leading=15,
                             textColor=colors.HexColor(MUTED), spaceBefore=9, spaceAfter=3),
        "para": ParagraphStyle("para", parent=base["BodyText"], fontSize=9.5, leading=14,
                               textColor=colors.HexColor(INK)),
        "bullet": ParagraphStyle("bullet", parent=base["BodyText"], fontSize=9.5, leading=14,
                                 leftIndent=10, bulletIndent=2,
                                 textColor=colors.HexColor(INK)),
        "cell": ParagraphStyle("cell", parent=base["BodyText"], fontSize=8.5, leading=11,
                               textColor=colors.HexColor(INK)),
        "cellhead": ParagraphStyle("cellhead", parent=base["BodyText"], fontSize=8.5,
                                   leading=11, textColor=colors.white),
    }

    story = []
    for kind, payload in _parse(markdown):
        if kind in ("h1", "h2", "h3"):
            story.append(Paragraph(_inline(str(payload)), styles[kind]))
        elif kind == "bullet":
            story.append(Paragraph(_inline(str(payload)), styles["bullet"], bulletText="•"))
        elif kind == "para":
            story.append(Paragraph(_inline(str(payload)), styles["para"]))
            story.append(Spacer(1, 3))
        elif kind == "rule":
            story.append(Spacer(1, 6))
            story.append(HRFlowable(width="100%", thickness=0.6,
                                    color=colors.HexColor(RULE)))
            story.append(Spacer(1, 6))
        elif kind == "table":
            rows = payload
            data = [[Paragraph(_inline(c), styles["cellhead"]) for c in rows[0]]]
            data += [[Paragraph(_inline(c), styles["cell"]) for c in r] for r in rows[1:]]
            table = Table(data, repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(ACCENT)),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.white, colors.HexColor("#f4f5f7")]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(RULE)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(Spacer(1, 4))
            story.append(table)
            story.append(Spacer(1, 8))

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.drawString(18 * mm, 11 * mm, "RISHFORGEAI — confidential")
        canvas.drawRightString(A4[0] - 18 * mm, 11 * mm, f"Page {doc_.page}")
        canvas.restoreState()

    if not story:
        story = [Paragraph("No content.", styles["para"])]
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def to_xlsx(markdown: str, title: str) -> bytes:
    """
    Tables become real sheets with real numbers; the prose lands on a Summary
    sheet. The point of the spreadsheet export is that figures stay computable,
    so numeric-looking cells are written as numbers, not strings.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    summary = wb.active
    summary.title = "Summary"

    head_fill = PatternFill("solid", fgColor="7F8CAA")
    head_font = Font(bold=True, color="FFFFFF", size=10)
    thin = Side(style="thin", color="D8DBE2")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def _num(value: str):
        """'Rs 1.20 Cr' stays text; '42.5' and '1,234' become numbers."""
        cleaned = value.replace(",", "").replace("%", "").strip()
        try:
            return float(cleaned) if "." in cleaned else int(cleaned)
        except ValueError:
            return value

    row = 1
    summary.cell(row=row, column=1, value=title).font = Font(bold=True, size=14)
    row += 2

    table_index = 0
    for kind, payload in _parse(markdown):
        if kind == "table":
            table_index += 1
            rows = payload
            # Name the sheet after the heading that introduced it where possible.
            sheet = wb.create_sheet(f"Table {table_index}")
            for c, header in enumerate(rows[0], start=1):
                cell = sheet.cell(row=1, column=c, value=_plain(header))
                cell.fill, cell.font, cell.border = head_fill, head_font, border
                cell.alignment = Alignment(vertical="center")
            for r, data_row in enumerate(rows[1:], start=2):
                for c, value in enumerate(data_row, start=1):
                    cell = sheet.cell(row=r, column=c, value=_num(_plain(value)))
                    cell.border = border
            for c in range(1, len(rows[0]) + 1):
                widest = max((len(str(r[c - 1])) for r in rows if c - 1 < len(r)), default=10)
                sheet.column_dimensions[get_column_letter(c)].width = min(46, max(12, widest + 3))
            sheet.freeze_panes = "A2"
            summary.cell(row=row, column=1, value=f"See sheet: {sheet.title}").font = Font(
                italic=True, color="5C6478")
            row += 1
        elif kind == "rule":
            row += 1
        else:
            text = _plain(str(payload))
            cell = summary.cell(row=row, column=1, value=("• " + text) if kind == "bullet" else text)
            if kind in ("h1", "h2", "h3"):
                cell.font = Font(bold=True, size=12 if kind != "h3" else 10)
            row += 1

    summary.column_dimensions["A"].width = 108
    for r in range(1, row):
        summary.cell(row=r, column=1).alignment = Alignment(wrap_text=True, vertical="top")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
