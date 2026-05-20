"""
SMS Profile PDF Builder (from scratch — no master_template.docx).

Public entry point: build_company_pdf(company) -> BytesIO

Layout:
  Page 1     – Full-page cover image (or fallback) with overlayed title
  Page 2     – Table of Contents (auto-populated)
  Page 3     – Introduction + company details
  Pages 4+   – Operations, Fleet, Risk, Subcontractors, Incidents

Every content page has a logo top-right and a page number bottom-right.
"""

import io
import os
import re
from collections import defaultdict
from datetime import datetime
from html.parser import HTMLParser

from django.contrib.staticfiles.finders import find as find_static
from django.utils.html import strip_tags
from html import unescape

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, NextPageTemplate,
    PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from .models import CompanyAccreditation, Section


# ── Brand palette ─────────────────────────────────────────────
BRAND_BLUE = colors.HexColor('#2563eb')
INK        = colors.HexColor('#0f172a')
MUTED      = colors.HexColor('#64748b')
DIVIDER    = colors.HexColor('#e2e8f0')
SOFT_BG    = colors.HexColor('#f8fafc')
ACCENT_BG  = colors.HexColor('#eff6ff')


# ── HTML to ReportLab conversion helper ──────────────────────
class HTMLToReportLab(HTMLParser):
    """Parse HTML and convert to ReportLab Paragraph format with table support."""
    
    def __init__(self):
        super().__init__()
        self.result = []
        self.list_stack = []
        self.table_data = []
        self.current_row = []
        self.current_cell = []
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.current_tag = None
        self.bold = False
        self.italic = False
        self.underline = False
        
    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        
        if tag == 'table':
            self.in_table = True
            self.table_data = []
        elif tag == 'tr':
            self.in_row = True
            self.current_row = []
        elif tag in ('td', 'th'):
            self.in_cell = True
            self.current_cell = []
        elif tag in ('b', 'strong'):
            self.result.append('<b>')
            self.bold = True
        elif tag in ('i', 'em'):
            self.result.append('<i>')
            self.italic = True
        elif tag == 'u':
            self.result.append('<u>')
            self.underline = True
        elif tag in ('ul', 'ol'):
            self.list_stack.append({'type': tag, 'count': 0})
        elif tag == 'li':
            list_info = self.list_stack[-1] if self.list_stack else None
            if list_info:
                if list_info['type'] == 'ul':
                    self.result.append('• ')
                else:
                    list_info['count'] += 1
                    self.result.append(f'{list_info["count"]}. ')
        elif tag == 'p':
            pass  # Paragraphs handled by line breaks
        elif tag == 'br':
            self.result.append('<br/>')
            
    def handle_endtag(self, tag):
        if tag == 'table':
            self.in_table = False
            # Convert table data to ReportLab Table
            if self.table_data:
                self.result.append('__TABLE__')
                self.result.append(self.table_data)
                self.result.append('__END_TABLE__')
        elif tag == 'tr':
            self.in_row = False
            if self.current_row:
                self.table_data.append(self.current_row)
        elif tag in ('td', 'th'):
            self.in_cell = False
            cell_text = ''.join(self.current_cell).strip()
            self.current_row.append(cell_text)
            self.current_cell = []
        elif tag in ('b', 'strong'):
            self.result.append('</b>')
            self.bold = False
        elif tag in ('i', 'em'):
            self.result.append('</i>')
            self.italic = False
        elif tag == 'u':
            self.result.append('</u>')
            self.underline = False
        elif tag in ('ul', 'ol'):
            self.list_stack.pop()
        elif tag == 'li':
            self.result.append('<br/>')
            
    def handle_data(self, data):
        if self.in_cell:
            self.current_cell.append(data)
        else:
            if data.strip():
                # Apply current formatting
                formatted_data = data
                if self.bold:
                    formatted_data = f'<b>{formatted_data}</b>'
                if self.italic:
                    formatted_data = f'<i>{formatted_data}</i>'
                if self.underline:
                    formatted_data = f'<u>{formatted_data}</u>'
                self.result.append(formatted_data)
                
    def get_result(self, styles):
        """Convert parsed result to ReportLab flowables."""
        flowables = []
        current_text = []
        
        for item in self.result:
            if isinstance(item, str):
                if item == '__TABLE__':
                    # Flush any pending text
                    if current_text:
                        text = ''.join(current_text)
                        if text.strip():
                            flowables.append(Paragraph(text, styles['body']))
                        current_text = []
                elif item == '__END_TABLE__':
                    pass
                else:
                    current_text.append(item)
            elif isinstance(item, list):  # Table data
                if current_text:
                    text = ''.join(current_text)
                    if text.strip():
                        flowables.append(Paragraph(text, styles['body']))
                    current_text = []
                
                # Create ReportLab table
                if item:
                    # Determine column count
                    max_cols = max([len(row) for row in item]) if item else 0
                    # Create table data
                    table_data = []
                    for row in item:
                        table_row = []
                        for cell in row:
                            # Clean cell content
                            cell_clean = cell.strip() if cell else '—'
                            table_row.append(Paragraph(cell_clean, styles['body']))
                        # Pad row if needed
                        while len(table_row) < max_cols:
                            table_row.append(Paragraph('—', styles['body']))
                        table_data.append(table_row)
                    
                    if table_data:
                        # Calculate column widths
                        col_widths = [A4[0] * 0.8 / max_cols] * max_cols
                        
                        tbl = Table(table_data, colWidths=col_widths)
                        tbl.setStyle(TableStyle([
                            ('FONT', (0, 0), (-1, -1), 'Helvetica', 9),
                            ('TEXTCOLOR', (0, 0), (-1, -1), INK),
                            ('GRID', (0, 0), (-1, -1), 0.3, DIVIDER),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('TOPPADDING', (0, 0), (-1, -1), 6),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                            ('LEFTPADDING', (0, 0), (-1, -1), 6),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                        ]))
                        flowables.append(tbl)
                        flowables.append(Spacer(1, 6))
        
        # Flush any remaining text
        if current_text:
            text = ''.join(current_text)
            if text.strip():
                flowables.append(Paragraph(text, styles['body']))
        
        return flowables if flowables else [Paragraph('—', styles['small'])]


