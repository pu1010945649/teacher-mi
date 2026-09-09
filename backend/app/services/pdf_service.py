import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

# 使用内置中文字体，无需外部字体文件
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

TITLE_STYLE = ParagraphStyle("title", fontName="STSong-Light", fontSize=18, leading=26,
                             alignment=1, spaceAfter=6 * mm)
BODY_STYLE = ParagraphStyle("body", fontName="STSong-Light", fontSize=11.5, leading=20)


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_pdf(title: str, content: str, out_path: str) -> None:
    """将练习内容渲染为 PDF，按行输出"""
    doc = SimpleDocTemplate(out_path, pagesize=A4,
                            leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm)
    story = [Paragraph(_esc(title), TITLE_STYLE),
             Paragraph("姓名：＿＿＿＿＿＿　班级：＿＿＿＿＿＿　日期：＿＿＿＿＿＿", BODY_STYLE),
             Spacer(1, 5 * mm)]
    for line in content.splitlines():
        line = line.strip()
        if line:
            story.append(Paragraph(_esc(line), BODY_STYLE))
        else:
            story.append(Spacer(1, 3 * mm))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc.build(story)
