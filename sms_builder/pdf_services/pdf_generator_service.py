import os
import re
from io import BytesIO
from datetime import date

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import Http404, JsonResponse

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ─────────────────────────────────────────────
#  Colour palette
# ─────────────────────────────────────────────
BRAND_DARK   = colors.HexColor("#1a2e4a")   # deep navy
BRAND_MID    = colors.HexColor("#2c5282")   # mid blue
BRAND_LIGHT  = colors.HexColor("#ebf4ff")   # pale blue tint
ACCENT       = colors.HexColor("#e53e3e")   # red accent for risk
GREY_LINE    = colors.HexColor("#cbd5e0")
TEXT_DARK    = colors.HexColor("#1a202c")
TEXT_MUTED   = colors.HexColor("#718096")
WHITE        = colors.white


# ─────────────────────────────────────────────
#  Style helpers
# ─────────────────────────────────────────────
def _styles():
    base = getSampleStyleSheet()

    def ps(name, **kw):
        return ParagraphStyle(name, **kw)

    return {
        "cover_company": ps(
            "CoverCompany",
            fontSize=26, leading=32, textColor=WHITE,
            fontName="Helvetica-Bold", alignment=TA_CENTER,
        ),
        "cover_sub": ps(
            "CoverSub",
            fontSize=13, leading=18, textColor=colors.HexColor("#bee3f8"),
            fontName="Helvetica", alignment=TA_CENTER,
        ),
        "cover_meta": ps(
            "CoverMeta",
            fontSize=10, leading=14, textColor=colors.HexColor("#a0aec0"),
            fontName="Helvetica", alignment=TA_CENTER,
        ),
        "section_heading": ps(
            "SectionHeading",
            fontSize=13, leading=18, textColor=WHITE,
            fontName="Helvetica-Bold", alignment=TA_LEFT,
            spaceAfter=0,
        ),
        "field_label": ps(
            "FieldLabel",
            fontSize=9, leading=12, textColor=TEXT_MUTED,
            fontName="Helvetica-Bold",
        ),
        "field_value": ps(
            "FieldValue",
            fontSize=10, leading=14, textColor=TEXT_DARK,
            fontName="Helvetica",
        ),
        "body": ps(
            "Body",
            fontSize=10, leading=15, textColor=TEXT_DARK,
            fontName="Helvetica", alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "bullet": ps(
            "Bullet",
            fontSize=10, leading=14, textColor=TEXT_DARK,
            fontName="Helvetica", leftIndent=12, bulletIndent=0,
            spaceAfter=2,
        ),
        "caption": ps(
            "Caption",
            fontSize=8, leading=11, textColor=TEXT_MUTED,
            fontName="Helvetica-Oblique",
        ),
        "table_header": ps(
            "TH",
            fontSize=9, leading=12, textColor=WHITE,
            fontName="Helvetica-Bold", alignment=TA_CENTER,
        ),
        "table_cell": ps(
            "TC",
            fontSize=9, leading=12, textColor=TEXT_DARK,
            fontName="Helvetica",
        ),
    }


# ─────────────────────────────────────────────
#  Reusable building blocks
# ─────────────────────────────────────────────
def _section_header(title, styles, story):
    """Dark navy banner with white section title."""
    tbl = Table([[Paragraph(title, styles["section_heading"])]],
                colWidths=[170 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), BRAND_DARK),
        ("TOPPADDING",  (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(Spacer(1, 8 * mm))
    story.append(tbl)
    story.append(Spacer(1, 4 * mm))


def _kv_table(rows, styles, story, col_widths=None):
    """Two-column label / value table."""
    if not rows:
        return
    col_widths = col_widths or [55 * mm, 115 * mm]
    data = [
        [Paragraph(label, styles["field_label"]),
         Paragraph(str(value) if value not in (None, "", [], {}) else "—", styles["field_value"])]
        for label, value in rows
    ]
    tbl = Table(data, colWidths=col_widths)
    tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS",(0, 0), (-1, -1), [WHITE, BRAND_LIGHT]),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.3, GREY_LINE),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 4 * mm))


def _bullet_list(items, styles, story, label=None):
    """Optional label then bulleted list."""
    if not items:
        story.append(Paragraph("No entries recorded.", styles["body"]))
        return
    if label:
        story.append(Paragraph(f"<b>{label}</b>", styles["body"]))
    for item in items:
        story.append(Paragraph(f"• {item}", styles["bullet"]))
    story.append(Spacer(1, 3 * mm))


def _prose(text, styles, story):
    story.append(Paragraph(text, styles["body"]))


def _hr(story):
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY_LINE,
                             spaceAfter=4, spaceBefore=4))


def _val(v):
    """Return a display-friendly string for any value."""
    if v in (None, "", [], {}):
        return "—"
    return str(v)


def _list_display(items):
    """Nicely join a list into a sentence."""
    if not items:
        return "None specified."
    if len(items) == 1:
        return items[0] + "."
    return ", ".join(items[:-1]) + f", and {items[-1]}."


# ─────────────────────────────────────────────
#  Cover page
# ─────────────────────────────────────────────
def _build_cover(company, styles, story):
    # Large coloured banner
    banner_data = [[
        Paragraph(company.company_name.upper(), styles["cover_company"]),
    ]]
    banner = Table(banner_data, colWidths=[170 * mm])
    banner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BRAND_DARK),
        ("TOPPADDING",    (0, 0), (-1, -1), 28),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 28),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
    ]))
    story.append(Spacer(1, 20 * mm))
    story.append(banner)
    story.append(Spacer(1, 6 * mm))

    sub = Table([[
        Paragraph("Safety Management System — Company Profile Document", styles["cover_sub"]),
    ]], colWidths=[170 * mm])
    sub.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BRAND_MID),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
    ]))
    story.append(sub)
    story.append(Spacer(1, 12 * mm))

    meta_rows = [
        ("ABN",               company.abn or "—"),
        ("Document Generated", date.today().strftime("%d %B %Y")),
        ("Status",            company.get_status_display()),
    ]
    if company.approved_at:
        meta_rows.append(("Approved On", company.approved_at.strftime("%d %B %Y")))

    meta_data = [[
        Paragraph(f"<b>{k}:</b>  {v}", styles["cover_meta"])
    ] for k, v in meta_rows]
    meta_tbl = Table(meta_data, colWidths=[170 * mm])
    meta_tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 10 * mm))
    _hr(story)
    _prose(
        "This document has been automatically generated from the company's registered profile "
        "within the Safety Management System (SMS) platform. It consolidates all submitted "
        "information across company details, operational activities, fleet composition, risk "
        "management, subcontractor arrangements, and incident history into a single reference "
        "document for review and compliance purposes.",
        styles, story,
    )
    story.append(Spacer(1, 6 * mm))