def html_to_flowables(html_content, styles):
    """Convert HTML content to a list of ReportLab flowables."""
    if not html_content or html_content == '—':
        return [Paragraph('—', styles['small'])]
    
    # Unescape HTML entities
    html_content = unescape(html_content)
    
    # Parse HTML
    parser = HTMLToReportLab()
    try:
        parser.feed(html_content)
        return parser.get_result(styles)
    except Exception as e:
        # Fallback to plain text
        clean_text = strip_tags(html_content)
        if clean_text.strip():
            return [Paragraph(clean_text, styles['body'])]
        return [Paragraph('—', styles['small'])]


# ── Static asset helpers ──────────────────────────────────────
def _find_first_static(candidates):
    for rel in candidates:
        p = find_static(rel)
        if p and os.path.exists(p):
            return p
    return None


def _logo_path():
    return _find_first_static([
        'images/logo.png', 'images/logo.jpg', 'images/logo.jpeg',
    ])


def _cover_path():
    return _find_first_static([
        'images/cover.jpg', 'images/cover.jpeg', 'images/cover.png',
    ])


# ── Custom heading flowable that records itself in the TOC ────
class TOCHeading(Paragraph):
    """A Paragraph that registers itself with the BaseDocTemplate's TOC."""
    def __init__(self, text, style, level=0):
        super().__init__(text, style)
        self.toc_level = level
        self.toc_text = text


