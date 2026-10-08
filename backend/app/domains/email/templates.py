"""Inline-styled HTML + plain-text email layout shared by every email.

Content is described with ``EmailContent`` and rendered into both formats, so the
text alternative never drifts from the HTML. All values are HTML-escaped; links are
only rendered for http(s) URLs.
"""

from dataclasses import dataclass, field
from html import escape
from string import Template

BRAND = "threecal."

_LAYOUT = Template(
    """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>
</head>
<body style="margin:0;padding:0;background:#f4f1ea;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1d1b17;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">$preheader</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f1ea;padding:32px 12px;">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border:1px solid #e4ded2;border-radius:14px;">
<tr><td style="padding:28px 32px 0 32px;font-size:20px;font-weight:700;letter-spacing:-0.02em;">$brand</td></tr>
<tr><td style="padding:20px 32px 0 32px;">
<h1 style="margin:0 0 12px 0;font-size:24px;line-height:1.25;font-weight:700;color:#1d1b17;">$heading</h1>
$paragraphs
</td></tr>
$details
$action
$links
<tr><td style="padding:24px 32px 28px 32px;font-size:12px;line-height:1.6;color:#8a8273;border-top:1px solid #efeae0;">$footer</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
"""
)


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    text: str
    html: str


@dataclass(frozen=True)
class EmailContent:
    subject: str
    heading: str
    paragraphs: list[str] = field(default_factory=list)
    # Label/value rows shown in a summary table.
    details: list[tuple[str, str]] = field(default_factory=list)
    # Primary call to action: (label, url).
    action: tuple[str, str] | None = None
    # Secondary links: (label, url).
    links: list[tuple[str, str]] = field(default_factory=list)
    preheader: str = ""
    footer: str = "Sent by threecal.com. You are receiving this because of an account or booking on threecal."


def _is_url(value: str) -> bool:
    return value.startswith(("https://", "http://"))


def _value_html(value: str) -> str:
    if _is_url(value):
        url = escape(value, quote=True)
        return f'<a href="{url}" style="color:#1d1b17;word-break:break-all;">{escape(value)}</a>'
    return escape(value).replace("\n", "<br>")


def render_email(content: EmailContent) -> RenderedEmail:
    paragraphs_html = "".join(
        f'<p style="margin:0 0 12px 0;font-size:15px;line-height:1.6;color:#3d3930;">{escape(paragraph).replace(chr(10), "<br>")}</p>'
        for paragraph in content.paragraphs
    )
    details_html = ""
    if content.details:
        rows = "".join(
            '<tr>'
            f'<td style="padding:8px 12px 8px 0;font-size:13px;color:#8a8273;vertical-align:top;white-space:nowrap;">{escape(label)}</td>'
            f'<td style="padding:8px 0;font-size:14px;color:#1d1b17;vertical-align:top;">{_value_html(value)}</td>'
            "</tr>"
            for label, value in content.details
        )
        details_html = (
            '<tr><td style="padding:8px 32px 0 32px;">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="background:#faf8f3;border:1px solid #efeae0;border-radius:10px;padding:8px 16px;">'
            f"{rows}</table></td></tr>"
        )
    action_html = ""
    if content.action and _is_url(content.action[1]):
        label, url = content.action
        action_html = (
            '<tr><td style="padding:24px 32px 0 32px;">'
            f'<a href="{escape(url, quote=True)}" style="display:inline-block;background:#1d1b17;color:#ffffff;'
            'text-decoration:none;font-size:14px;font-weight:600;padding:12px 20px;border-radius:999px;">'
            f"{escape(label)}</a></td></tr>"
        )
    links_html = ""
    links = [(label, url) for label, url in content.links if _is_url(url)]
    if links:
        items = " &middot; ".join(
            f'<a href="{escape(url, quote=True)}" style="color:#1d1b17;">{escape(label)}</a>' for label, url in links
        )
        links_html = f'<tr><td style="padding:16px 32px 0 32px;font-size:13px;color:#3d3930;">{items}</td></tr>'

    html = _LAYOUT.substitute(
        title=escape(content.subject),
        preheader=escape(content.preheader or content.heading),
        brand=escape(BRAND),
        heading=escape(content.heading),
        paragraphs=paragraphs_html,
        details=details_html,
        action=action_html,
        links=links_html,
        footer=escape(content.footer),
    )
    return RenderedEmail(subject=content.subject, text=render_text(content), html=html)


def render_text(content: EmailContent) -> str:
    lines: list[str] = [content.heading, ""]
    for paragraph in content.paragraphs:
        lines.extend([paragraph, ""])
    if content.details:
        width = max(len(label) for label, _ in content.details)
        for label, value in content.details:
            lines.append(f"{label.ljust(width)}  {value}")
        lines.append("")
    if content.action:
        lines.extend([f"{content.action[0]}: {content.action[1]}", ""])
    for label, url in content.links:
        lines.append(f"{label}: {url}")
    if content.links:
        lines.append("")
    lines.extend(["--", content.footer])
    return "\n".join(lines)
