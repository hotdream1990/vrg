"""Test bố cục Sơ đồ vận hành (`plant_layouts/*.json` + loader) — thuần, không cần DB/SQL Server.

`fixtures/historian-tags-phu-rieng.json` = 209 tag THẬT đọc từ bảng `Tag` Historian Phú Riềng
(30/09/2026, tên → mô tả): bố cục gõ sai một tag là truy vấn cả khu hỏng → test chặn ở đây.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import scada_historian_sql as hsql
from app.services import scada_plant_layout as plant

REAL_TAGS: dict[str, str] = json.loads(
    (Path(__file__).parent / "fixtures" / "historian-tags-phu-rieng.json").read_text("utf-8"))
LAYOUT = plant.get_layout("phu_rieng")
KINDS = {"mixer", "conveyor", "screw", "crusher", "tank", "pump", "fan", "zone", "motor", "counter"}
DECOR = {"basin", "pipe", "arrow_text", "badge"}
AREAS = ["khu-mu-vao", "vit-tai-ngang", "ham-say", "dong-goi"]  # 03/10/2026: bật lại cả 4 khu
POWER = ["PM - VoltAB", "PM - VoltBC", "PM - VoltCA", "PM - CurrentA", "PM - CurrentB",
         "PM - CurrentC", "PM - Power"]
#: Tag không thuộc sơ đồ: chỉ số ngày (điện lũy kế · nước) + điện áp pha (hợp đồng chỉ lấy dây).
NOT_ON_DIAGRAM = ("PM_EnergyReal", "Water_", "Sys", "PM - VoltAN", "PM - VoltBN", "PM - VoltCN")


def _area_node_tags(area: dict) -> list[str]:
    return [t for n in area["nodes"] for t in plant.node_tags(n)]


def test_loader_keys_cache_and_rejects_bad_keys() -> None:
    assert "phu_rieng" in plant.layout_keys()
    assert LAYOUT is not None and LAYOUT["key"] == "phu_rieng"
    assert plant.get_layout("phu_rieng") is LAYOUT  # cache trong bộ nhớ
    for bad in ("", "khong_co", "../phu_rieng", "Phu_Rieng", "phu_rieng.json", None, 1):
        assert plant.get_layout(bad) is None  # type: ignore[arg-type]


def _in(area: dict, x: float, y: float) -> bool:
    return 0 <= x <= area["width"] and 0 <= y <= area["height"]


def _apart(a: tuple, b: tuple) -> bool:
    """Hai hình chữ nhật (x, y, w, h) không chồng nhau."""
    return a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1]


def _text_rects(area: dict) -> list[tuple[str, tuple]]:
    """Khối chữ, cỡ ước theo web (ô số cao 20, dòng 23, khối ~105 rộng) + bảng tiêu thụ ở cuối."""
    out = []
    for n in area["nodes"]:
        rows = max(len(n["metrics"]), 1)
        out.append((n["id"], (*n["info_xy"], 105 if n["metrics"] else 60, 18 + 23 * rows)))
        if n.get("temps_xy"):
            cols, k = n["temps_cols"], len(n["temps"])
            out.append((n["id"] + " °C", (*n["temps_xy"], 90 * cols - 10, 23 * -(-k // cols))))
    for d in area["decor"]:
        if d["kind"] == "badge":
            out.append(("badge", (d["x"], d["y"], 30, 19)))
        elif d.get("text_xy"):
            out.append((d["text"], (d["text_xy"][0], d["text_xy"][1] - 9, 8.2 * len(d["text"]), 18)))
    u = area["usage_box"]
    return [*out, ("usage_box", (u["x"], u["y"], u["w"], u["h"]))]


def test_areas_order_power_and_frame() -> None:
    assert [a["key"] for a in LAYOUT["areas"]] == AREAS
    assert [a["key"] for a in plant.visible_areas(LAYOUT)] == AREAS  # không còn khu ẩn
    assert all(plant.find_area(LAYOUT, k) is not None for k in AREAS)
    assert [p["tag"] for p in LAYOUT["power"]] == POWER
    assert [p["unit"] for p in LAYOUT["power"]] == ["V"] * 3 + ["A"] * 3 + ["kW"]
    for a in LAYOUT["areas"]:
        assert a["label"] and a["width"] > 0 and a["height"] > 0


def test_every_layout_tag_is_real_and_valid() -> None:
    used = [t for a in LAYOUT["areas"] for t in _area_node_tags(a)] + POWER
    assert [t for t in used if t not in REAL_TAGS] == []
    assert all(hsql.valid_tag(t) for t in used)


def test_every_real_tag_on_exactly_one_area() -> None:
    per_area = {a["key"]: {t.lower() for t in _area_node_tags(a)} for a in LAYOUT["areas"]}
    for tag in REAL_TAGS:
        hits = [k for k, tags in per_area.items() if tag.lower() in tags]
        if tag.startswith(NOT_ON_DIAGRAM) or tag in POWER:
            assert hits == [], tag
        else:
            assert len(hits) == 1, (tag, hits)
    # Không trùng tag trong cùng khu (một cột Historian chỉ được một chỗ).
    for a in LAYOUT["areas"]:
        tags = [t.lower() for t in _area_node_tags(a)]
        assert len(tags) == len(set(tags)), a["key"]


def test_nodes_ids_kinds_geometry_links_decor() -> None:
    """Hình học + trường v2 tuỳ chọn (`hidden`, `usage_box`, `info_xy`/`temps_xy` tuyệt đối trong
    khung, `temps_cols` 1|2, `variant` chỉ cho crusher)."""
    ids = [n["id"] for a in LAYOUT["areas"] for n in a["nodes"]]
    assert len(ids) == len(set(ids))
    for a in LAYOUT["areas"]:
        mine = {n["id"] for n in a["nodes"]}
        u = a.get("usage_box")
        assert isinstance(a.get("hidden", False), bool)
        assert u is None or (_in(a, u["x"], u["y"]) and _in(a, u["x"] + u["w"], u["y"] + u["h"]))
        for n in a["nodes"]:
            assert n["kind"] in KINDS and n["label_pos"] in {"top", "bottom", "left", "right"}
            assert n["label"] and n["w"] > 0 and n["h"] > 0 and -90 <= n["angle"] <= 90
            # xoay quanh tâm → tâm phải trong khung
            assert _in(a, n["x"] + n["w"] / 2, n["y"] + n["h"] / 2), n["id"]
            assert all({"key", "tag", "unit"} <= set(m) for m in n["metrics"])
            assert all({"label", "tag"} <= set(t) for t in n["temps"])
            assert "variant" not in n or (n["kind"] == "crusher" and n["variant"] in ("mill", "creper"))
            assert all(k not in n or (len(n[k]) == 2 and _in(a, *n[k])) for k in ("info_xy", "temps_xy"))
            assert "temps_xy" not in n or (n["temps"] and n["temps_cols"] in (1, 2)), n["id"]
            if n["angle"] and "info_xy" not in n:  # khối nhãn theo khung CHƯA xoay → đè thân nghiêng
                assert n["label_pos"] in ("left", "right"), n["id"]
        assert all(len(pair) == 2 and set(pair) <= mine for pair in a["links"]), a["key"]
        for d in a["decor"]:
            assert d["kind"] in DECOR
            pts = d.get("points") or [[d["x"], d["y"]], [d["x"] + d.get("w", 0), d["y"] + d.get("h", 0)]]
            assert all(_in(a, x, y) for x, y in pts), d
            if d["kind"] == "arrow_text":  # đầu mũi tên ở điểm cuối, hướng nào cũng được (v2)
                # Không chữ = chỉ đầu mũi tên (cuối ống hồi vào BTCS1); có text_xy thì phải có chữ.
                assert len(d["points"]) >= 2 and d["points"][-2] != d["points"][-1], d
                assert "text_xy" not in d or (d.get("text") and _in(a, *d["text_xy"])), d
            assert d["kind"] != "badge" or d["text"], d


def test_khu_mu_vao_follows_relco_screen() -> None:
    area = plant.find_area(LAYOUT, "khu-mu-vao")
    nodes = {n["id"]: n for n in area["nodes"]}
    of = lambda key, v: {k for k, n in nodes.items() if n.get(key) == v}  # noqa: E731
    assert of("kind", "mixer") == {f"MLM{i}" for i in range(1, 7)} and of("kind", "pump") == {"BC1"}
    assert of("kind", "tank") == {"QM1", "QM2"} and of("kind", "screw") == {"VT1", "VT2"}
    assert of("variant", "mill") == {"CM1", "CM2", "CM3"}
    assert of("variant", "creper") == {"CCS1", "CCS2", "C3T1"}
    assert all("info_xy" in n for n in nodes.values()) and area["links"] == []
    temps = {k: (len(n["temps"]), n.get("temps_cols")) for k, n in nodes.items() if n["temps"]}
    assert temps == {"CM1": (2, 1), "CM2": (2, 1), "CM3": (2, 1), "CC1": (2, 1),
                     "C3T1": (4, 2), "CCS1": (4, 2), "CCS2": (4, 2)}
    arrows = [d for d in area["decor"] if d["kind"] == "arrow_text" and d.get("text")]
    assert [d["text"] for d in arrows] == ["Đến vít tải ngang", "Từ vít tải ngang"]
    heads = [d["points"][-2:] for d in area["decor"] if d["kind"] == "arrow_text" and not d.get("text")]
    assert len(heads) == 1 and heads[0][1][0] > heads[0][0][0]  # ống hồi → BTCS1: đầu mũi tên chỉ PHẢI
    (x0, _), (x1, _) = arrows[1]["points"][-2:]  # "Từ vít tải ngang" chỉ sang TRÁI như RELCO
    assert x1 < x0 and arrows[1]["text_xy"][0] > x0
    assert [d["text"] for d in area["decor"] if d["kind"] == "badge"] == ["pID"] * 7
    rects = _text_rects(area)
    for i, (na, ra) in enumerate(rects):  # chữ không đè chữ (nhãn+ô số · °C · badge · mũi tên · bảng)
        assert _in(area, *ra[:2]) and _in(area, ra[0] + ra[2], ra[1] + ra[3]), na
        assert [nb for nb, rb in rects[i + 1:] if not _apart(ra, rb)] == [], na
    for n in area["nodes"]:  # vùng bảng tiêu thụ (web tạm tắt, sẽ bật lại) không có thiết bị
        r = max(n["w"], n["h"]) / 2  # hình vuông bao cả khi xoay
        assert _apart((n["x"] + n["w"] / 2 - r, n["y"] + n["h"] / 2 - r, 2 * r, 2 * r), rects[-1][1])


def test_area_tags_adds_power_dedupes_and_hidden_or_unknown_area_is_none() -> None:
    tags = plant.area_tags(LAYOUT, "khu-mu-vao")
    assert tags[-len(POWER):] == POWER and "C3T1 - Upper Left Temperture" in tags
    assert len({t.lower() for t in tags}) == len(tags)
    assert plant.area_tags(LAYOUT, "khong-co") is None and "RobotTotalCount" in plant.area_tags(LAYOUT, "dong-goi")
    fake = {"power": [{"tag": "A"}], "areas": [{"key": "k", "nodes": [
        {"metrics": [{"tag": "A"}, {"tag": "b"}], "status_tag": "B", "temps": []}]},
        {"key": "h", "hidden": True, "nodes": [{"metrics": [{"tag": "Z"}], "temps": []}]}]}
    assert plant.area_tags(fake, "k") == ["A", "b"] == plant.all_tags(fake) and not plant.area_tags(fake, "h")
    every = plant.all_tags(LAYOUT)  # mọi khu đều hiện → đọc tag của cả 4 khu trong MỘT truy vấn
    for a in AREAS:
        assert set(plant.area_tags(LAYOUT, a)) <= set(every), a
    assert "Z01 - Champer Temperature" in every and "RobotTotalCount" in every
    hidden = {**LAYOUT, "areas": [{**a, "hidden": a["key"] != "khu-mu-vao"} for a in LAYOUT["areas"]]}
    assert plant.all_tags(hidden) == plant.area_tags(LAYOUT, "khu-mu-vao")  # khu ẩn: không đọc tag
    pub = plant.public_layout(hidden)
    assert [a["key"] for a in pub["areas"]] == ["khu-mu-vao"] and pub["power"] == LAYOUT["power"]
    assert len(hidden["areas"]) == 4  # bản sao — dict gốc không bị sửa


def test_plant_query_fits_openquery_limit() -> None:
    """OPENQUERY nhận chuỗi truy vấn tối đa 8 KB — kể cả khi bật lại mọi khu ẩn (đọc 1 lần/nhà máy)."""
    unhidden = {**LAYOUT, "areas": [{**a, "hidden": False} for a in LAYOUT["areas"]]}
    for layout in (LAYOUT, unhidden):
        assert len(hsql.latest_query("INSQL", plant.all_tags(layout), 1)) < 8000


@pytest.mark.parametrize("key", plant.layout_keys())
def test_every_layout_file_is_well_formed(key: str) -> None:
    """Mọi file bố cục (không chỉ phu_rieng): đủ khoá, kind hợp lệ, tag qua regex, id không trùng —
    file hỏng thì hỏng ở CI chứ không thành 500 khi người dùng mở màn."""
    layout = plant.get_layout(key)
    assert layout and layout["key"] == key and layout.get("label")
    assert all(hsql.valid_tag(p["tag"]) and p["label"] and p["unit"] for p in layout["power"])
    ids = [n["id"] for a in layout["areas"] for n in a["nodes"]]
    assert len(ids) == len(set(ids))
    for a in layout["areas"]:
        assert a["key"] and a["label"] and a["width"] > 0 and a["height"] > 0
        for n in a["nodes"]:
            assert n["kind"] in KINDS and all(hsql.valid_tag(t) for t in plant.node_tags(n)), n["id"]
    first = plant.visible_areas(layout)[0]["key"]  # ít nhất một khu hiện, không thì màn trống
    assert plant.all_tags(layout) and set(plant.area_tags(layout, first)) <= set(plant.all_tags(layout))
