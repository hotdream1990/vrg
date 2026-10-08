"""Xem trước + dò đè chữ cho khu "Khu mủ vào" v2 — CHỈ là công cụ kiểm, không phải cách web vẽ thật.

Nền = ảnh RELCO quy đổi vào viewBox (X = x − 110 · Y = (y − 140) × 1.047) để so vị trí bằng mắt; trên đó
vẽ khung thiết bị (xoay quanh tâm), khối nhãn+Hz/A tại `info_xy`, khối nhiệt độ tại `temps_xy`, badge,
ống, mũi tên + chữ tại `text_xy`, `usage_box`. Khối chữ đo theo 2 cỡ: RELCO (nhỏ) và cỡ web đoán (lớn).
Chạy: python3 preview_v2.py [out.png]  → in các chỗ chồng nhau + ghi ảnh.
"""
import base64
import io
import json
import math
import subprocess
import sys

from PIL import Image

ROOT = "/Volumes/Work/biz-project/VRG"
PATH = f"{ROOT}/apps/api/app/services/plant_layouts/phu_rieng.json"
SRC = f"{ROOT}/plans/260930-nha-may-thong-minh-scada/visuals/relco-khu-mu-vao.webp"
SIZES = {"nho": dict(bw=80, lab=14, row=19, tcol=64, tgap=40, trow=19),
         "lon": dict(bw=105, lab=18, row=23, tcol=80, tgap=10, trow=23)}


def rot(n):
    cx, cy = n["x"] + n["w"] / 2, n["y"] + n["h"] / 2
    a = math.radians(n["angle"])
    c, s = math.cos(a), math.sin(a)
    pts = [(n["x"], n["y"]), (n["x"] + n["w"], n["y"]), (n["x"] + n["w"], n["y"] + n["h"]),
           (n["x"], n["y"] + n["h"])]
    return [(cx + (px - cx) * c - (py - cy) * s, cy + (px - cx) * s + (py - cy) * c) for px, py in pts]


def rect(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def seg_poly(p, q, half):
    """Đoạn ống dày 2·half thành đa giác lồi."""
    (x0, y0), (x1, y1) = p, q
    ln = math.hypot(x1 - x0, y1 - y0) or 1
    nx, ny = -(y1 - y0) / ln * half, (x1 - x0) / ln * half
    return [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)]


