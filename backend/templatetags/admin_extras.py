# Add to backend/templatetags/list_extras.py
import json
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def json_dump(opt):
    """Serialize a CheckboxOption for inline onclick handlers."""
    return mark_safe(json.dumps({
        'id': opt.id,
        'label': opt.label,
        'value': opt.value,
        'description': opt.description or '',
        'order': opt.order,
        'is_active': opt.is_active,
        'requires_date': getattr(opt, 'requires_date', False),
        'category_id': opt.category_id,
    }))

@register.filter
def json_dump_cat(cat):
    return mark_safe(json.dumps({
        'id': cat.id,
        'name': cat.name,
        'description': cat.description or '',
        'order': cat.order,
        'is_active': cat.is_active,
    }))