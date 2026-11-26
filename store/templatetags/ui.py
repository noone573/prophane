from django import template
from django.templatetags.static import static
from django.utils.html import format_html

register = template.Library()

STATUS_TONES = {
    # reservations
    'pending': 'warn',
    'pending_approval': 'info',
    'approved': 'ok',
    'rejected': 'bad',
    'cancelled': '',
    # seller accounts
    'suspended': 'bad',
}


@register.simple_tag
def icon(name, size=''):
    cls = f'icon icon-{size}' if size else 'icon'
    return format_html(
        '<svg class="{}" aria-hidden="true" focusable="false"><use href="{}#{}"></use></svg>',
        cls, static('img/icons.svg'), name,
    )


@register.simple_tag
def status_badge(status, label=None):
    tone = STATUS_TONES.get(status, '')
    cls = f'badge badge-{tone}' if tone else 'badge'
    return format_html('<span class="{}">{}</span>', cls, label or status.replace('_', ' ').capitalize())


@register.simple_tag
def order_label(order):
    """Customer-facing wording for a reservation's state."""
    return {
        'pending': 'Ready for pickup',
        'pending_approval': 'Being verified',
        'approved': 'Completed',
        'rejected': 'Pickup photo re-check',
        'cancelled': 'Cancelled',
    }.get(order.status, order.get_status_display())


@register.filter
def peso(value):
    try:
        return f'₱{float(value):,.2f}'
    except (TypeError, ValueError):
        return ''


@register.simple_tag(takes_context=True)
def current(context, *url_names):
    """aria-current="page" when the request matches one of the URL names."""
    request = context.get('request')
    match = getattr(request, 'resolver_match', None)
    if match and match.url_name in url_names:
        return format_html('aria-current="page"')
    return ''
