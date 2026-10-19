#!/usr/bin/env python3
"""Render study-guide markdown drafts into styled, color-coded PDFs.

Usage: python scripts/render_pdfs.py --drafts pdf-drafts --out study-guide-pdfs
Requires: fpdf2, markdown (in build venv).
Design: color-coded section headers, callout styling via blockquotes,
tables, code blocks, page numbers, title page, table of contents.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import markdown  # noqa: E402
from fpdf import FPDF  # noqa: E402

# restrained, learning-friendly palette
COLORS = {
    "h1": (27, 58, 95),      # deep navy
    "h2": (35, 90, 130),     # steel blue
    "h3": (70, 120, 150),    # muted teal-blue
    "accent": (200, 120, 40),  # warm amber for rules/numbers
    "callout_bg": (240, 245, 250),
    "callout_border": (35, 90, 130),
    "code_bg": (245, 245, 245),
}

PDF_TITLES = {
    "pdf01": "Complete Project Walkthrough",
    "pdf02": "Python, SQL, and Data Engineering Fundamentals",
    "pdf03": "Google Cloud Complete Technical Guide",
    "pdf04": "Machine Learning Complete Study Guide",
    "pdf05": "Computer Vision Deep Dive",
    "pdf06": "Address Intelligence and Geospatial ML",
    "pdf07": "LLMs, Gemini, ADK, and Agentic AI",
    "pdf08": "Full Code Walkthrough",
    "pdf09": "Model Evaluation and Experiment Results",
    "pdf10": "Complete Technical Interview Question Bank",
    "pdf11": "Interview Speaking Scripts",
    "pdf12": "Troubleshooting and Failure Scenarios",
    "pdf13": "Architecture Decisions and Trade-offs",
    "pdf14": "Resume, Portfolio, and Hiring Manager Guide",
    "pdf15": "Interview Storytelling: The Complete Project Narrative",
    "pdf16": "The Outreach Experiment: A/B Testing Done Right",
}


class GuidePDF(FPDF):
    def __init__(self, title):
        super().__init__()
        self.guide_title = title
        self.set_auto_page_break(True, margin=20)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, self.guide_title, align="L")
        self.cell(0, 8, f"Delivery Experience Intelligence Platform",
                  align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(35, 90, 130)
        self.line(10, 16, 200, 16)
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def title_page(self, subtitle):
        self.add_page()
        self.ln(60)
        self.set_font("Helvetica", "B", 26)
        self.set_text_color(*COLORS["h1"])
        self.multi_cell(0, 12, self.guide_title, align="C")
        self.ln(6)
        self.set_font("Helvetica", "", 13)
        self.set_text_color(90, 90, 90)
        self.multi_cell(0, 8, subtitle, align="C")
        self.ln(10)
        self.set_draw_color(*COLORS["accent"])
        self.set_line_width(1.2)
        self.line(80, self.get_y(), 130, self.get_y())
        self.ln(10)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(120, 120, 120)
        self.multi_cell(0, 6, "Delivery Experience Intelligence Platform\n"
                              "Study Guide Series", align="C")

    def toc_page(self, headings):
        self.add_page()
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(*COLORS["h1"])
        self.cell(0, 12, "Contents", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(50, 50, 50)
        for level, text in headings:
            indent = 6 if level == 2 else 14
            self.set_x(10 + indent)
            style = "B" if level == 2 else ""
            self.set_font("Helvetica", style, 10 if level == 2 else 9)
            self.multi_cell(0, 6, text)


def md_to_html(md_text):
    # strip the leading "# PDF NN: Title" (we render our own title page)
    md_text = re.sub(r"^# PDF \d+:.*\n", "", md_text, count=1)
    # fpdf2 write_html handles a subset; keep markup simple
    html = markdown.markdown(md_text, extensions=["tables", "fenced_code"])
    # color-code h2/h3 via font tags (fpdf2 write_html supports <font color>)
    html = re.sub(r"<h2>(.*?)</h2>",
                  r'<h2><font color="#235A82">\1</font></h2>', html)
    html = re.sub(r"<h3>(.*?)</h3>",
                  r'<h3><font color="#467896">\1</font></h3>', html)
    return html


def collect_headings(md_text):
    out = []
    for line in md_text.splitlines():
        m = re.match(r"^(#{2,3})\s+(.*)", line)
        if m:
            out.append((len(m.group(1)), m.group(2).strip()[:90]))
    return out


def render_one(md_path, out_path):
    key = os.path.basename(md_path)[:5]
    title = PDF_TITLES.get(key, key)
    with open(md_path, encoding="utf-8") as f:
        md_text = f.read()
    pdf = GuidePDF(f"PDF {key[3:]}: {title}")
    pdf.alias_nb_pages("{nb}")
    pdf.title_page("A complete technical learning library for the "
                   "Delivery Experience Intelligence Platform")
    pdf.toc_page(collect_headings(md_text)[:60])
    pdf.add_page()
    html = md_to_html(md_text)
    pdf.set_font("Helvetica", "", 10)
    pdf.write_html(html, table_line_separators=True)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    pdf.output(out_path)
    size_kb = os.path.getsize(out_path) // 1024
    print(f"rendered {out_path} ({size_kb} KB, {pdf.page_no()} pages)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drafts",
                    default=os.path.join(os.path.expanduser("~"),
                                         "workspace", "build", "pdf-drafts"))
    ap.add_argument("--out",
                    default=os.path.join(os.path.expanduser("~"),
                                         "workspace", "build", "study-guide-pdfs"))
    args = ap.parse_args()
    files = sorted(f for f in os.listdir(args.drafts) if f.endswith(".md"))
    print(f"rendering {len(files)} PDFs...")
    for f in files:
        render_one(os.path.join(args.drafts, f),
                   os.path.join(args.out, f.replace(".md", ".pdf")))
    print("done.")


if __name__ == "__main__":
    main()
