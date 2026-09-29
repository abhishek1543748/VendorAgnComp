import os
from datetime import datetime
from typing import List, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.models.tables import Device, FindingDB

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(['html', 'xml'])
)


def _compute_summary(findings: List[FindingDB]) -> dict:
    """Compute executive summary stats from a findings list."""
    pass_count = sum(1 for f in findings if f.status.lower() == "pass")
    fail_count = sum(1 for f in findings if f.status.lower() == "fail")
    review_count = sum(1 for f in findings if f.status.lower() == "needs_review")
    skip_count = len(findings) - pass_count - fail_count - review_count
    total = len(findings)
    score_pct = round((pass_count / total) * 100) if total > 0 else 0
    
    failed = [f for f in findings if f.status.lower() == "fail"]
    sev_counts = {
        "critical": sum(1 for f in failed if (f.severity or "").lower() == "critical"),
        "high":     sum(1 for f in failed if (f.severity or "").lower() == "high"),
        "medium":   sum(1 for f in failed if (f.severity or "").lower() == "medium"),
        "low":      sum(1 for f in failed if (f.severity or "").lower() == "low"),
    }

    if score_pct >= 80:
        risk = "LOW"
    elif score_pct >= 50:
        risk = "MEDIUM"
    else:
        risk = "HIGH"

    return {
        "pass_count": pass_count,
        "fail_count": fail_count,
        "review_count": review_count,
        "skip_count": skip_count,
        "total": total,
        "score_pct": score_pct,
        "risk": risk,
        "sev_counts": sev_counts,
    }