# ─────────────────────────────────────────────
#  Section 1 — Company Details
# ─────────────────────────────────────────────
def _build_company_details(company, user, styles, story):
    _section_header("1. Company Details", styles, story)
    _prose(
        f"{company.company_name} is registered on the platform under ABN {company.abn or '—'}. "
        "The following section outlines the core company information as submitted during "
        "registration, including contact details and the current account status.",
        styles, story,
    )

    # Company info
    address_parts = filter(None, [
        company.address_street, company.city, company.state, company.postcode
    ])
    full_address = ", ".join(address_parts) or company.address or "—"

    _kv_table([
        ("Company Name",   company.company_name),
        ("ABN",            company.abn),
        ("Address",        full_address),
        ("Account Status", company.get_status_display()),
        ("Registration Date", company.registration_date.strftime("%d %B %Y") if company.registration_date else "—"),
    ], styles, story)

    _prose("<b>Contact Information</b>", styles, story)
    _kv_table([
        ("Contact Person", company.contact_person or user.full_name or "—"),
        ("Phone",          company.contact_phone or user.phone or "—"),
        ("Email",          company.contact_email or user.email or "—"),
    ], styles, story)

    # _prose("<b>Platform Account</b>", styles, story)
    # _kv_table([
    #     ("Account Email",    user.email),
    #     ("Account Verified", "Yes" if user.is_verified else "No"),
    #     ("Terms Accepted",   "Yes" if user.terms_accepted else "No"),
    #     ("Declaration Accepted", "Yes" if company.declaration_accepted else "No"),
    # ], styles, story)

    if company.company_document:
        _prose(
            f"A supporting company document has been uploaded to the platform "
            f"({company.company_document.name.split('/')[-1]}).",
            styles, story,
        )


