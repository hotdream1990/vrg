"""Sinh apps/api/app/services/plant_layouts/phu_rieng.json (một lần) — tag lấy ĐÚNG tên trong file tag."""
import json, math, sys
ROOT = "/Volumes/Work/biz-project/VRG"
TAGS = json.load(open(f"{ROOT}/plans/260930-nha-may-thong-minh-scada/historian-tags-phu-rieng.json"))
OUT = f"{ROOT}/apps/api/app/services/plant_layouts/phu_rieng.json"

TEMP_LABELS = [("Main Left", "Trái"), ("Main Right", "Phải"), ("Upper Left", "Trên trái"),
               ("Upper Right", "Trên phải"), ("Lower Left", "Dưới trái"), ("Lower Right", "Dưới phải"),
               ("Champer", "Buồng")]


def tag(*cands):
    for c in cands:
        if c in TAGS:
            return c
    return None


def parts(code, extra_metrics=()):
    hz = tag(f"{code} - Frequence", f"{code}- Frequence")
    a = tag(f"{code} - Current")
    metrics = []
    if hz:
        metrics.append({"key": "hz", "tag": hz, "unit": "Hz"})
    if a:
        metrics.append({"key": "a", "tag": a, "unit": "A"})
    metrics += list(extra_metrics)
    temps = []
    for word, label in TEMP_LABELS:
        t = [k for k in TAGS if k.startswith(f"{code} - {word} Temp")]
        assert len(t) <= 1, t
        if t:
            temps.append({"label": label, "tag": t[0]})
    return metrics, tag(f"{code} - Running Status"), temps


def node(id_, kind, x, y, w, h, angle=0, label=None, label_pos="top", metrics=None, status=None,
         temps=None, code=None, extra_metrics=()):
    m, s, t = parts(code or id_, extra_metrics)
    return {"id": id_, "kind": kind, "x": round(x), "y": round(y), "w": round(w), "h": round(h),
            "angle": angle, "label": label or id_, "label_pos": label_pos,
            "metrics": m if metrics is None else metrics,
            "status_tag": s if status is None else status, "temps": t if temps is None else temps}


