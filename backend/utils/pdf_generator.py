"""
pdf_generator.py
----------------
Generates a professional Credit Assessment PDF report using ReportLab.

Pages:
  1. Cover — score gauge, band, applicant info
  2. Business & Financial Details
  3. SHAP Feature Impact
  4. RBI Compliance Disclosure
"""

import io, json
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Table, TableStyle, HRFlowable,
                                 KeepTogether)
from reportlab.graphics.shapes import Drawing, Wedge, String, Circle, Rect
from reportlab.graphics import renderPDF
from reportlab.graphics.charts.piecharts import Pie
import math

# ── Brand colours ──────────────────────────────────────────────────────────────
PRIMARY   = colors.HexColor('#1a56db')
DARK      = colors.HexColor('#0f172a')
MUTED     = colors.HexColor('#64748b')
BORDER    = colors.HexColor('#e2e8f0')
BG        = colors.HexColor('#f8fafc')
GREEN     = colors.HexColor('#10b981')
AMBER     = colors.HexColor('#f59e0b')
RED       = colors.HexColor('#ef4444')
WHITE     = colors.white

PAGE_W, PAGE_H = A4
MARGIN = 2 * cm


def _score_color(score):
    if score >= 720: return GREEN
    if score >= 580: return AMBER
    return RED


def _risk_color(risk):
    return {'Low': GREEN, 'Medium': AMBER, 'High': RED}.get(risk, AMBER)


def _style(name, **kwargs):
    base = {
        'fontName' : 'Helvetica',
        'fontSize' : 10,
        'textColor': DARK,
        'leading'  : 14,
        'spaceAfter': 4,
    }
    base.update(kwargs)
    return ParagraphStyle(name, **base)


# Pre-define styles
S_TITLE    = _style('Title',    fontName='Helvetica-Bold', fontSize=22, textColor=WHITE, leading=28)
S_H1       = _style('H1',       fontName='Helvetica-Bold', fontSize=14, textColor=PRIMARY, spaceAfter=6)
S_H2       = _style('H2',       fontName='Helvetica-Bold', fontSize=11, textColor=DARK, spaceAfter=4)
S_BODY     = _style('Body',     fontSize=9,  textColor=DARK, leading=14)
S_MUTED    = _style('Muted',    fontSize=8,  textColor=MUTED, leading=12)
S_MONO     = _style('Mono',     fontName='Courier', fontSize=8, textColor=DARK, leading=12)
S_LABEL    = _style('Label',    fontName='Helvetica-Bold', fontSize=7,
                    textColor=MUTED, leading=10, spaceAfter=2)
S_WHITE    = _style('White',    fontSize=9,  textColor=WHITE, leading=13)
S_SCORE    = _style('Score',    fontName='Helvetica-Bold', fontSize=48,
                    textColor=WHITE, leading=52)
S_BAND     = _style('Band',     fontName='Helvetica-Bold', fontSize=13, textColor=WHITE)


def _gauge_drawing(score, color, width=160, height=90):
    """Draw a SVG-style semicircle gauge."""
    d   = Drawing(width, height)
    cx, cy, r = width / 2, 15, 60

    # Track arc (grey)
    for angle in range(0, 181, 2):
        rad = math.radians(angle)
        x1  = cx + r * math.cos(math.pi - rad)
        y1  = cy + r * math.sin(rad)
        d.add(Circle(x1, y1, 2.5, fillColor=colors.HexColor('#e2e8f0'), strokeColor=None))

    # Fill arc
    fill_angle = int((score - 300) / 600 * 180)
    for angle in range(0, fill_angle, 2):
        rad = math.radians(angle)
        x1  = cx + r * math.cos(math.pi - rad)
        y1  = cy + r * math.sin(rad)
        d.add(Circle(x1, y1, 2.5, fillColor=color, strokeColor=None))

    return d


def _kv_table(rows, col_widths=None):
    """Two-column key-value table."""
    cw = col_widths or [5 * cm, 9 * cm]
    data = [[Paragraph(f'<b>{k}</b>', S_LABEL), Paragraph(str(v), S_BODY)]
            for k, v in rows]
    t = Table(data, colWidths=cw)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), BG),
        ('GRID',       (0, 0), (-1, -1), 0.5, BORDER),
        ('PADDING',    (0, 0), (-1, -1), 6),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [WHITE, BG]),
    ]))
    return t