# ─────────────────────────────────────────────
#  Section 2 — Operations
# ─────────────────────────────────────────────
def _build_operations(company, styles, story):
    _section_header("2. Operational Profile", styles, story)

    try:
        ops = company.operations
    except Exception:
        _prose("No operational profile has been submitted for this company.", styles, story)
        return

    work_types = ops.work_types or []
    accreditations = ops.accreditations or []
    operating_areas = ops.operating_areas or []

    _prose(
        f"{company.company_name} operates across "
        f"{'multiple service categories' if len(work_types) > 1 else 'the following service category'}. "
        f"The company holds {'several' if len(accreditations) > 1 else 'the following'} "
        f"industry accreditation{'s' if len(accreditations) != 1 else ''} and services the "
        f"{'following geographic areas' if operating_areas else 'areas detailed below'}.",
        styles, story,
    )

    _kv_table([
        ("Operating Hours", ops.operating_hours or "—"),
        ("Number of Drivers", str(ops.num_drivers) if ops.num_drivers else "—"),
    ], styles, story)

    _bullet_list(work_types, styles, story, label="Types of Work Performed:")
    _bullet_list(accreditations, styles, story, label="Accreditations Held:")
    _bullet_list(operating_areas, styles, story, label="Operating Areas / Regions:")

    # Audit dates
    audit_rows = []
    if ops.audit_date_none:
        audit_rows.append(("Standard Audit Date", ops.audit_date_none.strftime("%d %B %Y")))
    if ops.audit_date_trucksafe:
        audit_rows.append(("TruckSafe Audit Date", ops.audit_date_trucksafe.strftime("%d %B %Y")))
    if ops.audit_date_wahva:
        audit_rows.append(("WAHVA Audit Date", ops.audit_date_wahva.strftime("%d %B %Y")))

    if audit_rows:
        _prose("<b>Scheduled Audit Dates</b>", styles, story)
        _kv_table(audit_rows, styles, story)


# ─────────────────────────────────────────────
#  Section 3 — Fleet
# ─────────────────────────────────────────────
def _build_fleet(company, styles, story):
    _section_header("3. Fleet Composition", styles, story)

    try:
        fleet = company.fleet
    except Exception:
        _prose("No fleet information has been submitted for this company.", styles, story)
        return

    vehicle_types  = fleet.vehicle_types or []
    special_cargo  = fleet.special_cargo or []
    nhvr           = fleet.nhvr_configurations or {}

    _prose(
        f"The fleet operated by {company.company_name} consists of "
        f"{fleet.total_vehicles or 0} registered vehicle{'s' if fleet.total_vehicles != 1 else ''}. "
        "The table below summarises key fleet metrics, followed by a breakdown of vehicle "
        "types, special cargo capabilities, and NHVR vehicle configurations.",
        styles, story,
    )

    _kv_table([
        ("Total Vehicles",      str(fleet.total_vehicles or "—")),
        ("Maximum GVM",         fleet.max_gvm or "—"),
        ("Average Vehicle Age", fleet.average_vehicle_age or "—"),
    ], styles, story)

    _bullet_list(vehicle_types, styles, story, label="Vehicle Types:")
    _bullet_list(special_cargo, styles, story, label="Special Cargo Capabilities:")

    # NHVR — dict of category → list
    if nhvr and isinstance(nhvr, dict):
        _prose("<b>NHVR Vehicle Configurations</b>", styles, story)
        _prose(
            "The following NHVR-regulated vehicle configurations are operated by this company, "
            "grouped by access class and combination type.",
            styles, story,
        )
        for category, configs in nhvr.items():
            story.append(Paragraph(f"<b>{category}</b>", styles["body"]))
            if isinstance(configs, list):
                for cfg in configs:
                    story.append(Paragraph(f"    • {cfg}", styles["bullet"]))
            story.append(Spacer(1, 2 * mm))
    elif nhvr and isinstance(nhvr, list):
        _bullet_list(nhvr, styles, story, label="NHVR Configurations:")


