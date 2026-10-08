"""Sơ đồ vận hành v2 (01/10/2026): vẽ lại khu "Khu mủ vào" bám SÁT ảnh RELCO + ẩn 3 khu còn lại.

Mọi toạ độ dưới đây là toạ độ ẢNH `visuals/relco-khu-mu-vao.webp` (2000×1113), đo trên ảnh phóng to có
lưới; quy đổi sang viewBox 1800×900 của khu theo hợp đồng v2: X = x − 110 · Y = (y − 140) × 1.047.
Tag GIỮ NGUYÊN từ file hiện tại (đã kiểm với 209 tag thật) — script chỉ đổi hình học + trường mới.
Chạy lại được nhiều lần (đọc file hiện tại, thay khu mủ vào, ghi đè).
"""
import json
import math

ROOT = "/Volumes/Work/biz-project/VRG"
PATH = f"{ROOT}/apps/api/app/services/plant_layouts/phu_rieng.json"
HIDE = ("vit-tai-ngang", "ham-say", "dong-goi")


def X(x):
    return round(x - 110)


def Y(y):
    return round((y - 140) * 1.047)


def xy(x, y):
    return [X(x), Y(y)]


class Area:
    def __init__(self, old_nodes):
        self.old = {n["id"]: n for n in old_nodes}
        self.nodes = []

    def _add(self, id_, kind, box, angle, label_pos, info, temps=None, cols=None, variant=None):
        old = self.old[id_]
        n = {"id": id_, "kind": kind}
        if variant:
            n["variant"] = variant
        n.update(box)
        n.update({"angle": angle, "label": old["label"], "label_pos": label_pos, "info_xy": xy(*info)})
        if temps:
            n["temps_xy"] = xy(*temps)
            n["temps_cols"] = cols or (2 if len(old["temps"]) == 4 else 1)
        n.update({"metrics": old["metrics"], "status_tag": old["status_tag"], "temps": old["temps"]})
        self.nodes.append(n)

    def box(self, id_, kind, x0, y0, x1, y1, info, label_pos="top", **kw):
        """Thiết bị đứng: khung bao (x0, y0)–(x1, y1) trên ảnh."""
        b = {"x": X(x0), "y": Y(y0), "w": X(x1) - X(x0), "h": Y(y1) - Y(y0)}
        self._add(id_, kind, b, 0, label_pos, info, **kw)

    def line(self, id_, kind, p0, p1, h, info, **kw):
        """Băng tải / vít tải: 2 đầu mút trên ảnh → quy đổi TRƯỚC rồi mới tính góc (Y giãn 4,7 %)."""
        (x0, y0), (x1, y1) = xy(*p0), xy(*p1)
        length = math.hypot(x1 - x0, y1 - y0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        b = {"x": round(cx - length / 2), "y": round(cy - h / 2), "w": round(length), "h": h}
        angle = round(math.degrees(math.atan2(y1 - y0, x1 - x0)), 1) if y1 != y0 else 0
        self._add(id_, kind, b, angle, "left" if angle else "top", info, **kw)


def basin(x0, y0, x1, y1):
    return {"kind": "basin", "x": X(x0), "y": Y(y0), "w": X(x1) - X(x0), "h": Y(y1) - Y(y0)}


def pipe(*pts):
    return {"kind": "pipe", "points": [xy(*p) for p in pts]}


def badge(x, y, text="pID"):
    return {"kind": "badge", "x": X(x), "y": Y(y), "text": text}


def arrow(text, text_at, *pts):
    return {"kind": "arrow_text", "x": X(text_at[0]), "y": Y(text_at[1]), "text": text,
            "points": [xy(*p) for p in pts], "text_xy": xy(*text_at)}


def build(old_area):
    a = Area(old_area["nodes"])
    # ── Hàng 1: máng dài + MLM1–3 → BTTL1 → tháp cán CM1 ──
    a.box("MLM1", "mixer", 148, 320, 246, 397, (150, 250))
    a.box("MLM2", "mixer", 262, 262, 382, 368, (322, 220))
    a.box("MLM3", "mixer", 418, 262, 532, 368, (473, 220))
    a.line("BTTL1", "conveyor", (508, 364), (830, 214), 22, (690, 145))
    a.box("CM1", "crusher", 822, 204, 886, 400, (892, 198), variant="mill", temps=(903, 272))
    # ── Hàng 2: máng dài + MLM4–6 → BTTL2 → CM2 → hồ QM1 → VT1 → CM3 → hồ QM2 → VT2 → C3T1 ──
    a.box("MLM4", "mixer", 148, 590, 246, 667, (154, 516))
    a.box("MLM5", "mixer", 264, 530, 382, 638, (323, 488))
    a.box("MLM6", "mixer", 414, 530, 532, 638, (473, 488))
    a.line("BTTL2", "conveyor", (508, 642), (828, 488), 22, (686, 420))
    a.box("CM2", "crusher", 822, 474, 886, 668, (892, 464), variant="mill", temps=(903, 540))
    a.box("QM1", "tank", 922, 600, 1202, 666, (1026, 494))
    a.line("VT1", "screw", (1105, 603), (1266, 444), 28, (1190, 360))
    a.box("CM3", "crusher", 1268, 474, 1332, 668, (1336, 463), variant="mill", temps=(1343, 540))
    a.box("QM2", "tank", 1365, 600, 1642, 666, (1466, 494))
    a.line("VT2", "screw", (1545, 604), (1710, 454), 28, (1636, 368))
    a.box("C3T1", "crusher", 1700, 506, 1823, 666, (1774, 444), variant="creper",
          temps=(1690, 690))
    # ── Hàng 3: BTCS1 → CCS1 → BTCS2 → CCS2 → BTCS3 → TL1 → CC1 (bàn dài) → bơm BC1 ──
    a.line("BTCS1", "conveyor", (156, 895), (368, 797), 20, (318, 690))
    a.box("CCS1", "crusher", 335, 812, 462, 945, (428, 748), variant="creper", temps=(333, 950))
    a.line("BTCS2", "conveyor", (386, 895), (598, 797), 20, (549, 690))
    a.box("CCS2", "crusher", 565, 812, 695, 945, (656, 748), variant="creper", temps=(572, 950))
    a.line("BTCS3", "conveyor", (616, 893), (829, 795), 20, (779, 690))
    a.box("TL1", "conveyor", 812, 830, 858, 850, (708, 864))
    a.box("CC1", "crusher", 862, 806, 982, 858, (932, 742), temps=(850, 760))
    a.box("BC1", "pump", 1266, 818, 1324, 945, (1204, 822), label_pos="left")
    decor = [
        basin(137, 327, 705, 400), basin(137, 596, 705, 670), basin(815, 868, 1255, 942),
        pipe((1716, 458), (1716, 520)),                                    # đầu VT2 → phễu C3T1
        pipe((1823, 627), (1884, 627), (1884, 682), (133, 682), (133, 858), (175, 858)),  # C3T1 → BTCS1
        arrow("Đến vít tải ngang", (1716, 752), (1294, 822), (1294, 752), (1712, 752)),
        arrow("Từ vít tải ngang", (1716, 897), (1700, 897), (1255, 897)),
        badge(792, 273), badge(792, 541), badge(1236, 542), badge(1667, 572),
        badge(304, 886), badge(534, 886), badge(996, 826),
    ]
    return {"key": old_area["key"], "label": old_area["label"], "width": 1800, "height": 900,
            "usage_box": {"x": X(1390), "y": Y(147), "w": X(1872) - X(1390), "h": Y(272) - Y(147)},
            "nodes": a.nodes, "decor": decor, "links": []}


def dump(layout):
    """Giữ kiểu file cũ: mỗi node / decor một dòng cho dễ review diff."""
    j = lambda o: json.dumps(o, ensure_ascii=False)  # noqa: E731
    out = ["{", f'  "key": {j(layout["key"])},', f'  "label": {j(layout["label"])},', '  "power": [']
    out.append(",\n".join(f"    {j(p)}" for p in layout["power"]))
    out += ["  ],", '  "areas": [']
    areas = []
    for a in layout["areas"]:
        head = {k: v for k, v in a.items() if k not in ("nodes", "decor", "links")}
        s = ["    {", "      " + j(head)[1:-1] + ","]
        s.append('      "nodes": [\n' + ",\n".join(f"        {j(n)}" for n in a["nodes"]) + "\n      ],")
        s.append('      "decor": [\n' + ",\n".join(f"        {j(d)}" for d in a["decor"]) + "\n      ],")
        s.append(f'      "links": {j(a["links"])}')
        s.append("    }")
        areas.append("\n".join(s))
    out.append(",\n".join(areas))
    out += ["  ]", "}"]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    layout = json.load(open(PATH, encoding="utf-8"))
    areas = []
    for area in layout["areas"]:
        if area["key"] == "khu-mu-vao":
            area = build(area)
        elif area["key"] in HIDE:
            area = {"key": area["key"], "label": area["label"], "hidden": True,
                    **{k: v for k, v in area.items() if k not in ("key", "label", "hidden")}}
        areas.append(area)
    layout["areas"] = areas
    text = dump(layout)
    json.loads(text)
    open(PATH, "w", encoding="utf-8").write(text)
    print("ok", PATH)
