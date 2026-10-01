/* Web Push phía trình duyệt — "Nhận thông báo trên máy này" (chuông thông báo, chốt 01/10/2026).

   Mỗi trình duyệt đăng ký service worker `/sw.js` rồi gửi đăng ký push lên server gắn với tài khoản
   ĐANG đăng nhập. Máy dùng chung: đăng xuất / hết phiên / tài khoản không có chuông thì gỡ; người
   sau đăng nhập (đã cho phép, chưa tự tắt) tự đăng ký lại.
   Lệnh GHI cố ý KHÔNG dùng `apiFetch` (như access-log-client): lỗi 401 của một lần đăng ký ngầm
   không được đá người dùng về /login, và không được phát `DATA_SAVED_EVENT` làm bảng nhắc việc tải lại. */

import { authHeaders } from "./auth-token";
import { API, apiFetch } from "./http";

/** Trạng thái công tắc trên máy này. */
export type PushState = "unsupported" | "ios-home-screen" | "denied" | "on" | "off";

const SW_URL = "/sw.js";
const DETACH_TIMEOUT_MS = 2500;   // đăng xuất không bao giờ phải chờ lâu hơn chừng này
// Tài khoản đã tự tắt trên máy này → đừng tự bật lại. Theo TỪNG tài khoản: người trước tắt không làm người sau mất.
const OPT_OUT_PREFIX = "vrg_push_off:";

export function isPushSupported(): boolean {
  return typeof window !== "undefined" && window.isSecureContext
    && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

function isIos(): boolean {
  // iPadOS tự xưng là Mac — nhận ra nhờ màn cảm ứng.
  return /iPad|iPhone|iPod/.test(navigator.userAgent)
    || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function isStandalone(): boolean {
  return window.matchMedia?.("(display-mode: standalone)").matches
    || (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

/** iPhone/iPad: Safari chỉ cho thông báo khi web đã "Thêm vào màn hình chính" và mở từ biểu tượng đó. */
export function needsIosHomeScreen(): boolean {
  return isIos() && !isStandalone();
}

export function permission(): NotificationPermission | "unsupported" {
  return typeof window !== "undefined" && "Notification" in window ? Notification.permission : "unsupported";
}

function setOptOut(username: string, off: boolean): void {
  try {
    if (off) localStorage.setItem(OPT_OUT_PREFIX + username, "1");
    else localStorage.removeItem(OPT_OUT_PREFIX + username);
  } catch { /* trình duyệt chặn lưu trữ — bỏ qua */ }
}

function isOptedOut(username: string): boolean {
  try { return localStorage.getItem(OPT_OUT_PREFIX + username) === "1"; } catch { return false; }
}

/** Đường dẫn trong chính web ("//host" và "/\host" là địa chỉ host khác) — khớp `localUrl` của sw.js. */
export function isLocalPath(url: unknown): url is string {
  return typeof url === "string" && url.startsWith("/") && !url.startsWith("//") && !url.startsWith("/\\");
}

function b64urlToBytes(s: string): Uint8Array<ArrayBuffer> {
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (s.length % 4)) % 4);
  return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
}

/** Đăng ký cũ có cùng khoá máy chủ không (khoá đổi thì phải đăng ký lại). Trình duyệt không cho
 *  biết khoá → coi như cùng, tránh đăng ký lại mỗi lần mở trang. */
function sameKey(current: ArrayBuffer | null, key: Uint8Array): boolean {
  if (!current) return true;
  const a = new Uint8Array(current);
  return a.length === key.length && a.every((v, i) => v === key[i]);
}

async function currentSubscription(): Promise<PushSubscription | null> {
  if (!isPushSupported()) return null;
  const reg = await navigator.serviceWorker.getRegistration("/");
  return reg ? reg.pushManager.getSubscription() : null;
}

async function postPush(path: string, body: unknown): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("Không kết nối được máy chủ — kiểm tra mạng hoặc thử lại.");
  }
  if (res.ok) return;
  let msg = `Máy chủ từ chối (HTTP ${res.status}).`;
  try {
    const j = await res.json();
    if (typeof j?.detail === "string") msg = j.detail;
  } catch { /* body không phải JSON */ }
  throw new Error(msg);
}

/** Đăng ký service worker → lấy (hoặc tạo) đăng ký push đúng khoá máy chủ → gửi lên server. */
async function subscribeAndSave(): Promise<void> {
  await navigator.serviceWorker.register(SW_URL, { scope: "/", updateViaCache: "none" });
  const reg = await navigator.serviceWorker.ready;
  const { public_key } = await apiFetch<{ public_key: string }>("/api/push/key");
  const key = b64urlToBytes(public_key);
  let sub = await reg.pushManager.getSubscription();
  if (sub && !sameKey(sub.options.applicationServerKey, key)) {
    await sub.unsubscribe().catch(() => false);
    sub = null;
  }
  sub = sub ?? await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
  const json = sub.toJSON();
  await postPush("/api/push/subscribe", {
    endpoint: json.endpoint, keys: { p256dh: json.keys?.p256dh ?? "", auth: json.keys?.auth ?? "" },
  });
}

