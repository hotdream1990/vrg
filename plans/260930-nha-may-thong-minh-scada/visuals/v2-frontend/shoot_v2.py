"""Chụp Sơ đồ vận hành v2 (Khu mủ vào). Chế độ:
  that   — số thật từ dev API (ban ngày/đêm tuỳ lúc chụp)
  chay   — SỬA phản hồi /plant/live NGAY TRONG trình duyệt thành đúng số trên ảnh RELCO (máy chạy/dừng như ảnh)
Không mock trong code web. Ghi lại mọi request /meters/daily để kiểm chứng đã tắt (SHOW_POWER_AND_USAGE=false).
"""
import asyncio, json, sys
from playwright.async_api import async_playwright

TOK = open(sys.argv[1]).read().strip()
OUT = sys.argv[2]
URL = "http://localhost:5390/nha-may-thong-minh/so-do-van-hanh"

# Số trên ảnh RELCO 30/09 14:43: (Hz, A, [nhiệt độ theo thứ tự tag của node]); Hz 0 = dừng.
RELCO = {
    "MLM1": (41.56, 1.62), "MLM2": (44.22, 1.62), "MLM3": (41.66, 1.64), "MLM4": (0, 0),
    "MLM5": (50.00, 1.63), "MLM6": (49.93, 1.62), "BTTL1": (37.87, 5.50), "BTTL2": (29.96, 4.95),
    "CM1": (45.33, 31.03, [31.30, 32.80]), "CM2": (44.75, 47.47, [31.10, 33.50]),
    "QM1": (34.96, 5.42), "VT1": (24.87, 5.73), "CM3": (50.00, 43.12, [33.40, 34.60]),
    "QM2": (30.16, 4.65), "VT2": (0, 0), "C3T1": (0, 0, [31.40, 32.70, 30.90, 32.00]),
    "BTCS1": (0, 0), "CCS1": (0, 0, [32.10, 31.90, 30.50, 33.00]), "BTCS2": (0, 0),
    "CCS2": (0, 0, [31.70, 32.50, 33.60, 34.40]), "BTCS3": (0, 0),
    "CC1": (49.79, 45.41, [48.10, 77.30]), "TL1": (58.83, 5.16), "BC1": (1, None),
}
NODES = {}
daily_calls = []


async def keep_layout(route):
    resp = await route.fetch()
    data = await resp.json()
    for a in data["layout"]["areas"]:
        for n in a["nodes"]:
            NODES[n["id"]] = n
    await route.fulfill(response=resp)


async def fake_relco(route):
    resp = await route.fetch()
    data = await resp.json()
    at = data.get("fetched_at")
    vals = data["values"]
    for nid, spec in RELCO.items():
        n = NODES.get(nid)
        if not n:
            continue
        hz, amp = spec[0], spec[1]
        if n.get("status_tag"):
            vals[n["status_tag"]] = {"value": 1 if hz else 0, "at": at}
        for m, v in zip(n.get("metrics", []), (hz, amp)):
            vals[m["tag"]] = {"value": v, "at": at}
        for t, v in zip(n.get("temps", []), spec[2] if len(spec) > 2 else []):
            vals[t["tag"]] = {"value": v, "at": at}
    await route.fulfill(response=resp, body=json.dumps(data),
                        headers={**resp.headers, "content-type": "application/json"})


async def shot(b, mode, width, height, name, scale=1.5):
    ctx = await b.new_context(viewport={"width": width, "height": height}, device_scale_factor=scale, locale="vi-VN")
    await ctx.add_init_script(f"localStorage.setItem('vrg_token', '{TOK}')")
    await ctx.route("**/api/smart-factory/plant/layout*", keep_layout)
    if mode == "chay":
        await ctx.route("**/api/smart-factory/plant/live*", fake_relco)
    page = await ctx.new_page()
    page.on("request", lambda r: daily_calls.append(r.url) if "/meters/daily" in r.url else None)
    await page.goto(URL)
    await page.wait_for_selector(".pl-svg .pl-dev", timeout=20000)
    await page.wait_for_timeout(6500)   # qua 1 nhịp 5 s → số giả đã vào
    await page.screenshot(path=f"{OUT}/{name}.png", full_page=True)
    svg = page.locator(".pl-scroll")
    await svg.screenshot(path=f"{OUT}/{name}-khung.png")
    info = await page.evaluate("""() => ({
      tabs: document.querySelectorAll('.pl-area-card .ant-tabs').length,
      power: document.querySelectorAll('.pl-power').length,
      usage: document.querySelectorAll('.pl-usage, .pl-usagebox').length,
      faultLamps: document.querySelectorAll('.pl-lamp.fault').length,
      redLamps: document.querySelectorAll('.pl-lamp.fault.stop').length,
      run: document.querySelectorAll('.pl-dev.run').length,
      stop: document.querySelectorAll('.pl-dev.stop').length,
      hscroll: document.documentElement.scrollWidth > window.innerWidth,
    })""")
    print(name, info)
    await ctx.close()


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        await shot(b, "chay", 1920, 1200, "v2-chay-1920")
        await shot(b, "that", 1920, 1200, "v2-that-1920")
        await shot(b, "chay", 1280, 900, "v2-chay-1280", scale=1)
        await shot(b, "chay", 390, 844, "v2-chay-390", scale=2)
        await b.close()
    print("meters/daily calls:", len(daily_calls))

asyncio.run(main())
