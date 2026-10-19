#!/usr/bin/env python3
"""Build the recruiter-facing PowerPoint presentation.

Colorful, concise, with clickable navigation between slides.
All numbers are verified measurements from the project.
No em dashes anywhere in the text.
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "docs", "Delivery-Experience-Intelligence-Showcase.pptx")

# Palette
BLUE = RGBColor(0x1A, 0x73, 0xE8)
DARK = RGBColor(0x20, 0x24, 0x2B)
GREEN = RGBColor(0x34, 0xA8, 0x53)
AMBER = RGBColor(0xFB, 0xBC, 0x04)
RED = RGBColor(0xEA, 0x43, 0x35)
PURPLE = RGBColor(0x6A, 0x1B, 0x9A)
TEAL = RGBColor(0x00, 0x96, 0x88)
LIGHT_BG = RGBColor(0xF8, 0xF9, 0xFA)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GRAY = RGBColor(0x5F, 0x63, 0x68)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
W, H = prs.slide_width, prs.slide_height

slides = {}  # name -> slide object for navigation
toc_links = []  # (shape, target_name) pairs for clickable TOC cards


def bg(slide, color):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_shape(slide, shape_type, left, top, width, height, fill_color,
              line_color=None):
    shape = slide.shapes.add_shape(shape_type, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.fill.background()
    if line_color:
        shape.line.color.rgb = line_color
        shape.line.width = Pt(1.5)
    return shape


def set_text(shape, text, size=18, bold=False, color=DARK,
             alignment=PP_ALIGN.LEFT):
    tf = shape.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    p.alignment = alignment
    return tf


def add_textbox(slide, left, top, width, height, text, size=18, bold=False,
                color=DARK, alignment=PP_ALIGN.LEFT):
    tx = slide.shapes.add_textbox(left, top, width, height)
    set_text(tx, text, size, bold, color, alignment)
    return tx


def header_bar(slide, title, color):
    """Colored top bar with section title."""
    bar = add_shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, W, Inches(1.1), color)
    set_text(bar, title, size=30, bold=True, color=WHITE,
             alignment=PP_ALIGN.LEFT)
    bar.text_frame.paragraphs[0].margin_left = Inches(0.5)
    return bar


def nav_button(slide, target_name, label="Home"):
    """Small button linking back to the table of contents."""
    btn = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE,
                    W - Inches(1.6), H - Inches(0.7),
                    Inches(1.3), Inches(0.45), LIGHT_BG, GRAY)
    set_text(btn, label, size=12, color=GRAY, alignment=PP_ALIGN.CENTER)
    btn.click_action.target_slide = slides[target_name]
    return btn


def bullet_slide(name, title, color, bullets, footer=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slides[name] = slide
    bg(slide, WHITE)
    header_bar(slide, title, color)
    tx = slide.shapes.add_textbox(Inches(0.7), Inches(1.6),
                                  Inches(11.9), Inches(4.8))
    tf = tx.text_frame
    tf.word_wrap = True
    for i, (b, sub) in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(14)
        run = p.add_run()
        run.text = b
        run.font.size = Pt(20)
        run.font.color.rgb = DARK
        if sub:
            p2 = tf.add_paragraph()
            p2.space_after = Pt(14)
            p2.level = 1
            run2 = p2.add_run()
            run2.text = sub
            run2.font.size = Pt(16)
            run2.font.color.rgb = GRAY
    if footer:
        add_textbox(slide, Inches(0.7), H - Inches(1.3), Inches(11),
                    Inches(0.6), footer, size=13, color=GRAY,
                    alignment=PP_ALIGN.LEFT)
    nav_button(slide, "toc")
    return slide


# ---------------------------------------------------------------- 1. Title
slide = prs.slides.add_slide(prs.slide_layouts[6])
slides["toc"] = slide  # placeholder, replaced below
bg(slide, BLUE)
add_textbox(slide, Inches(1), Inches(1.2), Inches(11.3), Inches(1.5),
            "Delivery Experience\nIntelligence Platform",
            size=54, bold=True, color=WHITE, alignment=PP_ALIGN.CENTER)
add_textbox(slide, Inches(2), Inches(3.9), Inches(9.3), Inches(1),
            "Spot delivery trouble early. Check the photo evidence.\n"
            "Decide what to do next, before the customer complains.",
            size=22, color=WHITE, alignment=PP_ALIGN.CENTER)
add_textbox(slide, Inches(2), Inches(5.6), Inches(9.3), Inches(0.6),
            "Anum Sagheer  |  End-to-end data science on Google Cloud",
            size=18, color=WHITE, alignment=PP_ALIGN.CENTER)
add_textbox(slide, Inches(2), Inches(6.3), Inches(9.3), Inches(0.6),
            "Real data. Real cloud. Every number measured.",
            size=15, color=WHITE, alignment=PP_ALIGN.CENTER)

# ------------------------------------------------------- 2. Contents (TOC)
slide = prs.slides.add_slide(prs.slide_layouts[6])
slides["toc"] = slide
bg(slide, WHITE)
header_bar(slide, "What is inside", BLUE)
items = [
    ("problem", "The problem", "Why late deliveries cost double"),
    ("how", "How it works", "Six steps from order to decision"),
    ("risk", "Risk models", "Predicting lateness and bad reviews"),
    ("vision", "Computer vision", "99.6% package detection"),
    ("agent", "Streaming + agent", "6,235 events/sec, 500 verified decisions"),
    ("ab", "A/B testing", "A properly designed experiment"),
    ("stack", "Tech stack", "GCP, ML, and engineering"),
    ("limits", "Honest limits", "What is real and what is not"),
]
for i, (key, title, sub) in enumerate(items):
    r, c = divmod(i, 2)
    x = Inches(0.8 + c * 6.2)
    y = Inches(1.6 + r * 1.35)
    box = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y,
                    Inches(5.6), Inches(1.1), LIGHT_BG, BLUE)
    tf = set_text(box, f"{title}\n{sub}", size=16, bold=False, color=DARK)
    tf.paragraphs[0].runs[0].font.bold = True
    tf.paragraphs[0].runs[0].font.size = Pt(19)
    toc_links.append((box, key))
add_textbox(slide, Inches(0.8), H - Inches(1.2), Inches(11), Inches(0.6),
            "Click any card to jump to that section.",
            size=14, color=GRAY)

# ------------------------------------------------------- 3. Problem
bullet_slide("problem", "The problem", RED, [
    ("Late deliveries cost twice: the redelivery, then the customer's trust.",
     "Most companies learn about failures from angry reviews. That is the most expensive feedback loop possible."),
    ("This platform moves detection earlier.",
     "Predict risk at purchase time. Watch events stream in. Check the delivery photo. Draft the right response, before the customer has to complain."),
    ("Built on 100% real public data, deployed on real Google Cloud.",
     "Olist orders, Amazon routes, OpenStreetMap, Open Images. Nothing invented."),
])

# ------------------------------------------------------- 4. How it works
slide = prs.slides.add_slide(prs.slide_layouts[6])
slides["how"] = slide
bg(slide, WHITE)
header_bar(slide, "How it works: six steps", TEAL)
steps = [
    ("1", "Orders stream in", "Real order events flow through Pub/Sub into BigQuery.", BLUE),
    ("2", "Risk is scored", "Two classifiers predict lateness and low reviews from purchase-time data only.", GREEN),
    ("3", "Photos are checked", "Blur check (free), then AI classifier, then Gemini for hard cases.", AMBER),
    ("4", "The agent decides", "A written policy weighs every signal. Drafts a message or escalates. Never auto-sends.", PURPLE),
    ("5", "Everything is audited", "All 500 cloud decisions independently re-verified: 500/500 matched.", TEAL),
    ("6", "Experiments done right", "A/B test designed with real power analysis before anyone claims an uplift.", RED),
]
for i, (num, title, desc, color) in enumerate(steps):
    x = Inches(0.5 + i * 2.12)
    card = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, Inches(1.7),
                     Inches(1.95), Inches(4.3), WHITE, color)
    num_box = add_shape(slide, MSO_SHAPE.OVAL, x + Inches(0.65),
                        Inches(1.95), Inches(0.65), Inches(0.65), color)
    set_text(num_box, num, size=22, bold=True, color=WHITE,
             alignment=PP_ALIGN.CENTER)
    add_textbox(slide, x + Inches(0.1), Inches(2.8), Inches(1.75),
                Inches(0.8), title, size=15, bold=True, color=DARK,
                alignment=PP_ALIGN.CENTER)
    add_textbox(slide, x + Inches(0.1), Inches(3.5), Inches(1.75),
                Inches(2.2), desc, size=12, color=GRAY,
                alignment=PP_ALIGN.CENTER)
nav_button(slide, "toc")

# ------------------------------------------------------- 5. Risk models
slide = prs.slides.add_slide(prs.slide_layouts[6])
slides["risk"] = slide
bg(slide, WHITE)
header_bar(slide, "Risk models: which orders are in trouble?", GREEN)
add_textbox(slide, Inches(0.7), Inches(1.4), Inches(11.9), Inches(0.8),
            "Two classifiers using only purchase-time features. Strict temporal splits, no peeking at the future.",
            size=17, color=GRAY)
rows_data = [
    ("Model", "Where", "ROC-AUC", "What it means"),
    ("Late delivery (HGB)", "Local", "0.649", "Ranks late orders above on-time ones 65% of the time"),
    ("Late delivery (BQML)", "BigQuery", "0.616", "Same task, trained where the data lives"),
    ("Low review (HGB)", "Local", "0.601", "Predicts 1 to 2 star reviews"),
    ("Low review (BQML)", "BigQuery", "0.575", "Cloud twin of the local model"),
]
tbl_shape = slide.shapes.add_table(6, 4, Inches(0.7), Inches(2.4),
                                   Inches(11.9), Inches(3.2))
tbl = tbl_shape.table
for j, h in enumerate(rows_data[0]):
    cell = tbl.cell(0, j)
    cell.text = h
    for p in cell.text_frame.paragraphs:
        for r in p.runs:
            r.font.bold = True
            r.font.size = Pt(15)
            r.font.color.rgb = WHITE
    cell.fill.solid()
    cell.fill.fore_color.rgb = GREEN
for i, row in enumerate(rows_data[1:], start=1):
    for j, val in enumerate(row):
        cell = tbl.cell(i, j)
        cell.text = val
        for p in cell.text_frame.paragraphs:
            for r in p.runs:
                r.font.size = Pt(14)
                r.font.color.rgb = DARK
        if i % 2 == 0:
            cell.fill.solid()
            cell.fill.fore_color.rgb = LIGHT_BG
add_textbox(slide, Inches(0.7), Inches(6.0), Inches(11.9), Inches(0.8),
            "Honest context: these are modest scores. Delivery lateness is hard to predict from purchase data alone. "
            "The value is the methodology: temporal splits, leakage controls, calibrated thresholds.",
            size=14, color=GRAY)
nav_button(slide, "toc")

# ------------------------------------------------------- 6. Vision
slide = prs.slides.add_slide(prs.slide_layouts[6])
slides["vision"] = slide
bg(slide, WHITE)
header_bar(slide, "Computer vision: is the package in the photo?", PURPLE)
add_textbox(slide, Inches(0.7), Inches(1.4), Inches(5.5), Inches(0.7),
            "Trained on 4,712 real photos with human-drawn annotations.",
            size=17, bold=True, color=DARK)
bullets = [
    "Test accuracy: 99.6% (469 of 471 held-out photos)",
    "Package precision: 1.0000, never cried wolf",
    "Package recall: 0.9910, missed 2 of 221",
    "Cost-ordered cascade: free blur check, then AI, then Gemini",
    "Batch prediction only, no expensive always-on endpoint",
]
tx = slide.shapes.add_textbox(Inches(0.7), Inches(2.2), Inches(5.5),
                              Inches(4.2))
tf = tx.text_frame
tf.word_wrap = True
for i, b in enumerate(bullets):
    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    p.space_after = Pt(12)
    run = p.add_run()
    run.text = "•  " + b
    run.font.size = Pt(17)
    run.font.color.rgb = DARK
img_path = os.path.join(REPO, "docs", "assets", "cv_predictions.png")
if os.path.exists(img_path):
    slide.shapes.add_picture(img_path, Inches(6.8), Inches(1.4),
                             width=Inches(5.8), height=Inches(4.35))
add_textbox(slide, Inches(0.7), Inches(6.3), Inches(11.9), Inches(0.6),
            "Real test photos with the model's actual predictions and confidence scores.",
            size=13, color=GRAY)
nav_button(slide, "toc")

# ------------------------------------------------------- 7. Agent
bullet_slide("agent", "Streaming + intervention agent", BLUE, [
    ("Pub/Sub streaming: 6,235 events per second, zero message loss.",
     "19,770 real order events published to the cloud topic and consumed into BigQuery."),
    ("500 real cloud decisions, every one independently verified.",
     "A separate script recomputed each decision from warehouse facts. 500 out of 500 matched. 496 no action, 4 customer outreach drafts."),
    ("Nothing is ever sent automatically.",
     "The agent drafts messages for human approval. Dry-run only, by design."),
], footer="Evidence: evals/streaming/pubsub_cloud.json, evals/agent/verify_audit_500.json, gcp/verify_agent_audit.py")

# ------------------------------------------------------- 8. A/B testing
bullet_slide("ab", "A/B testing: the outreach experiment", AMBER, [
    ("Designed like a real experiment, because it might become one.",
     "Customer-level randomization (not order-level), sticky assignment, 50/50 split."),
    ("Sample size calibrated on the real data: about 750 per arm.",
     "Simulation on the actual score distribution showed the naive textbook number was too small."),
    ("Sequential monitoring done correctly.",
     "O'Brien-Fleming boundaries hold the false positive rate at 5%. Naive repeated testing would hit 13%."),
    ("Status: designed and validated. Never run live. No uplift claimed.",
     "The module exists to prove experimental rigor, not to invent business impact."),
])

# ------------------------------------------------------- 9. Tech stack
slide = prs.slides.add_slide(prs.slide_layouts[6])
slides["stack"] = slide
bg(slide, WHITE)
header_bar(slide, "Technology stack", DARK)
groups = [
    ("Cloud", ["BigQuery", "Pub/Sub", "Cloud Storage", "Vertex AI"], BLUE),
    ("Machine learning", ["scikit-learn", "BigQuery ML", "HistGradientBoosting"], GREEN),
    ("Computer vision", ["OpenCV", "Vertex AI AutoML", "Gemini 2.5 Flash"], PURPLE),
    ("Agentic AI", ["Policy engine", "Dry-run eval", "Audit logging"], TEAL),
    ("Experimentation", ["Power analysis", "Permutation tests", "Sequential monitoring"], AMBER),
    ("Engineering", ["Python 3.10+", "pytest (31 tests)", "Docker", "GitHub Actions"], GRAY),
]
for i, (title, items_, color) in enumerate(groups):
    r, c = divmod(i, 3)
    x = Inches(0.7 + c * 4.1)
    y = Inches(1.6 + r * 2.5)
    card = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y,
                     Inches(3.8), Inches(2.1), WHITE, color)
    add_textbox(slide, x + Inches(0.2), y + Inches(0.15), Inches(3.4),
                Inches(0.5), title, size=17, bold=True, color=color)
    add_textbox(slide, x + Inches(0.2), y + Inches(0.7), Inches(3.4),
                Inches(1.3), "\n".join("•  " + t for t in items_),
                size=14, color=DARK)
nav_button(slide, "toc")

# ------------------------------------------------------- 10. Limits
bullet_slide("limits", "Honest limits", RED, [
    ("Historical data, not live operations.",
     "Olist 2016 to 2018, Amazon 2018 routes. The platform replays history; it has never touched a live delivery."),
    ("The agent never contacted anyone.",
     "All decisions were dry runs. Auto-send needs human-in-the-loop tooling this project does not claim."),
    ("Some treatment effects are simulated.",
     "The A/B power analysis simulates the uplift on real data. The design is real; the business impact is not claimed."),
    ("Modest risk models, clearly labeled as triage signals.",
     "ROC-AUC around 0.6. The methodology is the point, not the score."),
    ("Datasets are never falsely joined.",
     "Four datasets, four companies, four contexts. Cross-module demos are labeled as controlled scenarios."),
], footer="Every number in this deck traces to a script in the repo or a resource in GCP project delivery-experience-511901.")

# ------------------------------------------------------- 11. Closing
slide = prs.slides.add_slide(prs.slide_layouts[6])
bg(slide, BLUE)
add_textbox(slide, Inches(1), Inches(1.5), Inches(11.3), Inches(1.2),
            "Thank you",
            size=54, bold=True, color=WHITE, alignment=PP_ALIGN.CENTER)
add_textbox(slide, Inches(2), Inches(3.2), Inches(9.3), Inches(2),
            "Real data. Real cloud. Real measurements.\n"
            "Every claim verified, every limit stated.",
            size=24, color=WHITE, alignment=PP_ALIGN.CENTER)
add_textbox(slide, Inches(2), Inches(5.5), Inches(9.3), Inches(0.8),
            "Anum Sagheer  |  github.com/anumsagheer01",
            size=18, color=WHITE, alignment=PP_ALIGN.CENTER)
nav_button(slide, "toc")

# ------------------------------------------------- Link TOC cards
for shape, target in toc_links:
    if target in slides:
        shape.click_action.target_slide = slides[target]

prs.save(OUT)
print(f"saved {OUT}")
print(f"slides: {len(prs.slides.__iter__.__self__._sldIdLst)}")
