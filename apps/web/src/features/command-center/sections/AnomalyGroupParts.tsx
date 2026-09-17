/* Các mảnh hiển thị của màn "Cảnh báo bất thường" (thẻ tổng quan · tiêu đề nhóm · bảng nhóm),
   dùng chung cho màn của quản trị và của lãnh đạo đơn vị. Bảng dựng ĐỘNG theo `columns` server
   trả về: thêm luật mới ở server là web hiện được ngay. */

import { CheckCircleOutlined } from "@ant-design/icons";
import { Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";

import type {
  AnomalyGroup, AnomalyRow, AnomalySeverity, AnomalySummary,
} from "../../../lib/anomaly-client";
import { dmy } from "../../../lib/date";
import { formatViNumber } from "../../../lib/number-format";
import UnitLoginButton from "../pages/components/UnitLoginButton";

const ROWS_PER_PAGE = 10;          // bảng trong nhóm cắt trang ở client cho gọn
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/** Mức nghiêm trọng → nhãn tiếng Việt + màu. Dùng màu nhấn có chừng mực (viền trái + chữ số),
 *  KHÔNG tô đỏ cả mảng lớn: trang đỏ rực thì người xem hết phân biệt được việc nào gấp. */
export const SEVERITY: Record<AnomalySeverity, { label: string; tag: string; accent: string }> = {
  high: { label: "Nghiêm trọng", tag: "volcano", accent: "#c0392b" },
  medium: { label: "Cần xem", tag: "gold", accent: "#a96a00" },
  low: { label: "Ghi nhận", tag: "blue", accent: "#0369a1" },
};

/** Giá trị một ô → chữ hiển thị: số kiểu vi-VN, ngày ISO đổi sang DD/MM/YYYY, rỗng → "—". */
function cellText(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "number") return formatViNumber(v);
  if (typeof v === "boolean") return v ? "Có" : "Không";
  const s = String(v);
  return ISO_DATE_RE.test(s) ? dmy(s) : s;
}

/** Hàng thẻ tổng quan: tổng cảnh báo · số theo từng mức · số đơn vị bị nêu tên. */
export function SummaryCards({ s }: { s: AnomalySummary }) {
  const cards: { label: string; value: number; accent?: string }[] = [
    { label: "Tổng số cảnh báo", value: s.total },
    ...(["high", "medium", "low"] as AnomalySeverity[]).map((k) => ({
      label: SEVERITY[k].label, value: s[k], accent: SEVERITY[k].accent,
    })),
    { label: "Đơn vị bị nêu tên", value: s.units },
  ];
  return (
    <div className="kpi-row ct-kpi" style={{ marginBottom: 14 }}>
      {cards.map((c) => (
        <div className="kpi" key={c.label}
          style={c.accent ? { borderLeft: `3px solid ${c.accent}` } : undefined}>
          <div className="label">{c.label}</div>
          <div className="value" style={c.accent ? { color: c.accent } : undefined}>{formatViNumber(c.value)}</div>
        </div>
      ))}
    </div>
  );
}

/** Tiêu đề một nhóm cảnh báo: tên · thẻ mức · số dòng · số đơn vị · mô tả luật. */
export function GroupHeader({ g }: { g: AnomalyGroup }) {
  const sev = SEVERITY[g.severity] ?? SEVERITY.low;
  // Nhóm KHÔNG có cảnh báo: gạch ngang + làm mờ tiêu đề để mắt lướt qua ngay, khỏi phải đọc
  // "0 dòng" mới biết là sạch (cùng ý với việc đẩy các nhóm này xuống cuối trang).
  const clean = g.count === 0;
  return (
    <div style={clean ? { opacity: 0.55 } : undefined}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <b style={clean ? { textDecoration: "line-through" } : undefined}>{g.label}</b>
        <Tag color={sev.tag}>{sev.label}</Tag>
        <span style={{ color: "var(--muted)", fontSize: 12.5 }}>
          {formatViNumber(g.count)} dòng · {formatViNumber(g.units)} đơn vị
        </span>
      </div>
      {g.desc && <div style={{ color: "var(--muted)", fontSize: 12.5, marginTop: 2 }}>{g.desc}</div>}
    </div>
  );
}

/** Bảng của một nhóm — cột dựng ĐỘNG từ `group.columns` (server là nơi định nghĩa luật & cột). */
export function GroupTable({ group, showLogin }: { group: AnomalyGroup; showLogin: boolean }) {
  if (group.rows.length === 0) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#0b7a3b", fontSize: 13 }}>
        <CheckCircleOutlined /> Không có cảnh báo.
      </div>
    );
  }
  const columns: ColumnsType<AnomalyRow> = group.columns.map((c) => ({
    title: c.label,
    dataIndex: c.key,
    key: c.key,
    render: (v: unknown) => cellText(v),
  }));
  // Thấy lỗi là vào thẳng tài khoản đơn vị đó kiểm chứng, khỏi sang màn Tài khoản dò theo email.
  // Chỉ màn quản trị mới có cột này: nút tự ẩn với người không phải admin, nhưng TIÊU ĐỀ cột thì
  // không — để nguyên thì lãnh đạo đơn vị thấy một cột "Đăng nhập hộ" trống trơn.
  if (showLogin && group.rows.some((r) => r.don_vi)) {
    columns.push({
      title: "Đăng nhập hộ", key: "_login", width: 170,
      render: (_: unknown, r: AnomalyRow) =>
        r.don_vi ? <UnitLoginButton unit={String(r.don_vi)} /> : null,
    });
  }
  return (
    <Table<AnomalyRow>
      size="small" columns={columns} dataSource={group.rows}
      rowKey={(_, i) => `${group.key}-${i ?? 0}`}
      scroll={{ x: "max-content" }}   /* màn hẹp: cuộn ngang trong bảng, không vỡ trang */
      pagination={{
        pageSize: ROWS_PER_PAGE, showSizeChanger: false,
        showTotal: (t, [from, to]) => `${from}–${to} / ${t} dòng`,
      }}
    />
  );
}

