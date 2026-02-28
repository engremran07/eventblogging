"""
Custom template tags for reusable UI components.
Usage: {% load components %}
"""

from django import template

register = template.Library()


@register.inclusion_tag("components/card.html")
def card(title="", icon="", content="", css_class=""):
    """Render a card component with optional icon and title."""
    return {
        "title": title,
        "icon": icon,
        "content": content,
        "css_class": css_class,
    }


@register.inclusion_tag("components/badge.html")
def badge(text="", color="primary", size="md"):
    """Render a badge/pill component."""
    return {
        "text": text,
        "color": color,
        "size": size,
    }


@register.inclusion_tag("components/alert.html")
def alert(message="", alert_type="info", dismissible=True):
    """Render an alert/notification component."""
    return {
        "message": message,
        "alert_type": alert_type,
        "dismissible": dismissible,
    }


@register.inclusion_tag("components/stat_widget.html")
def stat_widget(label="", value="", icon="", trend="", css_class=""):
    """Render a statistics widget for dashboards."""
    return {
        "label": label,
        "value": value,
        "icon": icon,
        "trend": trend,
        "css_class": css_class,
    }


@register.inclusion_tag("components/button.html")
def button(text="", url="", type="primary", size="md", css_class="", onclick=""):
    """Render a button component."""
    return {
        "text": text,
        "url": url,
        "type": type,
        "size": size,
        "css_class": css_class,
        "onclick": onclick,
    }


@register.inclusion_tag("components/toast.html")
def toast(message="", toast_type="info", duration=3000):
    """Render a toast/notification component (used with Alpine.js)."""
    return {
        "message": message,
        "toast_type": toast_type,
        "duration": duration,
    }


@register.inclusion_tag("components/modal.html")
def modal(id="", title="", size="md", css_class=""):
    """Render a modal component."""
    return {
        "id": id,
        "title": title,
        "size": size,
        "css_class": css_class,
    }


@register.inclusion_tag("components/data_table.html")
def data_table(headers=None, rows=None, css_class=""):
    """Render a data table component."""
    if headers is None:
        headers = []
    if rows is None:
        rows = []

    return {
        "headers": headers,
        "rows": rows,
        "css_class": css_class,
    }


@register.simple_tag
def active_link(request, url):
    """Return 'active' class if the current request path matches the URL."""
    if request.path == url or request.path.startswith(url):
        return "active"
    return ""


@register.filter
def truncate_words(value, num_words=20):
    """Truncate text to a number of words."""
    words = value.split()
    if len(words) > num_words:
        return " ".join(words[:num_words]) + "..."
    return value