def line(id_, kind, p0, p1, h=24, label_pos="top"):
    """Băng tải / vít tải cho bằng 2 đầu mút → hộp (x, y, w = chiều dài, h) + angle quanh TÂM hộp."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy)
    cx, cy = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    return node(id_, kind, cx - length / 2, cy - h / 2, length, h,
                angle=round(math.degrees(math.atan2(dy, dx)), 1), label_pos=label_pos)


def basin(x, y, w, h):
    return {"kind": "basin", "x": x, "y": y, "w": w, "h": h}


def pipe(*pts):
    return {"kind": "pipe", "points": [list(p) for p in pts]}


def arrow(text, x, y, *pts):
    return {"kind": "arrow_text", "x": x, "y": y, "text": text, "points": [list(p) for p in pts]}


def chain(*ids):
    return [[a, b] for a, b in zip(ids, ids[1:])]


# ── Khu mủ vào: bám ảnh RELCO (khung màn 1793×860 px → 1800×900). Quy ước web: khối nhãn + Hz/A ở
# cạnh `label_pos` của khung CHƯA xoay, ô nhiệt độ ở cạnh đối diện → băng tải nghiêng đặt nhãn "left"
# (cạnh trái khung không chạm thân băng tải) và chừa ~100 đơn vị trống bên trái mỗi băng tải.
khu_mu_vao = {
    "key": "khu-mu-vao", "label": "Khu mủ vào", "width": 1800, "height": 900,
    "nodes": [
        # Hàng 1: 3 máy làm mủ trên máng → băng tải lên CM1
        node("MLM1", "mixer", 35, 175, 90, 90), node("MLM2", "mixer", 140, 128, 90, 90),
        node("MLM3", "mixer", 245, 128, 90, 90),
        line("BTTL1", "conveyor", (470, 246), (723, 105), label_pos="left"),
        node("CM1", "crusher", 705, 90, 90, 130),
        # Hàng 2: MLM4–6 → BTTL2 → CM2 → hồ QM1 → VT1 → CM3 → hồ QM2 → VT2 → C3T1
        node("MLM4", "mixer", 35, 457, 90, 90), node("MLM5", "mixer", 140, 410, 90, 90),
        node("MLM6", "mixer", 245, 410, 90, 90),
        line("BTTL2", "conveyor", (470, 528), (723, 387), label_pos="left"),
        node("CM2", "crusher", 705, 372, 90, 130),
        node("QM1", "tank", 815, 505, 230, 80),
        line("VT1", "screw", (990, 520), (1135, 240), h=26, label_pos="left"),
        node("CM3", "crusher", 1130, 260, 150, 130),
        node("QM2", "tank", 1300, 505, 230, 80),
        line("VT2", "screw", (1475, 520), (1640, 235), h=26, label_pos="left"),
        node("C3T1", "crusher", 1635, 255, 150, 150),
        # Hàng 3: BTCS1 → CCS1 → BTCS2 → CCS2 → BTCS3 → CC1 (TL1 cạnh) → bơm BC1
        line("BTCS1", "conveyor", (130, 810), (300, 715), label_pos="left"),
        node("CCS1", "crusher", 300, 720, 120, 120),
        line("BTCS2", "conveyor", (540, 810), (710, 715), label_pos="left"),
        node("CCS2", "crusher", 710, 720, 120, 120),
        line("BTCS3", "conveyor", (950, 810), (1120, 715), label_pos="left"),
        node("CC1", "crusher", 1120, 700, 150, 70),
        node("TL1", "conveyor", 1300, 740, 100, 18),
        node("BC1", "pump", 1560, 700, 60, 90, label_pos="right"),
    ],
    "decor": [
        basin(30, 195, 570, 80), basin(30, 475, 570, 80), basin(1110, 775, 280, 80),
        pipe((795, 200), (830, 200), (830, 505)),                                      # CM1 → hồ QM1
        pipe((1785, 380), (1793, 380), (1793, 590), (18, 590), (18, 810), (120, 810)),  # C3T1 → BTCS1
        arrow("Đến vít tải ngang", 1616, 645, (1590, 700), (1590, 645), (1610, 645)),
        arrow("Từ vít tải ngang", 1401, 800, (1370, 800), (1395, 800)),
    ],
    "links": chain("MLM1", "MLM2", "MLM3", "BTTL1", "CM1") + chain("MLM4", "MLM5", "MLM6", "BTTL2",
             "CM2", "QM1", "VT1", "CM3", "QM2", "VT2", "C3T1")
             + chain("BTCS1", "CCS1", "BTCS2", "CCS2", "BTCS3", "CC1", "BC1"),
}

# ── Vít tải ngang (dây chuyền 2): chưa có ảnh mẫu — xếp theo dòng chảy, 2 hàng trái → phải ──
vit_tai_ngang = {
    "key": "vit-tai-ngang", "label": "Vít tải ngang", "width": 1800, "height": 900,
    "nodes": [
        node("VTN", "screw", 165, 316, 470, 28),
        node("C3T2", "crusher", 660, 260, 150, 150),
        line("BTCS4", "conveyor", (925, 400), (1095, 305), label_pos="left"),
        node("CCS3", "crusher", 1095, 310, 120, 120),
        line("BTCS5", "conveyor", (1335, 400), (1505, 305), label_pos="left"),
        node("CCS4", "crusher", 1505, 310, 120, 120),
        line("BTCS6", "conveyor", (130, 810), (300, 715), label_pos="left"),
        node("CCS5", "crusher", 300, 720, 120, 120),
        line("BTCS7", "conveyor", (540, 810), (710, 715), label_pos="left"),
        node("CC2", "crusher", 710, 700, 150, 70),
        node("TL2", "conveyor", 890, 740, 100, 18),
        node("BC2", "pump", 1060, 700, 60, 90, label_pos="right"),
    ],
    "decor": [
        basin(700, 775, 330, 80),
        pipe((1625, 370), (1780, 370), (1780, 540), (18, 540), (18, 810), (120, 810)),  # CCS4 → BTCS6
        arrow("Từ khu mủ vào", 41, 330, (10, 330), (35, 330)),
        arrow("Đến hầm sấy", 1116, 640, (1090, 700), (1090, 640), (1110, 640)),
    ],
    "links": chain("VTN", "C3T2", "BTCS4", "CCS3", "BTCS5", "CCS4")
             + chain("BTCS6", "CCS5", "BTCS7", "CC2", "BC2"),
}

# ── Hầm sấy: thùng khuấy → 4 băng tải → hầm 12 buồng (Z01–Z12) + 6 quạt bên dưới ──
FAN_X = (170, 430, 690, 950, 1210, 1470)
FANS = ("QC01", "QC02", "QN01", "QN02", "QHL", "QK")


def fan(code, x):
    vib = tag(f"{code} - Vibration")
    extra = [{"key": "vib", "tag": vib, "unit": "mm/s"}] if vib else []
    return node(code, "fan", x, 670, 100, 100, label_pos="right", extra_metrics=extra)


ham_say = {
    "key": "ham-say", "label": "Hầm sấy", "width": 1800, "height": 900,
    "nodes": [
        node("TKMM1", "mixer", 200, 110, 100, 100), node("TKMM2", "mixer", 340, 110, 100, 100),
        *[node(f"BTCLM{i + 1}", "conveyor", 480 + i * 220, 150, 180, 22) for i in range(4)],
        node("XDT", "motor", 20, 440, 80, 80, label_pos="bottom", status="XDT_bOutAuto", metrics=[],
             temps=[]),
        *[node(f"Z{i + 1:02d}", "zone", 130 + i * 125, 410, 115, 150) for i in range(12)],
        *[fan(c, x) for c, x in zip(FANS, FAN_X)],
    ],
    "decor": [
        basin(120, 390, 1520, 190),
        pipe((1320, 161), (1360, 161), (1360, 300), (60, 300), (60, 440)),  # BTCLM4 → cửa hầm
        *[pipe((x + 50, 670), (x + 50, 580)) for x in FAN_X],               # quạt → hầm
        arrow("Từ vít tải ngang", 41, 160, (10, 160), (35, 160)),
        arrow("Đến đóng gói", 1671, 485, (1640, 485), (1665, 485)),
    ],
    "links": chain("TKMM1", "TKMM2", "BTCLM1", "BTCLM2", "BTCLM3", "BTCLM4") + [["XDT", "Z01"]],
}

# ── Đóng gói ──
dong_goi = {
    "key": "dong-goi", "label": "Đóng gói", "width": 1200, "height": 450,
    "nodes": [
        node("SR", "motor", 150, 170, 120, 120),
        node("RobotTotalCount", "counter", 600, 150, 300, 160, label="Số bành",
             metrics=[{"key": "count", "tag": "RobotTotalCount", "unit": "bành"}], temps=[]),
    ],
    "decor": [arrow("Từ hầm sấy", 41, 230, (10, 230), (35, 230))],
    "links": [["SR", "RobotTotalCount"]],
}

layout = {
    "key": "phu_rieng",
    "power": [
        {"label": "Volt AB", "unit": "V", "tag": "PM - VoltAB"},
        {"label": "Volt BC", "unit": "V", "tag": "PM - VoltBC"},
        {"label": "Volt CA", "unit": "V", "tag": "PM - VoltCA"},
        {"label": "Current A", "unit": "A", "tag": "PM - CurrentA"},
        {"label": "Current B", "unit": "A", "tag": "PM - CurrentB"},
        {"label": "Current C", "unit": "A", "tag": "PM - CurrentC"},
        {"label": "Power", "unit": "kW", "tag": "PM - Power"},
    ],
    "areas": [khu_mu_vao, vit_tai_ngang, ham_say, dong_goi],
}


def dump(obj):
    return json.dumps(obj, ensure_ascii=False)


def render(lay):
    out = ['{', f'  "key": {dump(lay["key"])},', '  "power": [']
    out += [f'    {dump(p)}' + (',' if i < len(lay["power"]) - 1 else '') for i, p in enumerate(lay["power"])]
    out += ['  ],', '  "areas": [']
    for ai, a in enumerate(lay["areas"]):
        out.append('    {')
        out.append(f'      "key": {dump(a["key"])}, "label": {dump(a["label"])}, '
                   f'"width": {a["width"]}, "height": {a["height"]},')
        for sect in ("nodes", "decor"):
            out.append(f'      "{sect}": [')
            items = a[sect]
            out += [f'        {dump(n)}' + (',' if i < len(items) - 1 else '') for i, n in enumerate(items)]
            out.append('      ],')
        out.append(f'      "links": {dump(a["links"])}')
        out.append('    }' + (',' if ai < len(lay["areas"]) - 1 else ''))
    out += ['  ]', '}']
    return "\n".join(out) + "\n"


text = render(layout)
assert json.loads(text) == layout
open(OUT, "w").write(text)
print("written", OUT, len(text.splitlines()), "lines")