def _shap_bar_table(contributions):
    """Horizontal bar chart for SHAP values."""
    MAX_BAR = 8 * cm
    rows = []
    for c in contributions[:10]:
        name  = c.get('display_name', c.get('feature', ''))[:30]
        val   = c.get('formatted_value', '')
        imp   = c.get('abs_impact', 0)
        dirn  = c.get('direction', 'positive')
        bar_w = min(imp * 1800 / 100 * MAX_BAR, MAX_BAR)
        color = GREEN if dirn == 'positive' else RED

        bar_drawing = Drawing(MAX_BAR, 14)
        bar_drawing.add(Rect(0, 3, bar_w, 8, fillColor=color,
                             strokeColor=None, rx=3, ry=3))

        rows.append([
            Paragraph(name, S_BODY),
            bar_drawing,
            Paragraph(val, S_MONO),
        ])

    t = Table(rows, colWidths=[5.5 * cm, MAX_BAR + 0.5 * cm, 2.5 * cm])
    t.setStyle(TableStyle([
        ('VALIGN',  (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -2), 0.3, BORDER),
    ]))
    return t


def generate_pdf(application, band: dict, explanation: dict) -> bytes:
    """
    Generate and return PDF bytes for the given application.

    Args:
        application : LoanApplication SQLAlchemy object
        band        : dict from scorer.get_band()
        explanation : dict from explainer.explain() (may be empty)

    Returns:
        bytes — PDF file content
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN,
        title=f'Credit Report — {application.business_name}',
        author='SMECreditAI',
    )

    story = []
    score = application.ai_credit_score or 0
    sc    = _score_color(score)
    rc    = _risk_color(application.risk_category or 'High')

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 1 — COVER
    # ══════════════════════════════════════════════════════════════════════════

    # Dark header banner
    header_data = [[
        Paragraph('SMECreditAI', _style('logo', fontName='Helvetica-Bold',
                                        fontSize=18, textColor=WHITE)),
        Paragraph('AI Credit Assessment Report',
                  _style('sub', fontSize=9, textColor=colors.HexColor('#94a3b8'),
                         alignment=2)),
    ]]
    header_t = Table(header_data,
                     colWidths=[PAGE_W - 2 * MARGIN - 5 * cm, 5 * cm])
    header_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), DARK),
        ('PADDING',    (0, 0), (-1, -1), 16),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(header_t)
    story.append(Spacer(1, 0.5 * cm))

    # Score + gauge side by side
    gauge = _gauge_drawing(score, sc, 180, 100)
    score_block = [
        [Paragraph('AI CREDIT SCORE', S_LABEL),
         Paragraph('', S_BODY)],
        [Paragraph(str(score),
                   _style('BigScore', fontName='Helvetica-Bold', fontSize=52,
                           textColor=sc, leading=56)),
         gauge],
        [Paragraph(band.get('label', ''), _style('BandLbl',
                    fontName='Helvetica-Bold', fontSize=13, textColor=sc)),
         Paragraph(f"Range: {band.get('range', '')}", S_MUTED)],
    ]
    score_t = Table(score_block, colWidths=[6 * cm, PAGE_W - 2 * MARGIN - 6 * cm])
    score_t.setStyle(TableStyle([
        ('VALIGN',  (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(score_t)
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width='100%', thickness=1, color=BORDER))
    story.append(Spacer(1, 0.3 * cm))

    # Applicant info strip
    eligible = 'YES' if score >= 620 else 'NO'
    elig_color = GREEN if score >= 620 else RED
    info_rows = [
        ['Business', application.business_name,
         'Risk Category', application.risk_category or '—'],
        ['Industry', application.industry,
         'Eligible', eligible],
        ['Loan Requested', f"Rs.{application.loan_amount_requested}L",
         'Annual Turnover', f"Rs.{application.annual_turnover}L"],
        ['Assessment Date', datetime.utcnow().strftime('%d %b %Y'),
         'Application ID', f"#{application.id}"],
    ]
    cw = [3 * cm, 5.5 * cm, 3 * cm, 5.5 * cm]
    info_t = Table(
        [[Paragraph(f'<b>{r[0]}</b>', S_LABEL), Paragraph(str(r[1]), S_BODY),
          Paragraph(f'<b>{r[2]}</b>', S_LABEL), Paragraph(str(r[3]), S_BODY)]
         for r in info_rows],
        colWidths=cw,
    )
    info_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), BG),
        ('BACKGROUND', (2, 0), (2, -1), BG),
        ('GRID',       (0, 0), (-1, -1), 0.4, BORDER),
        ('PADDING',    (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [WHITE, BG]),
    ]))
    story.append(info_t)
    story.append(Spacer(1, 0.5 * cm))

    # Summary text
    if explanation.get('summary_text'):
        story.append(Paragraph('AI ASSESSMENT SUMMARY', S_LABEL))
        story.append(Spacer(1, 0.15 * cm))
        summary_t = Table(
            [[Paragraph(explanation['summary_text'], S_BODY)]],
            colWidths=[PAGE_W - 2 * MARGIN],
        )
        summary_t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#eff6ff')),
            ('LINERIGHT',  (0, 0), (0, -1), 3, PRIMARY),
            ('PADDING',    (0, 0), (-1, -1), 10),
        ]))
        story.append(summary_t)

    story.append(Spacer(1, 0.5 * cm))

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 2 — BUSINESS & FINANCIAL DETAILS
    # ══════════════════════════════════════════════════════════════════════════
    story.append(HRFlowable(width='100%', thickness=0.5, color=BORDER))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph('BUSINESS & FINANCIAL DETAILS', S_H1))
    story.append(Spacer(1, 0.25 * cm))

    col_w = (PAGE_W - 2 * MARGIN - 0.5 * cm) / 2

    biz_rows = [
        ('Business Name',      application.business_name),
        ('Business Type',      application.business_type),
        ('Industry',           application.industry),
        ('Years in Business',  f'{application.years_in_business} yrs'),
        ('Employees',          str(application.num_employees)),
        ('Annual Turnover',    f'Rs.{application.annual_turnover}L'),
        ('Loan Purpose',       application.loan_purpose),
        ('Loan Requested',     f'Rs.{application.loan_amount_requested}L'),
    ]
    fin_rows = [
        ('Monthly Credits',    f'Rs.{application.monthly_credits}L'),
        ('Monthly Debits',     f'Rs.{application.monthly_debits}L'),
        ('Avg Bank Balance',   f'Rs.{application.avg_monthly_balance}L'),
        ('Existing EMI',       f'Rs.{application.existing_loan_emi}L'),
        ('EMI Bounces',        str(application.num_emi_bounces)),
        ('Cheque Bounces',     str(application.num_cheque_bounces)),
        ('GST Filing',         f'{application.gst_filing_regularity}%'),
        ('Prior Defaults',     str(application.previous_loan_defaults)),
    ]

    def mini_table(rows):
        data = [[Paragraph(f'<b>{k}</b>', S_LABEL), Paragraph(v, S_BODY)]
                for k, v in rows]
        t = Table(data, colWidths=[3.8 * cm, col_w - 3.8 * cm])
        t.setStyle(TableStyle([
            ('GRID',    (0, 0), (-1, -1), 0.4, BORDER),
            ('PADDING', (0, 0), (-1, -1), 5),
            ('BACKGROUND', (0, 0), (0, -1), BG),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [WHITE, BG]),
        ]))
        return t

    two_col = Table(
        [[mini_table(biz_rows), mini_table(fin_rows)]],
        colWidths=[col_w, col_w],
        hAlign='LEFT',
    )
    two_col.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                  ('LEFTPADDING', (1, 0), (1, -1), 12)]))
    story.append(two_col)
    story.append(Spacer(1, 0.5 * cm))

    # Alternate data row
    alt_rows = [
        ('Social Presence',     f'{application.social_presence_score}/10'),
        ('Industry Growth',     f'{application.industry_growth_factor}/10'),
        ('Online Rating',       f'{application.online_reviews_rating}/5'),
        ('Collateral',          f'Rs.{application.collateral_value}L' if application.collateral_available else 'None'),
        ('CIBIL Score',         str(application.existing_credit_score) if application.existing_credit_score else 'Not provided'),
        ('Export Presence',     'Yes' if application.export_presence else 'No'),
    ]
    story.append(Paragraph('ALTERNATE & MARKET SIGNALS', S_H2))
    story.append(Spacer(1, 0.15 * cm))
    alt_data = [[Paragraph(f'<b>{k}</b>', S_LABEL), Paragraph(v, S_BODY)]
                for k, v in alt_rows]
    alt_t = Table(alt_data, colWidths=[4.5 * cm, 12.5 * cm])
    alt_t.setStyle(TableStyle([
        ('GRID',    (0, 0), (-1, -1), 0.4, BORDER),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('BACKGROUND', (0, 0), (0, -1), BG),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [WHITE, BG]),
    ]))
    story.append(alt_t)
    story.append(Spacer(1, 0.5 * cm))

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 3 — SHAP FEATURE IMPACT
    # ══════════════════════════════════════════════════════════════════════════
    if explanation.get('contributions'):
        story.append(HRFlowable(width='100%', thickness=0.5, color=BORDER))
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph('AI FEATURE IMPACT (SHAP Analysis)', S_H1))
        story.append(Paragraph(
            f'Method: {explanation.get("method", "Permutation Importance")}. '
            'Green bars = positive impact on score. Red bars = negative impact.',
            S_MUTED))
        story.append(Spacer(1, 0.3 * cm))
        story.append(_shap_bar_table(explanation['contributions']))
        story.append(Spacer(1, 0.4 * cm))

        # Top positive / negative two-column
        top_pos = explanation.get('top_positive', [])[:4]
        top_neg = explanation.get('top_negative', [])[:4]

        def factor_table(items, color):
            rows = [[Paragraph(f'<b>{c["display_name"]}</b>', S_BODY),
                     Paragraph(c.get('formatted_value', ''), S_MUTED)]
                    for c in items]
            if not rows:
                return Paragraph('—', S_MUTED)
            t = Table(rows, colWidths=[5 * cm, 2.5 * cm])
            t.setStyle(TableStyle([
                ('GRID',    (0, 0), (-1, -1), 0.4, BORDER),
                ('PADDING', (0, 0), (-1, -1), 5),
                ('LINERIGHT', (-1, 0), (-1, -1), 2, color),
            ]))
            return t

        factors_t = Table(
            [[Paragraph('<b>Helped Your Score</b>', _style('pos', fontName='Helvetica-Bold',
                         fontSize=9, textColor=GREEN)),
              Paragraph('<b>Hurt Your Score</b>', _style('neg', fontName='Helvetica-Bold',
                         fontSize=9, textColor=RED))],
             [factor_table(top_pos, GREEN), factor_table(top_neg, RED)]],
            colWidths=[(PAGE_W - 2 * MARGIN) / 2 - 0.25 * cm] * 2,
        )
        factors_t.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (1, 0), (1, -1), 12),
        ]))
        story.append(factors_t)
        story.append(Spacer(1, 0.5 * cm))

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 4 — RBI COMPLIANCE BLOCK
    # ══════════════════════════════════════════════════════════════════════════
    story.append(HRFlowable(width='100%', thickness=0.5, color=BORDER))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph('RBI COMPLIANCE DISCLOSURE', S_H1))
    story.append(Spacer(1, 0.2 * cm))

    rbi_text = explanation.get('rbi_explanation', '') or (
        f"CREDIT ASSESSMENT DISCLOSURE (RBI Fair Lending Guidelines)\n"
        f"Credit Score Assigned : {score} / 900\n"
        f"Risk Classification   : {application.risk_category} Risk\n"
        f"Scoring Model         : Gradient Boosting Classifier\n"
        f"Assessment Date       : {datetime.utcnow().strftime('%d %b %Y')}\n\n"
        f"This assessment was generated by an AI model. The applicant has "
        f"the right to request a manual review of this decision."
    )

    rbi_lines = rbi_text.split('\n')
    rbi_paras = [Paragraph(line if line else '&nbsp;', S_MONO)
                 for line in rbi_lines]

    rbi_t = Table([[para] for para in rbi_paras],
                  colWidths=[PAGE_W - 2 * MARGIN])
    rbi_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), DARK),
        ('PADDING',    (0, 0), (-1, -1), 3),
        ('LEFTPADDING',(0, 0), (-1, -1), 12),
        ('RIGHTPADDING',(0,0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 10),
    ]))
    # Wrap rbi_paras with white text
    for para in rbi_paras:
        para.style = _style('RBI', fontName='Courier', fontSize=8,
                            textColor=WHITE, leading=13)

    story.append(rbi_t)
    story.append(Spacer(1, 0.5 * cm))

    # Footer
    footer_t = Table(
        [[Paragraph('Generated by SMECreditAI — AI-Powered SME Credit Scoring System',
                    S_MUTED),
          Paragraph(datetime.utcnow().strftime('%d %b %Y, %H:%M UTC'),
                    _style('ft', fontSize=8, textColor=MUTED, alignment=2))]],
        colWidths=[(PAGE_W - 2 * MARGIN) * 0.65,
                   (PAGE_W - 2 * MARGIN) * 0.35],
    )
    footer_t.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, 0), 0.5, BORDER),
        ('PADDING',   (0, 0), (-1, -1), 6),
    ]))
    story.append(footer_t)

    doc.build(story)
    return buf.getvalue()