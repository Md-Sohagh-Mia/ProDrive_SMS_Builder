import re
import shutil
import os
import subprocess
import tempfile
import time
from collections import defaultdict
from django.conf import settings
from django.core.files import File
from django.http import Http404
from docx import Document
from .pdf_builder import build_company_pdf
from .models import Section, CompanyDocument, CompanyAccreditation






# ══════════════════════════════════════════════════════════════
# STEP FORMATTERS
# ══════════════════════════════════════════════════════════════

def format_step1_data(data):
    """Validates and formats Company Details (Step 1)."""
    abn_raw = data.get('abn', '')
    abn_clean = re.sub(r'\s+', '', str(abn_raw)) if abn_raw else None

    return {
        'company_name': data.get('company_name'),
        'abn': abn_clean,
        'address_street': data.get('address_street'),
        'city': data.get('city'),
        'state': data.get('state'),
        'postcode': data.get('postcode'),
        'contact_phone': data.get('contact_phone'),
        'contact_email': data.get('contact_email'),
        'contact_person': data.get('contact_person'),
        'contact_role': data.get('contact_role'),
        'declaration_accepted': data.get('declaration_accepted', False),
    }


def format_step2_data(data):
    """Scalar fields for CompanyOperation. M2M is handled in the view."""
    try:
        num_drivers = int(data.get('num_drivers', 0))
    except (ValueError, TypeError):
        num_drivers = 0

    return {
        'operating_hours': data.get('operating_hours'),
        'num_drivers': num_drivers,
    }


def format_step3_data(data):
    """Scalar fields for CompanyFleet. M2M is handled in the view."""
    try:
        total_vehicles = int(data.get('total_vehicles', 0))
    except (ValueError, TypeError):
        total_vehicles = 0

    return {
        'total_vehicles': total_vehicles,
        'max_gvm': data.get('max_gvm'),
        'average_age': data.get('average_age'),
    }


def format_step4_static_data(data):
    """Scalar fields for CompanyRiskProfile. M2M is handled in the view."""
    return {
        'additional_notes': data.get('risk_notes', ''),
    }


def format_step4_dynamic_data(data):
    """Dynamic risk hazard rows."""
    return data.get('risk_hazards', [])


def format_step5_static_data(data):
    """Scalar fields for CompanySubcontractorProfile. M2M is handled in the view."""
    def parse_int(val):
        try:
            return int(val) if val and str(val).strip() != "" else 0
        except (ValueError, TypeError):
            return 0

    return {
        'engages_subcontractors': data.get('engages_subcontractors', False),
        'active_subcontractors': parse_int(data.get('active_subcontractors')),
        'primary_engagement_type': data.get('primary_engagement_type', ''),
        'review_frequency': data.get('review_frequency', ''),
        'cor_procedures': data.get('cor_procedures', ''),
    }


def format_step5_dynamic_data(data):
    """Dynamic subcontractor record rows."""
    return data.get('subcontractor_records', [])


def format_step6_static_data(data):
    """Scalar fields for CompanyIncidentProfile. M2M is handled in the view."""
    def parse_int(val):
        try:
            return int(val) if val and str(val).strip() != "" else 0
        except (ValueError, TypeError):
            return 0

    return {
        'incidents_last_12_months': parse_int(data.get('incidents_last_12_months')),
        'incidents_last_3_years': parse_int(data.get('incidents_last_3_years')),
        'injuries_resulting': parse_int(data.get('injuries_resulting')),
        'improvement_actions': data.get('improvement_actions', ''),
    }


def format_step6_dynamic_data(data):
    """Dynamic incident record rows."""
    return data.get('incident_records', [])


# ══════════════════════════════════════════════════════════════
# LIBREOFFICE LOOKUP (leave commented if defined elsewhere)
# ══════════════════════════════════════════════════════════════

# def get_libreoffice():
#     if os.name == "nt":
#         possible_paths = [
#             r"C:\Program Files\LibreOffice\program\soffice.exe",
#             r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
#         ]
#         for path in possible_paths:
#             if os.path.exists(path):
#                 return path
#     return shutil.which("soffice") or shutil.which("libreoffice")


# ══════════════════════════════════════════════════════════════
# PDF GENERATION
# ══════════════════════════════════════════════════════════════

def _joined_descriptions(qs):
    """Render an iterable of CheckboxOption as a bulleted list of descriptions."""
    lines = []
    for opt in qs:
        text = (opt.description or opt.label or '').strip()
        if text:
            lines.append(f"• {text}")
    return "\n".join(lines) if lines else "—"


