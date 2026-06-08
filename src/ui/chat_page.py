"""
src/ui/chat_page.py — Chat page design only
All HTML rendering functions. No logic here.
"""


def user_bubble(text: str) -> str:
    """User message styled as a rounded box."""
    return f"""
    <div style="background:#1c1c1c;border:1px solid #2a2a2a;border-radius:14px;
                padding:12px 16px;margin:10px 0 4px;color:#e0e0e0;
                font-size:15px;font-weight:400;line-height:1.7;
                font-family:Inter,sans-serif;">{text}</div>"""


def answer_html(text: str) -> str:
    """Assistant answer — no box, plain flowing text."""
    return f"""
    <div style="color:#c8c8c8;font-size:15px;font-weight:400;
                line-height:1.85;padding:4px 0 10px;
                font-family:Inter,sans-serif;">{text}</div>"""


def card_html(r: dict) -> str:
    """Result card for one opportunity."""
    title    = r.get("title", "Untitled")
    rtype    = r.get("type", "Scheme")
    desc     = r.get("description", "")
    deadline = r.get("deadline", "")
    amount   = r.get("amount", "")
    elig     = r.get("eligibility", "")
    ministry = r.get("ministry", "")
    link     = r.get("link", "")

    meta = ""
    if deadline: meta += f'<span style="margin-right:14px"><b style="color:#aaa;font-weight:500">Apply by</b>&nbsp;{deadline}</span>'
    if amount:   meta += f'<span style="margin-right:14px"><b style="color:#aaa;font-weight:500">Amount</b>&nbsp;{amount}</span>'
    if elig:     meta += f'<span style="margin-right:14px"><b style="color:#aaa;font-weight:500">Eligibility</b>&nbsp;{elig}</span>'
    if ministry: meta += f'<span><b style="color:#aaa;font-weight:500">Company</b>&nbsp;{ministry}</span>'
    link_html = (f'<a href="{link}" target="_blank" style="color:#4a9eff;font-size:12px;'
                 f'text-decoration:none;display:inline-block;margin-top:8px;">'
                 f'Official Portal →</a>') if link else ""

    relevance = r.get("relevance", "")
    rel_color = {"High": "#22c55e", "Medium": "#f59e0b", "Low": "#666"}.get(relevance, "")
    rel_badge = (f'<span style="font-size:11px;font-weight:400;color:{rel_color};'
                 f'margin-left:8px;">{relevance}</span>') if relevance else ""

    return f"""
    <div style="background:#161616;border:1px solid #222;border-radius:10px;
                padding:14px 16px;margin:6px 0;">
        <div style="font-size:14px;font-weight:500;color:#ddd;margin-bottom:6px;">
            {title}
            <span style="font-size:11px;font-weight:400;color:#555;background:#1e1e1e;
                         border:1px solid #2a2a2a;border-radius:4px;
                         padding:2px 7px;margin-left:8px;">{rtype}</span>
            {rel_badge}
        </div>
        <div style="font-size:13px;color:#777;font-weight:400;
                    line-height:1.6;margin-bottom:8px;">{desc}</div>
        <div style="font-size:12px;color:#555;line-height:1.8;">{meta}</div>
        {link_html}
    </div>"""


def steps_html(done: list, active=None) -> str:
    """Processing steps animation — done steps show ✓, active shows icon + text."""
    html = '<div style="padding:4px 0;">'
    for icon, text in done:
        html += (f'<div style="display:flex;align-items:center;gap:8px;padding:2px 0;'
                 f'font-size:13px;color:#444;font-family:Inter,sans-serif;">'
                 f'<span style="color:#22c55e;font-size:11px;">✓</span>'
                 f'<span>{text}</span></div>')
    if active:
        icon, text = active
        html += (f'<div style="display:flex;align-items:center;gap:8px;padding:2px 0;'
                 f'font-size:13px;color:#888;font-family:Inter,sans-serif;">'
                 f'<span>{icon}</span><span>{text}…</span></div>')
    html += "</div>"
    return html


def welcome_screen() -> str:
    """Empty chat welcome message."""
    return """
    <div style="padding:3rem 0 1rem;">
        <div style="font-size:26px;font-weight:600;color:#eee;
                    letter-spacing:-0.03em;margin-bottom:8px;">
            Scheme Scout
        </div>
        <div style="font-size:15px;font-weight:400;color:#555;line-height:1.7;">
            Find Indian government scholarships, internships and schemes instantly.
        </div>
    </div>"""


def sidebar_logo(username: str) -> str:
    """Sidebar top logo + username."""
    return f"""
    <div style="padding:0.5rem 0.25rem 1rem;">
        <div style="font-size:16px;font-weight:600;color:#e0e0e0;
                    letter-spacing:-0.02em;">🔍 Scheme Scout</div>
        <div style="font-size:12px;color:#3a3a3a;margin-top:3px;">
            {username}
        </div>
    </div>"""


def sidebar_footer() -> str:
    """Sidebar bottom credit text."""
    return '<div style="font-size:11px;color:#2a2a2a;padding:4px 10px 8px;">Gemini · LangGraph · Tavily</div>'


def sources_html(sources: list) -> str:
    """Compact source links below results."""
    if not sources:
        return ""
    srcs = "  ·  ".join(
        f'<a href="{s}" style="color:#333;font-size:11px;text-decoration:none;">{s[:45]}</a>'
        for s in sources[:3])
    return f'<div style="margin-top:6px;color:#333;font-size:11px;">Sources: {srcs}</div>'


def results_count(n: int) -> str:
    return f'<div style="font-size:12px;color:#444;margin-bottom:6px;">{n} opportunities found</div>'