def overlap(p, q):
    depth = 1e9
    for poly in (p, q):
        for i in range(len(poly)):
            (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
            ax, ay = y0 - y1, x1 - x0
            ln = math.hypot(ax, ay) or 1
            ax, ay = ax / ln, ay / ln
            pa = [px * ax + py * ay for px, py in p]
            qa = [px * ax + py * ay for px, py in q]
            d = min(max(pa), max(qa)) - max(min(pa), min(qa))
            if d <= 0:
                return 0
            depth = min(depth, d)
    return depth


def shapes(area, sz):
    out = []
    for n in area["nodes"]:
        if n["kind"] == "mixer":  # biểu tượng web hiện tại: chân vịt bên trái + hộp motor trên-phải
            x, y, w, h = n["x"], n["y"], n["w"], n["h"]
            r = 0.37 * h
            out.append((n["id"] + ".paddle", rect(x + 0.3 * w - r, y + 0.56 * h - r, 2 * r, 2 * r), "body"))
            out.append((n["id"] + ".motor", rect(x + 0.55 * w, y + 0.25 * h, 0.45 * w, 0.41 * h), "body"))
            out.append((n["id"] + ".frame", rot(n), "frame"))
        else:
            out.append((n["id"], rot(n), "body"))
        rows = max(len(n["metrics"]), 1)
        bw = sz["bw"] if n["metrics"] else 60
        out.append((n["id"] + ".info", rect(*n["info_xy"], bw, sz["lab"] + sz["row"] * rows), "info"))
        if n.get("temps_xy"):
            cols = n["temps_cols"]
            nrow = math.ceil(len(n["temps"]) / cols)
            w = sz["tcol"] * cols + sz["tgap"] * (cols - 1)
            out.append((n["id"] + ".temps", rect(*n["temps_xy"], w, sz["trow"] * nrow), "temps"))
    for i, d in enumerate(area["decor"]):
        if d["kind"] == "badge":
            out.append((f"badge{i}", rect(d["x"], d["y"], 30, 19), "badge"))
        elif d["kind"] == "arrow_text":
            tx, ty = d["text_xy"]
            out.append((f"text:{d['text']}", rect(tx, ty - 9, 8.2 * len(d["text"]), 18), "text"))
            pts = d["points"]
            out += [(f"arrow{i}.{k}", seg_poly(pts[k], pts[k + 1], 3), "pipe") for k in range(len(pts) - 1)]
        elif d["kind"] == "pipe":
            pts = d["points"]
            out += [(f"pipe{i}.{k}", seg_poly(pts[k], pts[k + 1], 4), "pipe") for k in range(len(pts) - 1)]
    u = area.get("usage_box")
    if u:
        out.append(("usage_box", rect(u["x"], u["y"], u["w"], u["h"]), "usage"))
    return out


TEXTY = {"info", "temps", "badge", "text", "usage"}


def clashes(area, sz, min_depth=1.5):
    sh = shapes(area, sz)
    bad = []
    for i, (na, pa, ka) in enumerate(sh):
        for nb, pb, kb in sh[i + 1:]:
            if (ka not in TEXTY and kb not in TEXTY) or "frame" in (ka, kb):
                continue  # thân–thân / thân–ống: RELCO cũng chồng (băng tải đổ vào phễu)
            d = overlap(pa, pb)
            if d > min_depth:
                bad.append((round(d, 1), na, nb))
    for name, poly, _ in sh:
        if any(not (0 <= x <= area["width"] and 0 <= y <= area["height"]) for x, y in poly):
            bad.append(("ngoài khung", name, ""))
    return bad


def svg(area, sz):
    im = Image.open(SRC).convert("RGB").crop((110, 140, 1910, 1000)).resize((1800, 900))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    b64 = base64.b64encode(buf.getvalue()).decode()
    col = {"body": "#1d4ed8", "frame": "#93c5fd", "info": "#dc2626", "temps": "#ea580c", "badge": "#7c3aed",
           "text": "#059669", "pipe": "#0891b2", "usage": "#111827"}
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
             f'width="1800" height="900" viewBox="0 0 1800 900">',
             f'<image href="data:image/jpeg;base64,{b64}" xlink:href="data:image/jpeg;base64,{b64}" '
             f'x="0" y="0" width="1800" height="900" opacity="0.55"/>']
    for name, poly, kind in shapes(area, sz):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in poly)
        fill = "none" if kind in ("body", "usage", "frame") else col[kind]
        parts.append(f'<polygon points="{pts}" fill="{fill}" fill-opacity="0.18" stroke="{col[kind]}" '
                     f'stroke-width="1.6"/>')
        if kind in ("body", "info"):
            x, y = poly[0]
            parts.append(f'<text x="{x + 2:.0f}" y="{y + 12:.0f}" font-size="11" font-family="Arial" '
                         f'fill="{col[kind]}">{name.split(".")[0]}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "preview-khu-mu-vao-v2.png"
    area = next(a for a in json.load(open(PATH, encoding="utf-8"))["areas"] if a["key"] == "khu-mu-vao")
    for key, sz in SIZES.items():
        print(f"== cỡ {key}:", clashes(area, sz) or "không chồng")
        path = out.replace(".png", f"-{key}.svg")
        open(path, "w").write(svg(area, sz))
        subprocess.run(["rsvg-convert", path, "-o", out.replace(".png", f"-{key}.png")], check=True)
    print("ảnh:", out)