def _build_pdf_replacements(company):
    """Build the placeholder → value map used when filling master_template.docx.

    For checkbox-style data we substitute each selected option's *description*
    (falling back to its label if no description has been set by the admin).
    """
    # Build address
    address_parts = [company.address_street, company.city, company.state, company.postcode]
    business_location = ", ".join(filter(None, address_parts))
    if not business_location:
        business_location = company.address or "Location not provided"

    op = getattr(company, 'operations', None)
    fl = getattr(company, 'fleet', None)
    rp = getattr(company, 'risk_profile', None)
    sp = getattr(company, 'subcontractor_profile', None)
    ip = getattr(company, 'incident_profile', None)

    # Accreditations — include audit dates inline
    accreditation_lines = []
    if op:
        for entry in CompanyAccreditation.objects.filter(operation=op).select_related('option'):
            text = (entry.option.description or entry.option.label or '').strip()
            if entry.audit_date:
                text = f"{text} (last audit: {entry.audit_date.strftime('%d %b %Y')})"
            if text:
                accreditation_lines.append(f"• {text}")
    accreditations_block = "\n".join(accreditation_lines) if accreditation_lines else "—"

    # NHVR — grouped by category, category title from category.description (fallback to name)
    nhvr_blocks = []
    if fl:
        grouped = defaultdict(list)
        for opt in fl.nhvr_configurations.select_related('category').all():
            grouped[opt.category].append((opt.description or opt.label or '').strip())
        for cat, items in grouped.items():
            cat_title = (cat.description or cat.name) if cat else "NHVR Configurations"
            joined = "\n".join(f"  • {it}" for it in items if it)
            nhvr_blocks.append(f"{cat_title}\n{joined}")
    nhvr_block = "\n\n".join(nhvr_blocks) if nhvr_blocks else "—"

    # Section descriptions (admin-managed — used as PDF subheaders)
    section_descs = {s.key: (s.description or s.title) for s in Section.objects.all()}

    return {
        "[INSERT COMPANY NAME]":     company.company_name or "Company Name Missing",
        "[INSERT BUSINESS LOCATION]": business_location,

        # Section-level descriptions
        "[SECTION WORK TYPES]":           section_descs.get('work_types', ''),
        "[SECTION ACCREDITATIONS]":       section_descs.get('accreditations', ''),
        "[SECTION OPERATING AREAS]":      section_descs.get('operating_areas', ''),
        "[SECTION VEHICLE TYPES]":        section_descs.get('vehicle_types', ''),
        "[SECTION SPECIAL CARGO]":        section_descs.get('special_cargo', ''),
        "[SECTION NHVR]":                 section_descs.get('nhvr_configurations', ''),
        "[SECTION SAFETY POLICIES]":      section_descs.get('safety_policies', ''),
        "[SECTION COMPLIANCE PRACTICES]": section_descs.get('compliance_practices', ''),
        "[SECTION REPORTING PROCESS]":    section_descs.get('reporting_process', ''),

        # Selected-option descriptions per group
        "[INSERT WORK TYPES]":           _joined_descriptions(op.work_types.all())          if op else "—",
        "[INSERT ACCREDITATIONS]":       accreditations_block,
        "[INSERT OPERATING AREAS]":      _joined_descriptions(op.operating_areas.all())     if op else "—",
        "[INSERT VEHICLE TYPES]":        _joined_descriptions(fl.vehicle_types.all())       if fl else "—",
        "[INSERT SPECIAL CARGO]":        _joined_descriptions(fl.special_cargo.all())       if fl else "—",
        "[INSERT NHVR CONFIGURATIONS]":  nhvr_block,
        "[INSERT SAFETY POLICIES]":      _joined_descriptions(rp.safety_policies.all())     if rp else "—",
        "[INSERT COMPLIANCE PRACTICES]": _joined_descriptions(sp.compliance_practices.all()) if sp else "—",
        "[INSERT REPORTING PROCESS]":    _joined_descriptions(ip.reporting_process.all())   if ip else "—",
    }


def generate_company_document_for_company(company):
    """
    Build the SMS profile PDF from scratch and save it as a CompanyDocument
    of type FULL_DOC. Returns the saved CompanyDocument object.
    """
    pdf_buffer = build_company_pdf(company)

    safe_name = re.sub(r'[^\w\-]', '_', company.company_name or 'Company')
    file_name = f'{safe_name}_SMS_Document.pdf'

    # Replace any previous FULL_DOC for this company
    CompanyDocument.objects.filter(company=company, doc_type='FULL_DOC').delete()

    doc_obj = CompanyDocument.objects.create(
        company=company,
        file=File(pdf_buffer, name=file_name),
        name=file_name,
        doc_type='FULL_DOC',
    )
    return doc_obj

def get_libreoffice():
    return shutil.which("soffice")