/** Trạng thái hiện tại của công tắc trên máy này. */
export async function pushState(): Promise<PushState> {
  if (needsIosHomeScreen()) return "ios-home-screen";
  if (!isPushSupported()) return "unsupported";
  if (Notification.permission === "denied") return "denied";
  if (Notification.permission !== "granted") return "off";
  try {
    return (await currentSubscription()) ? "on" : "off";
  } catch {
    return "off";
  }
}

/** Người dùng BẬT: xin quyền (phải gọi ngay trong cú bấm — Safari đòi) → đăng ký → lưu server. */
export async function enablePush(username: string): Promise<void> {
  if (!isPushSupported()) throw new Error("Trình duyệt này không hỗ trợ thông báo.");
  const perm = await Notification.requestPermission();
  if (perm === "denied") {
    throw new Error("Bạn đã chặn thông báo — mở cài đặt trang của trình duyệt để cho phép lại.");
  }
  if (perm !== "granted") throw new Error("Chưa được cho phép hiện thông báo.");
  await subscribeAndSave();
  setOptOut(username, false);
}

/** Người dùng TẮT trên máy này: gỡ ở server rồi huỷ trong trình duyệt; nhớ lựa chọn để không tự bật lại. */
export async function disablePush(username: string): Promise<void> {
  setOptOut(username, true);
  const sub = await currentSubscription();
  if (!sub) return;
  await postPush("/api/push/unsubscribe", { endpoint: sub.endpoint }).catch(() => undefined);
  await sub.unsubscribe();
}

/** Mở web khi đã cho phép từ trước: đăng ký lại ngầm cho tài khoản đang đăng nhập (máy dùng chung,
 *  khoá máy chủ đổi, trình duyệt tự xoay endpoint…); tài khoản này đã tự tắt trên máy → gỡ cả đăng ký
 *  còn sót của người trước. Không bao giờ hỏi quyền, không báo lỗi. */
export async function syncPushSubscription(username: string): Promise<void> {
  try {
    if (!isPushSupported() || Notification.permission !== "granted") return;
    if (isOptedOut(username)) await detachPush();
    else await subscribeAndSave();
  } catch { /* im lặng — công tắc trong chuông vẫn cho bật tay */ }
}

/** Gỡ đăng ký của máy này (server + trình duyệt) để người sau không nhận tin của người trước (đăng
 *  xuất · tài khoản không có chuông · đã tự tắt). Tối đa DETACH_TIMEOUT_MS; endpoint đã huỷ ở trình
 *  duyệt thì lần gửi sau dịch vụ push báo 410, server tự xoá dòng — chỉ cần một bước kịp xong. */
export async function detachPush(): Promise<void> {
  const work = (async () => {
    const sub = await currentSubscription();
    if (!sub) return;
    await Promise.allSettled([
      postPush("/api/push/unsubscribe", { endpoint: sub.endpoint }),
      sub.unsubscribe(),
    ]);
  })().catch(() => undefined);
  await Promise.race([work, new Promise((resolve) => window.setTimeout(resolve, DETACH_TIMEOUT_MS))]);
}

/** Hết phiên (401): hết token nên chỉ huỷ phía trình duyệt (lần gửi sau dịch vụ push báo 410, server
 *  tự xoá dòng); đăng nhập lại thì chuông tự đăng ký lại. Không bao giờ ném lỗi. */
export async function unsubscribeBrowserOnly(): Promise<void> {
  try { await (await currentSubscription())?.unsubscribe(); } catch { /* cố gắng hết sức */ }
}

export type SwMessage = { type?: string; url?: string };

/** Nghe tin service worker gửi về tab (`vrg-push` có thông báo mới · `vrg-navigate` bấm thông báo).
 *  `reply` trả lời qua cổng MessageChannel đi kèm tin (service worker chờ để biết SPA đã nhận việc). */
export function onServiceWorkerMessage(handler: (msg: SwMessage, reply: (data: unknown) => void) => void) {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return () => undefined;
  const listener = (e: MessageEvent) => {
    const port = e.ports?.[0];
    handler((e.data ?? {}) as SwMessage, (data) => {
      try { port?.postMessage(data); } catch { /* service worker đã thôi chờ */ }
    });
  };
  navigator.serviceWorker.addEventListener("message", listener);
  navigator.serviceWorker.startMessages();
  return () => navigator.serviceWorker.removeEventListener("message", listener);
}