def _generate_pdf_reportlab(
    device: Device,
    findings: List[FindingDB],
    generated_at: str,
    framework: str = "General",
    parse_warnings: Optional[List[str]] = None,
) -> bytes:
    """Fallback PDF generator using ReportLab when native WeasyPrint GTK C-libraries are unavailable."""
    from io import BytesIO
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Preformatted

    parse_warnings = parse_warnings or []
    summary = _compute_summary(findings)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=20, leading=24,
                                 textColor=colors.HexColor('#0f172a'), spaceAfter=4)
    h2_style = ParagraphStyle('SectionHeader', parent=styles['Heading2'], fontSize=14, leading=18,
                              textColor=colors.HexColor('#1e293b'), spaceBefore=16, spaceAfter=8)
    normal_style = styles['Normal']
    small_style = ParagraphStyle('Small', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#64748b'))
    code_style = ParagraphStyle('CodeStyle', parent=styles['Code'], fontSize=9, leading=12,
                                textColor=colors.HexColor('#f8fafc'), backColor=colors.HexColor('#0f172a'),
                                borderPadding=6, spaceAfter=10)

    # --- Header ---
    story.append(Paragraph("Device Compliance Evaluation Report", title_style))
    story.append(Paragraph(f"Generated on {generated_at}  ·  Device ID: {device.id}", small_style))
    story.append(Spacer(1, 8))

    # --- Parse quality warning ---
    if parse_warnings:
        warn_text = "⚠ Parse Quality Notice: " + " | ".join(parse_warnings)
        story.append(Paragraph(warn_text, ParagraphStyle('Warn', parent=normal_style, fontSize=9,
                               textColor=colors.HexColor('#78350f'),
                               backColor=colors.HexColor('#fffbeb'),
                               borderPadding=6, spaceAfter=8)))
        story.append(Spacer(1, 6))

    # --- Section 0: Executive Summary ---
    story.append(Paragraph(f"0. Executive Summary  [{framework}]", h2_style))
    
    risk_color = {'LOW': '#166534', 'MEDIUM': '#92400e', 'HIGH': '#991b1b'}.get(summary['risk'], '#000')
    story.append(Paragraph(
        f"<b>Compliance Score: {summary['score_pct']}%</b> "
        f"({summary['pass_count']}/{summary['total']} controls passed) &nbsp;&nbsp; "
        f"<font color='{risk_color}'><b>Risk: {summary['risk']}</b></font>",
        normal_style
    ))
    story.append(Spacer(1, 6))

    exec_data = [
        ["Passed", "Failed", "Needs Review", "Skipped/Not Evaluated"],
        [str(summary['pass_count']), str(summary['fail_count']),
         str(summary['review_count']), str(summary['skip_count'])],
    ]
    exec_table = Table(exec_data, colWidths=[120, 120, 120, 120])
    exec_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TEXTCOLOR', (0, 1), (0, 1), colors.HexColor('#166534')),
        ('TEXTCOLOR', (1, 1), (1, 1), colors.HexColor('#991b1b')),
        ('TEXTCOLOR', (2, 1), (2, 1), colors.HexColor('#92400e')),
    ]))
    story.append(exec_table)

    sc = summary['sev_counts']
    if any(sc.values()):
        story.append(Spacer(1, 6))
        sev_text = "Failed by severity — " + "  ".join(
            f"{k.capitalize()}: {v}" for k, v in sc.items() if v > 0
        )
        story.append(Paragraph(sev_text, small_style))

    story.append(Spacer(1, 12))

    # --- Section 1: Device Identification ---
    story.append(Paragraph("1. Device Identification", h2_style))
    dev_data = [
        ["Hostname:", device.hostname or 'N/A', "Serial Number:", device.serial_number or 'N/A'],
        ["Model:", device.model or 'N/A', "Firmware Version:", device.firmware_version or 'N/A'],
        ["Vendor:", device.vendor or 'N/A', "OS / Platform:", device.os_hint or 'N/A'],
        ["Detection Confidence:", f"{int((device.detection_confidence or 0) * 100)}%", "Source File:", device.filename],
    ]
    meta_table = Table(dev_data, colWidths=[100, 160, 100, 160])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8fafc')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f8fafc')),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTNAME', (3, 0), (3, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # --- Section 2: Compliance Findings ---
    story.append(Paragraph(f"2. Compliance Findings  [{framework}]", h2_style))
    if findings:
        findings_data = [["Control ID", "Status", "Severity", "Observed Value", "Raw Source Line"]]
        for f in findings:
            findings_data.append([
                f.control_id,
                f.status.upper(),
                f.severity or 'N/A',
                f.observed_value or 'N/A',
                f.raw_line or 'N/A'
            ])
        find_table = Table(findings_data, colWidths=[80, 70, 70, 120, 180])
        t_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#334155')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ]
        for idx, f in enumerate(findings, start=1):
            if f.status.lower() == 'pass':
                t_style.append(('TEXTCOLOR', (1, idx), (1, idx), colors.HexColor('#166534')))
            elif f.status.lower() == 'fail':
                t_style.append(('TEXTCOLOR', (1, idx), (1, idx), colors.HexColor('#991b1b')))
            elif f.status.lower() == 'needs_review':
                t_style.append(('TEXTCOLOR', (1, idx), (1, idx), colors.HexColor('#92400e')))
        find_table.setStyle(TableStyle(t_style))
        story.append(find_table)
    else:
        story.append(Paragraph("No compliance findings recorded for this device.", normal_style))

    story.append(Spacer(1, 12))

    # --- Section 3: Remediation Paths ---
    story.append(Paragraph("3. Remediation Paths", h2_style))
    failed = [f for f in findings if f.status.lower() == 'fail']
    review = [f for f in findings if f.status.lower() == 'needs_review']

    if failed or review:
        if failed:
            story.append(Paragraph("The following remediation CLI sequences apply to failed compliance controls:", normal_style))
            story.append(Spacer(1, 6))
            for f in failed:
                story.append(Paragraph(f"<b>Control {f.control_id}</b> (Severity: {f.severity or 'Unspecified'})", normal_style))
                cli_text = f.remediation_cli or "No automated CLI remediation path defined."
                story.append(Preformatted(cli_text, code_style))
        if review:
            story.append(Spacer(1, 6))
            story.append(Paragraph(
                f"<font color='#92400e'><b>Note: {len(review)} controls require manual review.</b></font>",
                normal_style
            ))
    else:
        story.append(Paragraph(
            "<font color='#166534'><b>All evaluated controls passed. No remediation steps required.</b></font>",
            normal_style
        ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def generate_device_pdf(
    device: Device,
    findings: List[FindingDB],
    framework: str = "General",
    parse_warnings: Optional[List[str]] = None,
) -> bytes:
    """
    Renders device details & evaluation findings into a compiled PDF binary document.
    Uses Jinja2 HTML rendering + WeasyPrint, falling back to ReportLab if native GTK libraries are missing.
    """
    parse_warnings = parse_warnings or []
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    summary = _compute_summary(findings)

    # 1. Render Jinja2 HTML Template
    template = env.get_template("report.html")
    rendered_html = template.render(
        device=device,
        findings=findings,
        generated_at=now_str,
        framework=framework,
        parse_warnings=parse_warnings,
        summary=summary,
    )

    # 2. Try WeasyPrint compilation
    try:
        import weasyprint
        return weasyprint.HTML(string=rendered_html).write_pdf()
    except (ImportError, OSError, Exception):
        # Fallback to ReportLab on platforms missing GTK/cairo libraries (e.g. Windows host)
        return _generate_pdf_reportlab(device, findings, now_str, framework, parse_warnings)
