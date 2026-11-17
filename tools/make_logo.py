# -*- coding: utf-8 -*-
"""Build the OpenRefresh wordmark as an SVG with the text as outlines.

usage: python -I make_logo.py <font dir> <out.svg> <preview.png> [overlap] [lift]

Needs PySide6 (FreeCAD 1.1 bundles it: use FreeCAD's own python.exe) and the
Evolventa fonts, which are not stored in this repository. Get
ttf/Evolventa-Regular.ttf and ttf/Evolventa-Bold.ttf from
https://github.com/evolventa/evolventa (GPLv2 / LPPL) into <font dir>.

The defaults reproduce docs/media/logo.svg: the dot's centre sits on the
baseline (lift 0.0), 0.65 of its radius to the right of the "h" (overlap 0.35).

"Open" in Evolventa Regular, FreeCAD red #CB333B; "Refresh" in Evolventa Bold,
FreeCAD blue #418FDE (FreeCAD's own wordmark: "Free" Regular, "CAD" Bold).
The green refresh dot from the original icon overlaps the end of the word; the
letters under it get a small gap cut out of their outlines, so the overlap
reads the same on light and dark backgrounds and needs no SVG masks.
"""

import sys

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QFontMetricsF,
                           QGuiApplication, QImage, QPainter, QPainterPath)
from PySide6.QtSvg import QSvgRenderer

RED, BLUE, GREEN = "#CB333B", "#418FDE", "#37b24d"
PX = 100.0                  # font pixel size used for the outlines

app = QGuiApplication(sys.argv[:1])
font_dir, out_svg, preview = sys.argv[1], sys.argv[2], sys.argv[3]
overlap = float(sys.argv[4]) if len(sys.argv) > 4 else 0.35  # share of r over the h

fid_r = QFontDatabase.addApplicationFont(font_dir + "/Evolventa-Regular.ttf")
fid_b = QFontDatabase.addApplicationFont(font_dir + "/Evolventa-Bold.ttf")
family = QFontDatabase.applicationFontFamilies(fid_r)[0]
print("families:", QFontDatabase.applicationFontFamilies(fid_r),
      QFontDatabase.applicationFontFamilies(fid_b))

regular = QFont(family); regular.setPixelSize(int(PX)); regular.setWeight(QFont.Weight.Normal)
bold = QFont(family); bold.setPixelSize(int(PX)); bold.setWeight(QFont.Weight.Bold)
print("faces:", QFontMetricsF(regular).horizontalAdvance("Open"),
      QFontMetricsF(bold).horizontalAdvance("Open"), "(should differ)")

base = PX
open_path = QPainterPath(); open_path.addText(QPointF(0, base), regular, "Open")
advance = QFontMetricsF(regular).horizontalAdvance("Open")
refresh_path = QPainterPath(); refresh_path.addText(QPointF(advance, base), bold, "Refresh")

# Qt's capHeight() is wrong for Evolventa; measure a real capital instead.
probe = QPainterPath(); probe.addText(QPointF(0, base), bold, "H")
cap = probe.boundingRect().height()
print("cap height (measured): %.1f, Qt metric: %.1f" % (cap, QFontMetricsF(bold).capHeight()))
r = cap * 0.55                                   # dot slightly taller than the capitals
right = refresh_path.boundingRect().right()
cx = right + r * (1.0 - overlap)                 # overlap*r of the dot sits over the h
lift = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0  # dot centre height, in caps above the baseline
cy = base - cap * lift

gap = QPainterPath(); gap.addEllipse(QPointF(cx, cy), r * 1.10, r * 1.10)
refresh_path = refresh_path.subtracted(gap)
open_path = open_path.subtracted(gap)


def svg_d(path):
    out, i, n = [], 0, path.elementCount()
    T = QPainterPath.ElementType
    while i < n:
        e = path.elementAt(i)
        if e.type == T.MoveToElement:
            if out:
                out.append("Z")
            out.append("M%.2f %.2f" % (e.x, e.y)); i += 1
        elif e.type == T.LineToElement:
            out.append("L%.2f %.2f" % (e.x, e.y)); i += 1
        elif e.type == T.CurveToElement:
            c2, p = path.elementAt(i + 1), path.elementAt(i + 2)
            out.append("C%.2f %.2f %.2f %.2f %.2f %.2f" % (e.x, e.y, c2.x, c2.y, p.x, p.y)); i += 3
        else:
            i += 1
    out.append("Z")
    return " ".join(out)


rule = "evenodd" if open_path.fillRule().name == "OddEvenFill" else "nonzero"
text_box = open_path.boundingRect().united(refresh_path.boundingRect())
dot_box = QRectF(cx - r, cy - r, 2 * r, 2 * r)
box = text_box.united(dot_box)
pad = PX * 0.06
vx, vy = box.left() - pad, box.top() - pad
vw, vh = box.width() + 2 * pad, box.height() + 2 * pad

s = r / 15.0                                     # the original dot has r = 15 at (46, 46)
dot = (
    '<g transform="translate(%.3f %.3f) scale(%.4f)">'
    '<circle cx="46" cy="46" r="15" fill="%s"/>'
    '<path d="M 52.93 50 A 8 8 0 1 1 51.66 40.34" fill="none" stroke="#ffffff" '
    'stroke-width="3.5" stroke-linecap="round"/>'
    '<path d="M 55.5 35.5 L 55.5 43.5 L 47.5 43.5 Z" fill="#ffffff" stroke="#ffffff" '
    'stroke-width="1.5" stroke-linejoin="round"/></g>'
    % (cx - 46 * s, cy - 46 * s, s, GREEN))

svg = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%.2f %.2f %.2f %.2f" '
    'width="%d" height="%d" role="img" aria-label="OpenRefresh">\n'
    '  <title>OpenRefresh</title>\n'
    '  <!-- Text: Evolventa (Regular / Bold) converted to outlines. -->\n'
    '  <path fill="%s" fill-rule="%s" d="%s"/>\n'
    '  <path fill="%s" fill-rule="%s" d="%s"/>\n'
    '  %s\n'
    '</svg>\n'
    % (vx, vy, vw, vh, round(vw), round(vh),
       RED, rule, svg_d(open_path), BLUE, rule, svg_d(refresh_path), dot))
with open(out_svg, "w", encoding="utf-8") as fh:
    fh.write(svg)
print("svg: %dx%d, %d bytes, fill-rule %s" % (round(vw), round(vh), len(svg), rule))

# preview: GitHub dark and light backgrounds, stacked
renderer = QSvgRenderer(out_svg)
W = 900
H = int(W * vh / vw)
sheet = QImage(W, 2 * H + 30, QImage.Format.Format_ARGB32)
sheet.fill(QColor("#868e96"))
p = QPainter(sheet); p.setRenderHint(QPainter.RenderHint.Antialiasing)
for i, bg in enumerate(("#0d1117", "#ffffff")):
    y = i * (H + 30)
    p.fillRect(0, y, W, H, QColor(bg))
    renderer.render(p, QRectF(0, y, W, H))
p.end()
print("preview saved:", sheet.save(preview))
