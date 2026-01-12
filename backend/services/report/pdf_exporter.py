from io import BytesIO
from datetime import datetime

from models.report import InterviewReport


def export_report_pdf(report: InterviewReport) -> bytes:
    """Export interview report as PDF.

    Args:
        report: The interview report to export.

    Returns:
        PDF file as bytes.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError:
        raise ImportError(
            "reportlab is required for PDF export. "
            "Install it with: pip install reportlab"
        )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72,
    )

    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=24,
        spaceAfter=30,
        alignment=1,  # Center
    )
    story.append(Paragraph("Interview Report", title_style))

    # Candidate Info
    story.append(Paragraph("Candidate Information", styles["Heading2"]))
    info_data = [
        ["Name:", report.candidate_name],
        ["Email:", report.candidate_email],
        ["Position:", report.job_title],
        ["Company:", report.company_name],
        ["Interview Date:", _format_date(report.interview_date)],
        ["Report Generated:", _format_date(report.generated_at)],
    ]
    info_table = Table(info_data, colWidths=[1.5 * inch, 4 * inch])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))

    # Summary
    story.append(Paragraph("Interview Summary", styles["Heading2"]))
    summary = report.summary
    summary_data = [
        ["Overall Score:", f"{summary.overall_score:.0%}"],
        ["Status:", "PASS" if summary.pass_status else "FAIL"],
        ["Recommendation:", summary.recommendation],
        ["Total Questions:", str(summary.total_questions)],
        ["Follow-up Questions:", str(summary.total_followups)],
        ["Duration:", f"{summary.duration_minutes:.1f} minutes"],
        ["Topics Covered:", ", ".join(summary.topics_covered)],
    ]
    summary_table = Table(summary_data, colWidths=[1.5 * inch, 4 * inch])
    summary_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))

    # Skill Assessments
    story.append(Paragraph("Skill Assessments", styles["Heading2"]))

    if report.skill_assessments:
        skill_header = ["Skill", "Score", "Correctness", "Depth", "Communication", "Questions"]
        skill_data = [skill_header]

        for assessment in report.skill_assessments:
            skill_data.append([
                assessment.skill,
                f"{assessment.overall_score:.0%}",
                f"{assessment.average_correctness:.0%}",
                f"{assessment.average_depth:.0%}",
                f"{assessment.average_communication:.0%}",
                str(assessment.questions_asked),
            ])

        skill_table = Table(skill_data, colWidths=[1.2 * inch, 0.8 * inch, 1 * inch, 0.8 * inch, 1.2 * inch, 0.8 * inch])
        skill_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(skill_table)
    else:
        story.append(Paragraph("No skill assessments available.", styles["Normal"]))

    story.append(Spacer(1, 20))

    # Insights
    story.append(Paragraph("Evaluation Insights", styles["Heading2"]))

    story.append(Paragraph("<b>Strengths:</b>", styles["Normal"]))
    story.append(Paragraph(report.strengths_summary or "N/A", styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Areas for Improvement:</b>", styles["Normal"]))
    story.append(Paragraph(report.areas_for_improvement or "N/A", styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Hiring Recommendation:</b>", styles["Normal"]))
    story.append(Paragraph(report.hiring_recommendation or "N/A", styles["Normal"]))

    if report.detailed_feedback:
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>Detailed Feedback:</b>", styles["Normal"]))
        story.append(Paragraph(report.detailed_feedback, styles["Normal"]))

    # Build PDF
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes


def _format_date(dt: datetime) -> str:
    """Format datetime for display."""
    return dt.strftime("%B %d, %Y at %I:%M %p")
