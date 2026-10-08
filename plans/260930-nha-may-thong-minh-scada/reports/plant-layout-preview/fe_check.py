"""Mô phỏng cách web đặt khối nhãn/nhiệt độ (theo lời FE) để dò chồng lấn trong bố cục.
FE: (x,y) góc trên-trái khung w×h; angle xoay quanh tâm; khối nhãn+đèn+Hz/A ở cạnh label_pos của KHUNG
(chưa xoay); ô nhiệt độ ở cạnh đối diện; zone/counter hiện số bên trong; arrow_text: chữ sau đầu mũi tên."""
import json, math, sys
PATH = "/Volumes/Work/biz-project/VRG/apps/api/app/services/plant_layouts/phu_rieng.json"
OPP = {"top": "bottom", "bottom": "top", "left": "right", "right": "left"}
PAD = 4


def rot_poly(n):
    cx, cy = n["x"] + n["w"] / 2, n["y"] + n["h"] / 2
    a = math.radians(n["angle"]); c, s = math.cos(a), math.sin(a)
    pts = [(n["x"], n["y"]), (n["x"] + n["w"], n["y"]), (n["x"] + n["w"], n["y"] + n["h"]), (n["x"], n["y"] + n["h"])]
    return [(cx + (px - cx) * c - (py - cy) * s, cy + (px - cx) * s + (py - cy) * c) for px, py in pts]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def overlap(p, q):
    """SAT cho 2 đa giác lồi → độ sâu chồng nhỏ nhất (0 = không chạm)."""
    depth = 1e9
    for poly in (p, q):
        for i in range(len(poly)):
            x0, y0 = poly[i]; x1, y1 = poly[(i + 1) % len(poly)]
            ax, ay = y0 - y1, x1 - x0
            ln = math.hypot(ax, ay) or 1; ax, ay = ax / ln, ay / ln
            pa = [px * ax + py * ay for px, py in p]; qa = [px * ax + py * ay for px, py in q]
            d = min(max(pa), max(qa)) - max(min(pa), min(qa))
            if d <= 0:
                return 0
            depth = min(depth, d)
    return depth


def block(n, side, bw, bh):
    x, y, w, h = n["x"], n["y"], n["w"], n["h"]; cx, cy = x + w / 2, y + h / 2
    if side == "top":
        return rect(cx - bw / 2, y - PAD - bh, cx + bw / 2, y - PAD)
    if side == "bottom":
        return rect(cx - bw / 2, y + h + PAD, cx + bw / 2, y + h + PAD + bh)
    if side == "left":
        return rect(x - PAD - bw, cy - bh / 2, x - PAD, cy + bh / 2)
    return rect(x + w + PAD, cy - bh / 2, x + w + PAD + bw, cy + bh / 2)


def label_block(n, side=None):
    inside = n["kind"] in ("zone", "counter")
    k = 0 if inside else len(n["metrics"])
    return block(n, side or n["label_pos"], 90, 20 + 19 * k + (4 if k else 0))


def temp_block(n, side=None):
    t = 0 if n["kind"] == "zone" else len(n["temps"])
    if not t:
        return None
    return block(n, OPP[side or n["label_pos"]], 80 if t <= 2 else 150, 42)


def text_rect(d):
    (x0, y0), (x1, y1) = d["points"][-2], d["points"][-1]
    wtxt = 8.6 * len(d["text"])
    if x1 > x0:  # sang phải → chữ bên phải đầu mũi tên
        return rect(x1 + 6, y1 - 11, x1 + 6 + wtxt, y1 + 11)
    if x1 < x0:  # sang trái → chữ bên trái
        return rect(x1 - 6 - wtxt, y1 - 11, x1 - 6, y1 + 11)
    return rect(x1 - wtxt / 2, y1 + (8 if y1 > y0 else -30), x1 + wtxt / 2, y1 + (30 if y1 > y0 else -8))


def shapes(area, override=None):
    """[(tên, đa giác, loại)] — loại: body/label/temps/text."""
    out = []
    for n in area["nodes"]:
        side = (override or {}).get(n["id"])
        out.append((n["id"], rot_poly(n), "body"))
        out.append((n["id"] + ".label", label_block(n, side), "label"))
        tb = temp_block(n, side)
        if tb:
            out.append((n["id"] + ".temps", tb, "temps"))
    for d in area["decor"]:
        if d["kind"] == "arrow_text":
            out.append(("«" + d["text"] + "»", text_rect(d), "text"))
    return out


def conflicts(area, override=None):
    sh = shapes(area, override)
    bad = []
    W, H = area["width"], area["height"]
    for name, poly, kind in sh:
        if kind != "body" and any(px < 0 or px > W or py < 0 or py > H for px, py in poly):
            bad.append((name, "NGOÀI KHUNG", 99))
    for i in range(len(sh)):
        for j in range(i + 1, len(sh)):
            (a, pa, ka), (b, pb, kb) = sh[i], sh[j]
            if ka == kb == "body":
                continue  # thân chạm thân là cố ý (băng tải đổ vào máy)
            if a.split(".")[0] == b.split(".")[0] and "body" not in (ka, kb):
                continue
            d = overlap(pa, pb)
            if d > 2:
                bad.append((a, b, round(d)))
    return bad


if __name__ == "__main__":
    L = json.load(open(PATH))
    total = 0
    for area in L["areas"]:
        c = conflicts(area)
        total += len(c)
        print(f"== {area['key']}: {len(c)} chồng lấn")
        for x in c:
            print("  ", x)
    sys.exit(1 if total else 0)
