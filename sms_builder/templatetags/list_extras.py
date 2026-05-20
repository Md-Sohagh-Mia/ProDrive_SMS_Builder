from django import template

register = template.Library()


@register.filter
def split(value, sep=","):
    """Usage in template: {% for v in "Rare,Unlikely,Possible"|split:"," %}"""
    if value is None:
        return []
    return str(value).split(sep)


@register.filter
def get_item(dictionary, key):
    """Usage in template: {{ mydict|get_item:somekey }}"""
    if not dictionary:
        return None
    return dictionary.get(key) if hasattr(dictionary, 'get') else None