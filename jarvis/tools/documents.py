"""Document & artifact builders: PowerPoint, PDF, and multi-page websites.

These let JARVIS produce finished deliverables in one shot instead of dictating
raw bytes through ``write_file`` (which can't emit binary .pptx/.pdf). Heavy
deps are imported lazily so the package stays import-safe without them; install
with ``pip install -e ".[documents]"`` (python-pptx + reportlab).

Inputs are plain JSON-friendly structures so any model can drive them:

- ``create_pptx``: slides = [{"title": str, "bullets": [str, ...], "notes"?: str}]
- ``create_pdf``:  blocks = [{"type": "heading"|"subheading"|"text"|"bullets",
                              "text"|"items": ...}]
- ``create_website``: pages = [{"filename": str, "title": str, "body_html": str}]
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from jarvis.tools.base import Tool, ToolError
from jarvis.utils.safety import SafetyGate


def _resolve(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


def _coerce(value: Any, what: str) -> Any:
    """Accept either a real list/dict or a JSON string of one (models vary)."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise ToolError(f"{what} must be JSON; could not parse: {exc}") from exc
    return value


# --------------------------------------------------------------------------- #
# PowerPoint
# --------------------------------------------------------------------------- #
def _build_pptx(path: str, title: str, slides: Any, subtitle: str = "") -> str:
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
    except ImportError as exc:  # pragma: no cover - dep missing
        raise ToolError(
            "python-pptx not installed. Run: pip install python-pptx"
        ) from exc

    slides = _coerce(slides, "slides")
    if not isinstance(slides, list):
        raise ToolError("slides must be a list of {title, bullets} objects")

    prs = Presentation()

    # Title slide.
    title_layout = prs.slide_layouts[0]
    s = prs.slides.add_slide(title_layout)
    s.shapes.title.text = title
    if subtitle and len(s.placeholders) > 1:
        s.placeholders[1].text = subtitle

    # Content slides.
    bullet_layout = prs.slide_layouts[1]
    for i, slide in enumerate(slides, 1):
        if not isinstance(slide, dict):
            raise ToolError(f"slide {i} must be an object with title/bullets")
        s = prs.slides.add_slide(bullet_layout)
        s.shapes.title.text = str(slide.get("title", f"Slide {i}"))
        body = s.placeholders[1].text_frame
        body.clear()
        bullets = slide.get("bullets") or []
        if isinstance(bullets, str):
            bullets = [bullets]
        for j, bullet in enumerate(bullets):
            para = body.paragraphs[0] if j == 0 else body.add_paragraph()
            para.text = str(bullet)
            para.font.size = Pt(18)
        notes = slide.get("notes")
        if notes:
            s.notes_slide.notes_text_frame.text = str(notes)

    p = _resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(p))
    return f"created PowerPoint with {len(slides) + 1} slides at {p}"


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #
def _build_pdf(path: str, title: str, blocks: Any) -> str:
    try:
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import (
            ListFlowable,
            ListItem,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
        )
    except ImportError as exc:  # pragma: no cover - dep missing
        raise ToolError("reportlab not installed. Run: pip install reportlab") from exc

    blocks = _coerce(blocks, "blocks")
    if not isinstance(blocks, list):
        raise ToolError("blocks must be a list of {type, text|items} objects")

    p = _resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(p), pagesize=letter, title=title)
    styles = getSampleStyleSheet()
    story: list[Any] = []

    if title:
        story.append(Paragraph(title, styles["Title"]))
        story.append(Spacer(1, 12))

    for blk in blocks:
        if not isinstance(blk, dict):
            raise ToolError("each block must be an object with a 'type'")
        kind = str(blk.get("type", "text")).lower()
        if kind == "heading":
            story.append(Spacer(1, 8))
            story.append(Paragraph(str(blk.get("text", "")), styles["Heading1"]))
        elif kind == "subheading":
            story.append(Paragraph(str(blk.get("text", "")), styles["Heading2"]))
        elif kind in ("bullets", "list"):
            items = blk.get("items") or []
            if isinstance(items, str):
                items = [items]
            story.append(
                ListFlowable(
                    [ListItem(Paragraph(str(it), styles["BodyText"])) for it in items],
                    bulletType="bullet",
                )
            )
        else:  # text / paragraph
            story.append(Paragraph(str(blk.get("text", "")), styles["BodyText"]))
        story.append(Spacer(1, 6))

    doc.build(story)
    return f"created PDF with {len(blocks)} blocks at {p}"