# ─────────────────────────────────────────────
#  Section 4 — Risk Profile
# ─────────────────────────────────────────────
def _build_risk(company, styles, story):
    _section_header("4. Risk Management Profile", styles, story)

    try:
        risk = company.risk_profile
    except Exception:
        _prose("No risk profile has been submitted for this company.", styles, story)
        return

    safety_policies = risk.safety_policies or []

    _prose(
        f"{company.company_name} has completed a risk and safety profile as part of its "
        "Safety Management System submission. This section details the safety policies in "
        "place, any identified hazards, and the controls established to manage those risks.",
        styles, story,
    )

    _bullet_list(safety_policies, styles, story, label="Safety Policies in Place:")

    if risk.additional_notes:
        _prose("<b>Additional Notes</b>", styles, story)
        _prose(risk.additional_notes, styles, story)

    # Risk hazards table
    hazards = list(company.risk_hazards.all())
    if hazards:
        story.append(Spacer(1, 4 * mm))
        _prose(
            f"The following {len(hazards)} hazard{'s have' if len(hazards) != 1 else ' has'} "
            "been identified and assessed, with corresponding control measures documented below.",
            styles, story,
        )

        LIKELIHOOD_SCORE = {
            "Rare": 1, "Unlikely": 2, "Possible": 3, "Likely": 4, "Almost Certain": 5
        }
        CONSEQUENCE_SCORE = {
            "Insignificant": 1, "Minor": 2, "Moderate": 3, "Major": 4, "Catastrophic": 5
        }

        def _risk_colour(l, c):
            score = LIKELIHOOD_SCORE.get(l, 1) * CONSEQUENCE_SCORE.get(c, 1)
            if score >= 12:
                return colors.HexColor("#fc8181")   # high — red
            if score >= 6:
                return colors.HexColor("#f6e05e")   # medium — yellow
            return colors.HexColor("#9ae6b4")        # low — green

        styles_th = styles["table_header"]
        styles_tc = styles["table_cell"]
        header = [
            Paragraph("Hazard Description", styles_th),
            Paragraph("Likelihood", styles_th),
            Paragraph("Consequence", styles_th),
            Paragraph("Control Measures", styles_th),
        ]
        rows = [header]
        row_colours = [("BACKGROUND", (0, 0), (-1, 0), BRAND_MID)]

        for i, h in enumerate(hazards, start=1):
            rc = _risk_colour(h.likelihood, h.consequence)
            rows.append([
                Paragraph(h.hazard_description or "—", styles_tc),
                Paragraph(h.likelihood or "—", styles_tc),
                Paragraph(h.consequence or "—", styles_tc),
                Paragraph(h.control_measures or "—", styles_tc),
            ])
            row_colours.append(("BACKGROUND", (1, i), (2, i), rc))

        tbl = Table(rows, colWidths=[55 * mm, 28 * mm, 28 * mm, 59 * mm])
        tbl.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
            ("GRID",          (0, 0), (-1, -1), 0.4, GREY_LINE),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, BRAND_LIGHT]),
            *row_colours,
        ]))
        story.append(tbl)
    else:
        _prose("No individual hazards have been recorded for this company.", styles, story)


