/* Nội dung một tin trong luồng Hỗ trợ & Thông báo — chữ thuần, riêng ĐƯỜNG DẪN NỘI BỘ thành link.

   Tin cảnh báo tự động kèm đường dẫn tới trang Cảnh báo bất thường; chữ thuần thì đơn vị phải tự
   chép đường dẫn. An toàn: KHÔNG dựng HTML từ chữ người gõ (không dangerouslySetInnerHTML), chỉ
   biến thành link hai dạng:
   - đường dẫn bắt đầu bằng "/" + chữ/số (chặn "//máy-khác" — trình duyệt hiểu là trang ngoài);
   - địa chỉ đầy đủ CÙNG gốc với web đang mở → quy về đường dẫn nội bộ.
   Địa chỉ khác (trang ngoài, javascript:…) giữ nguyên là chữ. */

import { Fragment } from "react";
import { Link } from "react-router-dom";

const INTERNAL = /^\/[A-Za-z0-9]/;
const TRAILING = /[.,;:!?)\]]+$/;   // dấu câu dính cuối đường dẫn không thuộc về link

/** Token → đường dẫn nội bộ để mở trong app, hoặc null nếu không phải link nội bộ hợp lệ. */
function internalPath(token: string): string | null {
  if (INTERNAL.test(token)) return token;
  if (!/^https?:\/\//i.test(token)) return null;
  try {
    const u = new URL(token);
    const path = u.pathname + u.search + u.hash;
    return u.origin === window.location.origin && INTERNAL.test(path) ? path : null;
  } catch {
    return null;   // không phải URL hợp lệ → để nguyên chữ
  }
}

export default function SupportMessageBody({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\s+)/).map((part, i) => {
        const core = part.replace(TRAILING, "");
        const path = core ? internalPath(core) : null;
        if (!path) return <Fragment key={i}>{part}</Fragment>;
        return (
          <Fragment key={i}>
            {/* Hiện phần đường dẫn, bỏ tham số truy vấn cho gọn; bấm vẫn mở đúng khoảng ngày. */}
            {/* CSS chung đặt `a{color:inherit;text-decoration:none}` → phải tự tô, không thì link
                trông y như chữ thường và đơn vị không biết bấm được. */}
            <Link to={path} title={path}
              style={{ color: "var(--accent-2)", textDecoration: "underline", fontWeight: 600 }}>
              {path.split("?")[0]}
            </Link>
            {part.slice(core.length)}
          </Fragment>
        );
      })}
    </>
  );
}