# ── Custom doc template ───────────────────────────────────────
class CompanyPDFBuilder(BaseDocTemplate):
    def __init__(self, output, company, **kw):
        self.company = company
        super().__init__(
            output, pagesize=A4,
            leftMargin=2.0 * cm, rightMargin=2.0 * cm,
            topMargin=2.8 * cm, bottomMargin=2.2 * cm,
            **kw,
        )

        # Cover page — no margins, drawn entirely on canvas via onPage
        cover_frame = Frame(
            0, 0, A4[0], A4[1], id='cover',
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        )
        cover_tpl = PageTemplate(
            id='Cover', frames=[cover_frame], onPage=self._draw_cover_page,
        )

        # Content pages — header/footer drawn on canvas, content in frame
        content_frame = Frame(
            self.leftMargin, self.bottomMargin,
            A4[0] - self.leftMargin - self.rightMargin,
            A4[1] - self.topMargin - self.bottomMargin,
            id='content',
        )
        content_tpl = PageTemplate(
            id='Content', frames=[content_frame], onPage=self._draw_content_chrome,
        )

        self.addPageTemplates([cover_tpl, content_tpl])

    # The TOC listens for these calls
    def afterFlowable(self, flowable):
        if isinstance(flowable, TOCHeading):
            self.notify('TOCEntry',
                        (flowable.toc_level, flowable.toc_text, self.page))

    # ─── Cover page renderer ───
    def _draw_cover_page(self, c, doc):
        c.saveState()
        w, h = A4

        cover = _cover_path()
        if cover:
            try:
                c.drawImage(cover, 0, 0, width=w, height=h,
                            preserveAspectRatio=False, mask='auto')
                # Dark overlay for legible text
                c.setFillColor(colors.black)
                c.setFillAlpha(0.50)
                c.rect(0, 0, w, h, fill=1, stroke=0)
                c.setFillAlpha(1)
            except Exception:
                self._fallback_cover_bg(c, w, h)
        else:
            self._fallback_cover_bg(c, w, h)

        # Title block
        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold', 36)
        c.drawCentredString(w / 2, h / 2 + 2.4 * cm, 'Safety Management')
        c.drawCentredString(w / 2, h / 2 + 1.1 * cm, 'System Profile')

        # Thin divider line
        c.setStrokeColor(colors.white)
        c.setLineWidth(0.8)
        c.line(w / 2 - 4.5 * cm, h / 2 - 0.2 * cm, w / 2 + 4.5 * cm, h / 2 - 0.2 * cm)

        # Company name
        c.setFont('Helvetica-Bold', 22)
        c.drawCentredString(w / 2, h / 2 - 2.0 * cm,
                            (self.company.company_name or '—')[:60])

        # Date
        c.setFont('Helvetica', 12)
        c.drawCentredString(w / 2, h / 2 - 3.2 * cm,
                            datetime.now().strftime('%B %Y'))

        # Footer brand
        c.setFont('Helvetica', 10)
        c.setFillColor(colors.white)
        c.drawCentredString(w / 2, 1.8 * cm, 'PRODRIVE  ·  SMS Builder')

        c.restoreState()

    def _fallback_cover_bg(self, c, w, h):
        # Solid brand block with a lighter band — classy fallback
        c.setFillColor(BRAND_BLUE)
        c.rect(0, 0, w, h, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFillAlpha(0.06)
        c.rect(0, h * 0.55, w, 5 * cm, fill=1, stroke=0)
        c.setFillAlpha(1)

    # ─── Content-page header/footer ───
    def _draw_content_chrome(self, c, doc):
        c.saveState()
        w, h = A4

        # Header: logo top-right
        logo = _logo_path()
        if logo:
            try:
                c.drawImage(
                    logo,
                    w - self.rightMargin - 2.6 * cm,
                    h - self.topMargin + 0.6 * cm,
                    width=2.6 * cm, height=1.6 * cm,
                    preserveAspectRatio=True, mask='auto',
                )
            except Exception:
                pass

        # Header: company name (left)
        c.setFont('Helvetica', 8)
        c.setFillColor(MUTED)
        c.drawString(self.leftMargin, h - self.topMargin + 1.1 * cm,
                     (self.company.company_name or '').upper())

        # Header divider
        c.setStrokeColor(DIVIDER)
        c.setLineWidth(0.4)
        c.line(self.leftMargin, h - self.topMargin + 0.4 * cm,
               w - self.rightMargin, h - self.topMargin + 0.4 * cm)

        # Footer divider
        c.line(self.leftMargin, 1.7 * cm, w - self.rightMargin, 1.7 * cm)

        # Footer: doc title (left) + page number (right)
        c.setFont('Helvetica', 8)
        c.setFillColor(MUTED)
        c.drawString(self.leftMargin, 1.2 * cm,
                     'Safety Management System Profile')
        c.drawRightString(w - self.rightMargin, 1.2 * cm,
                          f'Page {doc.page}')

        c.restoreState()


# ── Styles ────────────────────────────────────────────────────
def _build_styles():
    base = getSampleStyleSheet()
    return {
        'h1': ParagraphStyle('h1', parent=base['Heading1'],
                             fontName='Helvetica-Bold', fontSize=20,
                             textColor=BRAND_BLUE, leading=24,
                             spaceBefore=4, spaceAfter=12),
        'h2': ParagraphStyle('h2', parent=base['Heading2'],
                             fontName='Helvetica-Bold', fontSize=13,
                             textColor=INK, leading=16,
                             spaceBefore=14, spaceAfter=6),
        'h3': ParagraphStyle('h3', parent=base['Heading3'],
                             fontName='Helvetica-Bold', fontSize=10,
                             textColor=MUTED, leading=12,
                             spaceBefore=8, spaceAfter=4),
        'body': ParagraphStyle('body', parent=base['BodyText'],
                               fontName='Helvetica', fontSize=10,
                               textColor=INK, leading=14,
                               spaceAfter=6, alignment=TA_JUSTIFY),
        'bullet': ParagraphStyle('bullet', parent=base['BodyText'],
                                 fontName='Helvetica', fontSize=10,
                                 textColor=INK, leading=14,
                                 leftIndent=14, bulletIndent=2, spaceAfter=3),
        'small': ParagraphStyle('small', parent=base['BodyText'],
                                fontName='Helvetica-Oblique', fontSize=9,
                                textColor=MUTED, leading=12, spaceAfter=4),
        'intro': ParagraphStyle('intro', parent=base['BodyText'],
                                fontName='Helvetica', fontSize=10,
                                textColor=INK, leading=15,
                                spaceAfter=10, alignment=TA_JUSTIFY),
        'toc_h1': ParagraphStyle('toc_h1', fontName='Helvetica-Bold',
                                 fontSize=11, leading=18, textColor=INK),
        'toc_h2': ParagraphStyle('toc_h2', fontName='Helvetica',
                                 fontSize=10, leading=14,
                                 textColor=MUTED, leftIndent=18),
    }


# ── Section/data helpers ──────────────────────────────────────
def _section_meta():
    return {s.key: (s.title, s.description or '') for s in Section.objects.all()}


def _bullets_from_options(options_qs, styles):
    """Turn a QuerySet of CheckboxOption into a list of bullet Paragraphs with rich text support."""
    items = []
    for opt in options_qs:
        text = (opt.description or opt.label or '').strip()
        if text:
            # Use rich text converter for descriptions
            flowables = html_to_flowables(f'• {text}', styles)
            items.extend(flowables)
    return items or [Paragraph('—', styles['small'])]


def _kv_table(rows):
    """Two-column key/value table."""
    if not rows:
        return None
    data = [[k, v if v not in (None, '') else '—'] for k, v in rows]
    t = Table(data, colWidths=[5.5 * cm, 11.0 * cm])
    t.setStyle(TableStyle([
        ('FONT',       (0, 0), (-1, -1), 'Helvetica', 10),
        ('FONT',       (0, 0), (0, -1), 'Helvetica-Bold', 10),
        ('TEXTCOLOR',  (0, 0), (0, -1), MUTED),
        ('TEXTCOLOR',  (1, 0), (1, -1), INK),
        ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW',  (0, 0), (-1, -2), 0.4, DIVIDER),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t


def _data_table(headers, rows, col_widths=None):
    """Header + data rows table (used for risk register, incidents, subs)."""
    if not rows:
        return Paragraph('No records recorded.', _build_styles()['small'])
    data = [headers] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, 0), ACCENT_BG),
        ('TEXTCOLOR',   (0, 0), (-1, 0), INK),
        ('FONT',        (0, 0), (-1, 0), 'Helvetica-Bold', 9),
        ('FONT',        (0, 1), (-1, -1), 'Helvetica', 9),
        ('TEXTCOLOR',   (0, 1), (-1, -1), INK),
        ('GRID',        (0, 0), (-1, -1), 0.3, DIVIDER),
        ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',  (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING',  (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    return t


def _intro_block(section_key, sec_meta, styles, fallback=''):
    """Create an introduction block with rich text support from section description."""
    title, desc = sec_meta.get(section_key, ('', ''))
    text = desc or fallback
    if not text:
        return None
    # Use rich text converter for section descriptions
    flowables = html_to_flowables(text, styles)
    return flowables


# ── MAIN ENTRY POINT ──────────────────────────────────────────
def build_company_pdf(company):
    """Return a BytesIO buffer containing the generated PDF."""
    buf = io.BytesIO()
    doc = CompanyPDFBuilder(buf, company)
    s = _build_styles()
    meta = _section_meta()

    op = getattr(company, 'operations', None)
    fl = getattr(company, 'fleet', None)
    rp = getattr(company, 'risk_profile', None)
    sp = getattr(company, 'subcontractor_profile', None)
    ip = getattr(company, 'incident_profile', None)

    story = []

    # ═══ Page 1 — Cover (drawn on canvas) ═══
    story.append(Spacer(1, 1))                       # 1px placeholder
    story.append(NextPageTemplate('Content'))
    story.append(PageBreak())

    # ═══ Page 2 — Table of Contents ═══
    story.append(Paragraph('Contents', s['h1']))
    toc = TableOfContents()
    toc.levelStyles = [s['toc_h1'], s['toc_h2']]
    story.append(toc)
    story.append(PageBreak())

    # ═══ Introduction ═══
    story.append(TOCHeading('Introduction', s['h1'], 0))
    intro_flowables = html_to_flowables(
        f"This Safety Management System (SMS) Profile presents a structured "
        f"overview of <b>{(company.company_name or 'the company')}</b>'s "
        f"operational, fleet, risk, subcontractor and incident-management "
        f"practices as recorded in the Prodrive platform. The contents are "
        f"derived from the company's own declarations and are intended for "
        f"internal review, due-diligence assessments and regulator engagement.",
        s,
    )
    story.extend(intro_flowables)
    story.append(Spacer(1, 10))

    # Company details block
    story.append(TOCHeading('Company Details', s['h2'], 1))
    address = ', '.join(filter(None, [
        company.address_street, company.city, company.state, company.postcode
    ])) or company.address or '—'
    story.append(_kv_table([
        ('Company name',    company.company_name),
        ('ABN',             company.abn),
        ('Business address', address),
        ('Contact person',  company.contact_person),
        ('Contact role',    company.contact_role),
        ('Contact email',   company.contact_email),
        ('Contact phone',   company.contact_phone),
    ]))
    story.append(PageBreak())

    # ═══ Operations ═══
    story.append(TOCHeading('Operations', s['h1'], 0))
    ops_flowables = html_to_flowables(
        "The following items describe the company's operational scope, "
        "regulatory accreditations, and workforce.",
        s,
    )
    story.extend(ops_flowables)

    # Work Types
    story.append(TOCHeading('Work Types', s['h2'], 1))
    intro = _intro_block('work_types', meta, s)
    if intro: story.extend(intro)
    if op:
        story.extend(_bullets_from_options(op.work_types.all(), s))
    else:
        story.append(Paragraph('—', s['small']))

    # Accreditations (with audit dates)
    story.append(TOCHeading('Accreditations', s['h2'], 1))
    intro = _intro_block('accreditations', meta, s)
    if intro: story.extend(intro)
    if op:
        entries = list(
            CompanyAccreditation.objects
            .filter(operation=op)
            .select_related('option')
        )
        if entries:
            for e in entries:
                text = (e.option.description or e.option.label or '').strip()
                if e.audit_date:
                    text += (f'  <font color="#64748b">'
                             f'(last audit: {e.audit_date.strftime("%d %b %Y")})'
                             f'</font>')
                flowables = html_to_flowables(f'• {text}', s)
                story.extend(flowables)
        else:
            story.append(Paragraph('—', s['small']))
    else:
        story.append(Paragraph('—', s['small']))

    # Operating Areas
    story.append(TOCHeading('Operating Areas', s['h2'], 1))
    intro = _intro_block('operating_areas', meta, s)
    if intro: story.extend(intro)
    if op:
        story.extend(_bullets_from_options(op.operating_areas.all(), s))
    else:
        story.append(Paragraph('—', s['small']))

    # Workforce
    story.append(TOCHeading('Workforce', s['h2'], 1))
    story.append(_kv_table([
        ('Typical operating hours',
            op.operating_hours if op else None),
        ('Number of employed drivers',
            str(op.num_drivers) if op and op.num_drivers is not None else None),
        ('Engages subcontractors',
            'Yes' if (sp and sp.engages_subcontractors) else 'No'),
    ]))
    story.append(PageBreak())

    # ═══ Fleet ═══
    story.append(TOCHeading('Fleet', s['h1'], 0))
    fleet_flowables = html_to_flowables(
        "The fleet composition, special cargo handling, and applicable NHVR "
        "vehicle configurations operated by the company.",
        s,
    )
    story.extend(fleet_flowables)

    # Fleet summary
    story.append(TOCHeading('Fleet Summary', s['h2'], 1))
    story.append(_kv_table([
        ('Total number of vehicles',
            str(fl.total_vehicles) if fl and fl.total_vehicles is not None else None),
        ('Maximum GVM in fleet',
            fl.max_gvm if fl else None),
        ('Average vehicle age',
            fl.average_age if fl else None),
    ]))

    # Vehicle Types
    story.append(TOCHeading('Vehicle Types', s['h2'], 1))
    intro = _intro_block('vehicle_types', meta, s)
    if intro: story.extend(intro)
    if fl:
        story.extend(_bullets_from_options(fl.vehicle_types.all(), s))
    else:
        story.append(Paragraph('—', s['small']))

    # Special Cargo
    story.append(TOCHeading('Special Cargo', s['h2'], 1))
    intro = _intro_block('special_cargo', meta, s)
    if intro: story.extend(intro)
    if fl:
        story.extend(_bullets_from_options(fl.special_cargo.all(), s))
    else:
        story.append(Paragraph('—', s['small']))

    # NHVR Configurations (grouped by category)
    story.append(TOCHeading('NHVR Vehicle Configurations', s['h2'], 1))
    intro = _intro_block('nhvr_configurations', meta, s)
    if intro: story.extend(intro)
    if fl:
        grouped = defaultdict(list)
        for opt in fl.nhvr_configurations.select_related('category').all():
            grouped[opt.category].append(opt)
        if grouped:
            for cat, opts in grouped.items():
                cat_title = (cat.description or cat.name) if cat else 'Other'
                # Use rich text for category description if it has HTML
                if cat and cat.description:
                    cat_flowables = html_to_flowables(cat_title, s)
                    story.extend(cat_flowables)
                else:
                    story.append(Paragraph(cat_title, s['h3']))
                for opt in opts:
                    text = (opt.description or opt.label or '').strip()
                    if text:
                        flowables = html_to_flowables(f'• {text}', s)
                        story.extend(flowables)
        else:
            story.append(Paragraph('—', s['small']))
    else:
        story.append(Paragraph('—', s['small']))
    story.append(PageBreak())

    # ═══ Risk ═══
    story.append(TOCHeading('Risk Management', s['h1'], 0))
    risk_flowables = html_to_flowables(
        "Documented safety policies, identified operational hazards and "
        "additional risk notes.",
        s,
    )
    story.extend(risk_flowables)

    story.append(TOCHeading('Safety Management Policies', s['h2'], 1))
    intro = _intro_block('safety_policies', meta, s)
    if intro: story.extend(intro)
    if rp:
        story.extend(_bullets_from_options(rp.safety_policies.all(), s))
    else:
        story.append(Paragraph('—', s['small']))

    story.append(TOCHeading('Risk Register', s['h2'], 1))
    hazard_rows = []
    for h in company.risk_hazards.all():
        # Use rich text for hazard descriptions and control measures
        hazard_desc_flowables = html_to_flowables(h.hazard_description or '—', s)
        control_measures_flowables = html_to_flowables(h.control_measures or '—', s)
        
        # For tables, we need simple Paragraphs, so extract the text
        hazard_desc = hazard_desc_flowables[0] if hazard_desc_flowables else Paragraph('—', s['body'])
        control_measures = control_measures_flowables[0] if control_measures_flowables else Paragraph('—', s['body'])
        
        hazard_rows.append([
            hazard_desc,
            h.likelihood or '—',
            h.consequence or '—',
            control_measures,
        ])
    story.append(_data_table(
        ['Hazard', 'Likelihood', 'Consequence', 'Control measures'],
        hazard_rows,
        col_widths=[5.5 * cm, 2.5 * cm, 2.5 * cm, 6.0 * cm],
    ))

    if rp and rp.additional_notes:
        story.append(TOCHeading('Additional Risk Notes', s['h2'], 1))
        additional_flowables = html_to_flowables(rp.additional_notes, s)
        story.extend(additional_flowables)
    story.append(PageBreak())

    # ═══ Subcontractors ═══
    story.append(TOCHeading('Subcontractor Management', s['h1'], 0))
    sub_flowables = html_to_flowables(
        "Whether the company engages subcontractors, the practices in place "
        "to ensure compliance, and the active subcontractor register.",
        s,
    )
    story.extend(sub_flowables)

    engages = bool(sp and sp.engages_subcontractors)
    story.append(_kv_table([
        ('Engages subcontractors', 'Yes' if engages else 'No'),
        ('Active subcontractors',
            str(sp.active_subcontractors) if sp and sp.active_subcontractors is not None else None),
        ('Primary engagement type',
            sp.primary_engagement_type if sp else None),
        ('Review frequency',
            sp.review_frequency if sp else None),
    ]))

    if engages:
        story.append(TOCHeading('Compliance Practices', s['h2'], 1))
        intro = _intro_block('compliance_practices', meta, s)
        if intro: story.extend(intro)
        story.extend(_bullets_from_options(sp.compliance_practices.all(), s))

        story.append(TOCHeading('Subcontractor Register', s['h2'], 1))
        sub_rows = []
        for sub in company.subcontractor_records.all():
            sub_rows.append([
                sub.subcontractor_name or '—',
                sub.abn or '—',
                sub.licence_type or '—',
                sub.contract_expiry.strftime('%d %b %Y') if sub.contract_expiry else '—',
            ])
        story.append(_data_table(
            ['Subcontractor', 'ABN', 'Licence', 'Contract expiry'],
            sub_rows,
            col_widths=[6.0 * cm, 3.5 * cm, 3.0 * cm, 4.0 * cm],
        ))

    if sp and sp.cor_procedures:
        story.append(TOCHeading('Chain of Responsibility', s['h2'], 1))
        cor_flowables = html_to_flowables(sp.cor_procedures, s)
        story.extend(cor_flowables)
    story.append(PageBreak())

    # ═══ Incidents ═══
    story.append(TOCHeading('Incident Management', s['h1'], 0))
    incident_flowables = html_to_flowables(
        "The company's incident reporting process, recent incident counts, "
        "and improvement actions taken.",
        s,
    )
    story.extend(incident_flowables)

    story.append(TOCHeading('Reporting Process', s['h2'], 1))
    intro = _intro_block('reporting_process', meta, s)
    if intro: story.extend(intro)
    if ip:
        story.extend(_bullets_from_options(ip.reporting_process.all(), s))
    else:
        story.append(Paragraph('—', s['small']))

    story.append(TOCHeading('Incident Summary', s['h2'], 1))
    story.append(_kv_table([
        ('Incidents in last 12 months',
            str(ip.incidents_last_12_months) if ip and ip.incidents_last_12_months is not None else '0'),
        ('Incidents in last 3 years',
            str(ip.incidents_last_3_years) if ip and ip.incidents_last_3_years is not None else '0'),
        ('Resulting injuries',
            str(ip.injuries_resulting) if ip and ip.injuries_resulting is not None else '0'),
    ]))

    story.append(TOCHeading('Significant Incidents', s['h2'], 1))
    inc_rows = []
    for inc in company.incident_records.all():
        # Use rich text for incident descriptions and outcomes
        inc_desc_flowables = html_to_flowables(inc.description or '—', s)
        inc_outcome_flowables = html_to_flowables(inc.outcome or '—', s)
        
        inc_desc = inc_desc_flowables[0] if inc_desc_flowables else Paragraph('—', s['body'])
        inc_outcome = inc_outcome_flowables[0] if inc_outcome_flowables else Paragraph('—', s['body'])
        
        inc_rows.append([
            inc.incident_date.strftime('%d %b %Y') if inc.incident_date else '—',
            inc.incident_type or '—',
            inc_desc,
            inc_outcome,
        ])
    story.append(_data_table(
        ['Date', 'Type', 'Description', 'Outcome'],
        inc_rows,
        col_widths=[2.5 * cm, 2.8 * cm, 6.0 * cm, 5.2 * cm],
    ))

    if ip and ip.improvement_actions:
        story.append(TOCHeading('Improvement Actions', s['h2'], 1))
        improvement_flowables = html_to_flowables(ip.improvement_actions, s)
        story.extend(improvement_flowables)

    # ─── Build (multiBuild needed for TOC) ───
    doc.multiBuild(story)
    buf.seek(0)
    return buf