# ─────────────────────────────────────────────
#  Section 5 — Subcontractors
# ─────────────────────────────────────────────
def _build_subcontractors(company, styles, story):
    _section_header("5. Subcontractor Management", styles, story)

    try:
        sub_profile = company.subcontractor_profile
    except Exception:
        _prose("No subcontractor profile has been submitted for this company.", styles, story)
        return

    engages = sub_profile.engages_subcontractors
    compliance_practices = sub_profile.compliance_practices or []

    _prose(
        f"{company.company_name} {'engages' if engages else 'does not currently engage'} "
        "subcontractors as part of its operations. "
        + (
            f"The company maintains a pool of approximately {sub_profile.active_subcontractors or 0} "
            f"active subcontractor{'s' if sub_profile.active_subcontractors != 1 else ''}, "
            f"primarily engaged on a {'\"' + sub_profile.primary_engagement_type + '\"' if sub_profile.primary_engagement_type else 'project'} basis, "
            f"with compliance reviews conducted {sub_profile.review_frequency or 'periodically'}."
            if engages else ""
        ),
        styles, story,
    )

    _kv_table([
        ("Engages Subcontractors",   "Yes" if engages else "No"),
        ("Active Subcontractors",    str(sub_profile.active_subcontractors or "—")),
        ("Primary Engagement Type",  sub_profile.primary_engagement_type or "—"),
        ("Review Frequency",         sub_profile.review_frequency or "—"),
    ], styles, story)

    _bullet_list(compliance_practices, styles, story, label="Compliance Practices Applied:")

    if sub_profile.cor_procedures:
        _prose("<b>Chain of Responsibility (CoR) Procedures</b>", styles, story)
        _prose(sub_profile.cor_procedures, styles, story)

    # Subcontractor records table
    records = list(company.subcontractor_records.all())
    if records:
        _prose(
            f"The following {len(records)} subcontractor record{'s are' if len(records) != 1 else ' is'} "
            "currently registered against this company's profile.",
            styles, story,
        )
        styles_th = styles["table_header"]
        styles_tc = styles["table_cell"]
        header = [
            Paragraph("Subcontractor Name", styles_th),
            Paragraph("ABN", styles_th),
            Paragraph("Licence Type", styles_th),
            Paragraph("Contract Expiry", styles_th),
        ]
        rows = [header]
        for r in records:
            rows.append([
                Paragraph(r.subcontractor_name or "—", styles_tc),
                Paragraph(r.abn or "—", styles_tc),
                Paragraph(r.licence_type or "—", styles_tc),
                Paragraph(r.contract_expiry.strftime("%d %b %Y") if r.contract_expiry else "—", styles_tc),
            ])
        tbl = Table(rows, colWidths=[60 * mm, 32 * mm, 40 * mm, 38 * mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), BRAND_MID),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
            ("GRID",          (0, 0), (-1, -1), 0.4, GREY_LINE),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, BRAND_LIGHT]),
        ]))
        story.append(tbl)
    else:
        _prose("No individual subcontractor records have been registered.", styles, story)


