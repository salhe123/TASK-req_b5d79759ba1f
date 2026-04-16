import re


def sanitize_highlight(html_str):
    """Allow only <mark> and </mark> tags, escaping everything else."""
    if not html_str:
        return html_str
    # Temporarily replace valid <mark> tags with placeholders
    html_str = html_str.replace('<mark>', '\x00MARK_OPEN\x00')
    html_str = html_str.replace('</mark>', '\x00MARK_CLOSE\x00')
    # Escape all remaining HTML
    html_str = (html_str
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#x27;'))
    # Restore <mark> tags
    html_str = html_str.replace('\x00MARK_OPEN\x00', '<mark>')
    html_str = html_str.replace('\x00MARK_CLOSE\x00', '</mark>')
    return html_str
