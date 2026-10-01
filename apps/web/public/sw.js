/* Service worker VRG — CHỈ để nhận Web Push (chuông thông báo). Không cache, không chạy offline.

   Máy chủ gửi JSON {title, body, url, tag} (đã mã hoá RFC 8291, trình duyệt tự giải mã).
   - push: hiện thông báo của hệ điều hành + báo các tab đang mở để chuông tải lại số chưa đọc.
   - bấm thông báo: có tab VRG đang mở → đưa lên trước và nhờ SPA tự chuyển trang (giữ phiên, qua
     hàng rào "chưa lưu"). SPA không trả lời trong NAV_ACK_MS (tab đang ở /login, trang công khai,
     đang tải) → tải hẳn trang đích trong tab đó; chưa đăng nhập thì ProtectedRoute đưa về /login
     và đăng nhập xong quay lại đúng trang. Chưa có tab nào → mở cửa sổ mới tới đúng trang. */

const NAV_ACK_MS = 1000;

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

function readPayload(event) {
  try {
    return event.data ? event.data.json() : {};
  } catch {
    return { body: event.data ? event.data.text() : "" };
  }
}

/** Chỉ nhận đường dẫn trong chính web — không bao giờ mở trang ngoài từ thông báo.
 *  "//host" và "/\host" đều bị trình duyệt hiểu là địa chỉ của host khác. */
function localUrl(url) {
  return typeof url === "string" && url.startsWith("/") && !url.startsWith("//") && !url.startsWith("/\\")
    ? url : "/";
}

async function windowClients() {
  return self.clients.matchAll({ type: "window", includeUncontrolled: true });
}

/** Nhờ SPA trong tab tự chuyển trang; true = SPA đã nhận việc (trả lời qua MessageChannel). */
function askSpaToNavigate(client, url) {
  return new Promise((resolve) => {
    const channel = new MessageChannel();
    const timer = setTimeout(() => resolve(false), NAV_ACK_MS);
    channel.port1.onmessage = (e) => {
      clearTimeout(timer);
      resolve(Boolean(e.data && e.data.ok));
    };
    try {
      client.postMessage({ type: "vrg-navigate", url }, [channel.port2]);
    } catch {
      clearTimeout(timer);
      resolve(false);
    }
  });
}

async function tryFocus(client) {
  try { await client.focus(); } catch { /* trình duyệt không cho focus — vẫn chuyển trang */ }
}

self.addEventListener("push", (event) => {
  const data = readPayload(event);
  const url = localUrl(data.url);
  const tag = data.tag || undefined;
  event.waitUntil((async () => {
    await self.registration.showNotification(data.title || "VRG", {
      body: data.body || "",
      icon: "/logo-vrg.png",
      badge: "/logo-vrg.png",
      // Cùng thẻ thì thay thông báo cũ — renotify để vẫn kêu/rung cho tin mới (Chrome báo lỗi nếu
      // renotify mà không có tag, nên chỉ gắn khi có tag).
      ...(tag ? { tag, renotify: true } : {}),
      data: { url },
    });
    for (const client of await windowClients()) client.postMessage({ type: "vrg-push" });
  })());
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = localUrl(event.notification.data && event.notification.data.url);
  event.waitUntil((async () => {
    const all = await windowClients();   // matchAll chỉ trả tab CÙNG nguồn với service worker
    const client = all.find((c) => c.focused) || all[0];
    if (!client) {
      await self.clients.openWindow(url);
      return;
    }
    // Focus NGAY (quyền đưa cửa sổ lên trước chỉ có trong chốc lát sau cú bấm), rồi mới chờ SPA.
    await tryFocus(client);
    if (await askSpaToNavigate(client, url)) return;
    try {
      const moved = await client.navigate(url);   // null = tab đã sang trang khác nguồn
      if (moved) {
        await tryFocus(moved);
        return;
      }
    } catch { /* tab chưa do service worker này quản lý — mở cửa sổ mới */ }
    try { await self.clients.openWindow(url); } catch { /* trình duyệt không cho mở thêm cửa sổ */ }
  })());
});