# ─────────────────────────────────────────────
#  Section 6 — Incidents
# ─────────────────────────────────────────────
def _build_incidents(company, styles, story):
    _section_header("6. Incident History & Reporting", styles, story)

    try:
        inc_profile = company.incident_profile
    except Exception:
        _prose("No incident profile has been submitted for this company.", styles, story)
        return

    reporting_process = inc_profile.reporting_process or []

    _prose(
        f"This section documents {company.company_name}'s incident reporting framework and "
        "historical incident data as submitted to the SMS platform. The figures below reflect "
        "self-reported incident counts and should be read alongside the improvement actions "
        "taken by the company.",
        styles, story,
    )

    _kv_table([
        ("Incidents (Last 12 Months)",  str(inc_profile.incidents_last_12_months or 0)),
        ("Incidents (Last 3 Years)",    str(inc_profile.incidents_last_3_years or 0)),
        ("Injuries Resulting",          str(inc_profile.injuries_resulting or 0)),
    ], styles, story)

    _bullet_list(reporting_process, styles, story, label="Incident Reporting Process:")

    if inc_profile.improvement_actions:
        _prose("<b>Improvement Actions Taken</b>", styles, story)
        _prose(inc_profile.improvement_actions, styles, story)

    # Incident records table
    records = list(company.incident_records.all())
    if records:
        _prose(
            f"The following {len(records)} incident record{'s have' if len(records) != 1 else ' has'} "
            "been logged on the platform.",
            styles, story,
        )
        styles_th = styles["table_header"]
        styles_tc = styles["table_cell"]

        TYPE_COLOURS = {
            "Accident":         colors.HexColor("#fc8181"),
            "Injury":           colors.HexColor("#f6ad55"),
            "Near-Miss":        colors.HexColor("#f6e05e"),
            "Property Damage":  colors.HexColor("#90cdf4"),
            "Dangerous Goods":  colors.HexColor("#d6bcfa"),
        }

        header = [
            Paragraph("Date", styles_th),
            Paragraph("Type", styles_th),
            Paragraph("Description", styles_th),
            Paragraph("Outcome", styles_th),
        ]
        rows = [header]
        row_bg = [("BACKGROUND", (0, 0), (-1, 0), BRAND_MID)]

        for i, r in enumerate(records, start=1):
            tc = TYPE_COLOURS.get(r.incident_type, WHITE)
            rows.append([
                Paragraph(r.incident_date.strftime("%d %b %Y") if r.incident_date else "—", styles_tc),
                Paragraph(r.incident_type or "—", styles_tc),
                Paragraph(r.description or "—", styles_tc),
                Paragraph(r.outcome or "—", styles_tc),
            ])
            row_bg.append(("BACKGROUND", (1, i), (1, i), tc))

        tbl = Table(rows, colWidths=[24 * mm, 28 * mm, 72 * mm, 46 * mm])
        tbl.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
            ("GRID",          (0, 0), (-1, -1), 0.4, GREY_LINE),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, BRAND_LIGHT]),
            *row_bg,
        ]))
        story.append(tbl)
    else:
        _prose("No individual incident records have been logged.", styles, story)


# ─────────────────────────────────────────────
#  Page header / footer callback
# ─────────────────────────────────────────────
def _make_canvas_callback(company_name):
    def _on_page(canvas, doc):
        canvas.saveState()
        w, h = A4

        # Header bar
        canvas.setFillColor(BRAND_DARK)
        canvas.rect(0, h - 20 * mm, w, 20 * mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(15 * mm, h - 12 * mm, company_name.upper())
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(w - 15 * mm, h - 12 * mm,
                               "Safety Management System — Company Profile")

        # Footer bar
        canvas.setFillColor(BRAND_DARK)
        canvas.rect(0, 0, w, 12 * mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(15 * mm, 4 * mm,
                          f"Generated: {date.today().strftime('%d %B %Y')}  |  CONFIDENTIAL")
        canvas.drawRightString(w - 15 * mm, 4 * mm,
                               f"Page {doc.page}")
        canvas.restoreState()

    return _on_page


# ─────────────────────────────────────────────
#  Main generator
# ─────────────────────────────────────────────
def build_company_pdf(company):
    """Return a BytesIO containing the rendered PDF."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=28 * mm,
        bottomMargin=22 * mm,
    )

    styles = _styles()
    story  = []
    user   = company.user

    _build_cover(company, styles, story)
    _build_company_details(company, user, styles, story)
    _build_operations(company, styles, story)
    _build_fleet(company, styles, story)
    _build_risk(company, styles, story)
    _build_subcontractors(company, styles, story)
    _build_incidents(company, styles, story)

    # Closing statement
    _section_header("Declaration & Sign-Off", styles, story)
    _prose(
        f"This document was automatically compiled from data submitted by {company.company_name} "
        "through the Safety Management System platform. All information is self-reported and "
        "subject to verification by the relevant authority. This document is confidential and "
        "intended solely for the use of the company and authorised reviewers.",
        styles, story,
    )
    if user.terms_accepted and user.terms_accepted_at:
        _prose(
            f"The company's authorised representative accepted the platform's terms and conditions "
            f"on {user.terms_accepted_at.strftime('%d %B %Y')}.",
            styles, story,
        )

    doc.build(
        story,
        onFirstPage=_make_canvas_callback(company.company_name),
        onLaterPages=_make_canvas_callback(company.company_name),
    )
    buffer.seek(0)
    return buffer