# --------------------------------------------------------------------------- #
# Website
# --------------------------------------------------------------------------- #
_DEFAULT_CSS = """\
:root { --fg:#1a1a2e; --muted:#555; --accent:#0066ff; --bg:#ffffff; }
* { box-sizing: border-box; }
body { margin:0; font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
  color:var(--fg); background:var(--bg); line-height:1.6; }
header { background:var(--fg); color:#fff; padding:1rem 2rem; }
header nav a { color:#fff; margin-right:1.25rem; text-decoration:none; opacity:.9; }
header nav a:hover { opacity:1; text-decoration:underline; }
main { max-width:960px; margin:0 auto; padding:2rem; }
h1,h2,h3 { line-height:1.25; }
a { color:var(--accent); }
.card { border:1px solid #e3e3e3; border-radius:12px; padding:1.25rem; margin:1rem 0;
  box-shadow:0 1px 3px rgba(0,0,0,.05); }
footer { color:var(--muted); text-align:center; padding:2rem; font-size:.9rem; }
button,.btn { background:var(--accent); color:#fff; border:0; padding:.6rem 1.1rem;
  border-radius:8px; cursor:pointer; text-decoration:none; display:inline-block; }
"""

_PAGE_TEMPLATE = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="styles.css">
</head>
<body>
<header><nav>{nav}</nav></header>
<main>
{body}
</main>
<footer>{footer}</footer>
</body>
</html>
"""


def _build_website(
    directory: str, pages: Any, site_name: str = "My Site", css: str = ""
) -> str:
    pages = _coerce(pages, "pages")
    if not isinstance(pages, list) or not pages:
        raise ToolError("pages must be a non-empty list of {filename, title, body_html}")

    root = _resolve(directory)
    root.mkdir(parents=True, exist_ok=True)

    # Build a shared nav from page titles.
    nav_links = []
    for pg in pages:
        fn = str(pg.get("filename", "")).strip()
        if not fn:
            raise ToolError("each page needs a 'filename' (e.g. index.html)")
        nav_links.append(f'<a href="{fn}">{pg.get("title", fn)}</a>')
    nav = "".join(nav_links)
    footer = f"&copy; {site_name}"

    (root / "styles.css").write_text(css or _DEFAULT_CSS, encoding="utf-8")

    written = ["styles.css"]
    for pg in pages:
        fn = str(pg["filename"]).strip()
        html = _PAGE_TEMPLATE.format(
            title=pg.get("title", site_name),
            nav=nav,
            body=pg.get("body_html", ""),
            footer=footer,
        )
        (root / fn).write_text(html, encoding="utf-8")
        written.append(fn)

    return f"created website '{site_name}' in {root} ({len(written)} files: {', '.join(written)})"


def make_document_tools(gate: SafetyGate) -> list[Tool]:
    """Tools that produce finished artifacts (decks, PDFs, websites)."""

    def create_pptx(path: str, title: str, slides: Any, subtitle: str = "") -> str:
        if not gate.confirm(f"CREATE PowerPoint at {path}"):
            raise ToolError("create_pptx denied by safety gate")
        return _build_pptx(path, title, slides, subtitle)

    def create_pdf(path: str, title: str, blocks: Any) -> str:
        if not gate.confirm(f"CREATE PDF at {path}"):
            raise ToolError("create_pdf denied by safety gate")
        return _build_pdf(path, title, blocks)

    def create_website(
        directory: str, pages: Any, site_name: str = "My Site", css: str = ""
    ) -> str:
        if not gate.confirm(f"CREATE website in {directory}"):
            raise ToolError("create_website denied by safety gate")
        return _build_website(directory, pages, site_name, css)

    _str = {"type": "string"}
    return [
        Tool(
            "create_pptx",
            "Build a PowerPoint (.pptx) deck. 'slides' is a list of objects like "
            '{"title": str, "bullets": [str, ...], "notes": str (optional)}. '
            "A title slide is added automatically. Great for presentations.",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "output .pptx path"},
                    "title": {"type": "string", "description": "deck title"},
                    "subtitle": _str,
                    "slides": {
                        "type": "array",
                        "description": "list of {title, bullets[, notes]} slides",
                        "items": {"type": "object"},
                    },
                },
                "required": ["path", "title", "slides"],
            },
            create_pptx,
            dangerous=True,
        ),
        Tool(
            "create_pdf",
            "Build a PDF document. 'blocks' is an ordered list of content blocks: "
            '{"type": "heading"|"subheading"|"text"|"bullets", "text": str} or '
            '{"type": "bullets", "items": [str, ...]}. '
            "Ideal for reports, study notes, and handouts.",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "output .pdf path"},
                    "title": {"type": "string", "description": "document title"},
                    "blocks": {
                        "type": "array",
                        "description": "ordered content blocks",
                        "items": {"type": "object"},
                    },
                },
                "required": ["path", "title", "blocks"],
            },
            create_pdf,
            dangerous=True,
        ),
        Tool(
            "create_website",
            "Scaffold a complete multi-page static website into a directory. "
            "'pages' is a list of {filename, title, body_html}; a shared nav, "
            "responsive styles.css, and footer are generated. Pass your own 'css' "
            "to override the default theme.",
            {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "output folder"},
                    "site_name": _str,
                    "css": {"type": "string", "description": "optional CSS override"},
                    "pages": {
                        "type": "array",
                        "description": "list of {filename, title, body_html}",
                        "items": {"type": "object"},
                    },
                },
                "required": ["directory", "pages"],
            },
            create_website,
            dangerous=True,
        ),
    ]
