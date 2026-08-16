"""
Generates a small synthetic PDF that mimics the structure of a real BRSR report
(a principle heading, a hedged narrative paragraph, and a KPI table) so the
ingestion pipeline can be smoke-tested end-to-end before any real filings are
available. This is NOT training data — it exists purely to validate that
extraction, table detection, and text ordering work correctly.
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm


def build(output_path: str) -> None:
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Principle 6: Environmental Protection and Stewardship", styles["Heading1"]))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph(
        "The Company remains committed to achieving significant progress in reducing its "
        "environmental footprint. We aspire to substantially lower our greenhouse gas "
        "emissions over time and are working towards a more sustainable future, subject to "
        "operational feasibility and evolving regulatory guidance.",
        styles["BodyText"],
    ))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("Table 1: GHG Emissions (Scope 1 and Scope 2)", styles["Heading3"]))
    data = [
        ["Parameter", "FY 2022-23", "FY 2023-24", "Unit"],
        ["Scope 1 Emissions", "12,450", "13,120", "tCO2e"],
        ["Scope 2 Emissions", "8,900", "9,340", "tCO2e"],
        ["Water Consumption", "1,20,000", "1,26,500", "KL"],
    ]
    table = Table(data, colWidths=[6 * cm, 3.2 * cm, 3.2 * cm, 2 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E4053")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.6 * cm))

    story.append(Paragraph("Principle 3: Employee Well-being and Safety", styles["Heading1"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        "The Company provided 42,300 total training hours to employees during the reporting "
        "period, a 15% increase over the previous year. 98.2% of permanent employees received "
        "health insurance coverage, and zero fatalities were recorded across all operations.",
        styles["BodyText"],
    ))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.build(story)


if __name__ == "__main__":
    build(str(Path(__file__).parent / "synthetic_brsr_sample.pdf"))
    print("Wrote synthetic_brsr_sample.pdf")
