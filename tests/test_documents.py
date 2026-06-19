"""Tests for the document/artifact builders (pptx, pdf, website).

The pptx/pdf tests are skipped if the optional deps aren't installed, so the
suite still runs on a minimal environment.
"""

import importlib.util
import json
import tempfile
from pathlib import Path

import pytest

from jarvis.tools.documents import make_document_tools
from jarvis.utils.safety import SafetyGate

_HAS_PPTX = importlib.util.find_spec("pptx") is not None
_HAS_REPORTLAB = importlib.util.find_spec("reportlab") is not None


def _tools():
    return {t.name: t for t in make_document_tools(SafetyGate(require_confirmation=False))}


@pytest.mark.skipif(not _HAS_PPTX, reason="python-pptx not installed")
def test_create_pptx_real_file():
    tools = _tools()
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "deck.pptx"
        slides = [
            {"title": "Intro", "bullets": ["Point A", "Point B"], "notes": "hi"},
            {"title": "Details", "bullets": ["One", "Two", "Three"]},
        ]
        # Pass slides as a JSON string to exercise the coercion path.
        msg = tools["create_pptx"].run(
            {"path": str(out), "title": "Demo", "slides": json.dumps(slides)}
        )
        assert out.is_file() and out.stat().st_size > 0
        assert "3 slides" in msg  # title + 2 content slides


@pytest.mark.skipif(not _HAS_REPORTLAB, reason="reportlab not installed")
def test_create_pdf_real_file():
    tools = _tools()
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "notes.pdf"
        blocks = [
            {"type": "heading", "text": "Chapter 1"},
            {"type": "text", "text": "Some explanation."},
            {"type": "bullets", "items": ["k1", "k2"]},
        ]
        msg = tools["create_pdf"].run(
            {"path": str(out), "title": "Study Notes", "blocks": blocks}
        )
        assert out.is_file() and out.stat().st_size > 0
        assert out.read_bytes().startswith(b"%PDF")
        assert "3 blocks" in msg


def test_create_website_real_files():
    tools = _tools()
    with tempfile.TemporaryDirectory() as d:
        site = Path(d) / "site"
        pages = [
            {"filename": "index.html", "title": "Home", "body_html": "<h1>Hi</h1>"},
            {"filename": "about.html", "title": "About", "body_html": "<p>About</p>"},
        ]
        msg = tools["create_website"].run(
            {"directory": str(site), "pages": pages, "site_name": "Test"}
        )
        assert (site / "index.html").is_file()
        assert (site / "about.html").is_file()
        assert (site / "styles.css").is_file()
        # Shared nav links to every page.
        index = (site / "index.html").read_text()
        assert 'href="about.html"' in index and 'href="index.html"' in index
        assert "3 files" in msg
