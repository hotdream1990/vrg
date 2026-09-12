/* Quản trị → Cảnh báo bất thường (CHỈ ADMIN).
   Mở một trang là nắm mọi dấu hiệu sai trong số liệu đơn vị thành viên: nhập sai đơn vị tính,
   chưa nộp, thiếu đơn giá, doanh thu vô lý… — thay cho việc chạy script dò tay từng đợt.

   Bảng của mỗi nhóm dựng ĐỘNG theo `columns` server trả về: backend thêm luật cảnh báo mới thì
   web hiện được ngay, không phải sửa file này. */

import {
  CheckCircleOutlined, FileExcelOutlined, ReloadOutlined, SlidersOutlined, WarningOutlined,
} from "@ant-design/icons";
import {
  Alert, App, Button, Collapse, DatePicker, Drawer, InputNumber, Space, Spin, Table, Tag, Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs, { type Dayjs } from "dayjs";
import { useCallback, useEffect, useState } from "react";

import {
  type AnomalyConfigItem, type AnomalyGroup, type AnomalyReport, type AnomalyRow,
  type AnomalySeverity, type AnomalySummary,
  defaultAnomalyRange, downloadAnomalyXlsx, fetchAnomalies, fetchAnomalyConfig, saveAnomalyConfig,
} from "../../../lib/anomaly-client";
import { dmy } from "../../../lib/date";
import { formatViNumber } from "../../../lib/number-format";

const { RangePicker } = DatePicker;

const DATE_DISPLAY = "DD/MM/YYYY";
const ISO_DATE = "YYYY-MM-DD";
const ROWS_PER_PAGE = 10;          // bảng trong nhóm cắt trang ở client cho gọn
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/** Mức nghiêm trọng → nhãn tiếng Việt + màu. Dùng màu nhấn có chừng mực (viền trái + chữ số),
 *  KHÔNG tô đỏ cả mảng lớn: trang đỏ rực thì người xem hết phân biệt được việc nào gấp. */
const SEVERITY: Record<AnomalySeverity, { label: string; tag: string; accent: string }> = {
  high: { label: "Nghiêm trọng", tag: "volcano", accent: "#c0392b" },
  medium: { label: "Cần xem", tag: "gold", accent: "#a96a00" },
  low: { label: "Ghi nhận", tag: "blue", accent: "#0369a1" },
};

const errText = (e: unknown): string =>
  (e instanceof Error ? e.message : "Không tải được dữ liệu, vui lòng thử lại.");

/** Giá trị một ô → chữ hiển thị: số kiểu vi-VN, ngày ISO đổi sang DD/MM/YYYY, rỗng → "—". */
function cellText(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "number") return formatViNumber(v);
  if (typeof v === "boolean") return v ? "Có" : "Không";
  const s = String(v);
  return ISO_DATE_RE.test(s) ? dmy(s) : s;
}

/** Hàng thẻ tổng quan: tổng cảnh báo · số theo từng mức · số đơn vị bị nêu tên. */
function SummaryCards({ s }: { s: AnomalySummary }) {
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
function GroupHeader({ g }: { g: AnomalyGroup }) {
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
function GroupTable({ group }: { group: AnomalyGroup }) {
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

/** Ngăn cấu hình ngưỡng: mỗi ngưỡng một ô số + dòng giải thích; Lưu xong trang tự quét lại. */
function ThresholdDrawer({ open, onClose, onSaved }:
{ open: boolean; onClose: () => void; onSaved: () => void }) {
  const { message } = App.useApp();
  const [items, setItems] = useState<AnomalyConfigItem[]>([]);
  const [draft, setDraft] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  // Nạp lại mỗi lần mở: ngưỡng có thể đã bị admin khác đổi từ lúc trang này được mở.
  useEffect(() => {
    if (!open) return;
    setLoading(true); setErr("");
    fetchAnomalyConfig()
      .then((list) => {
        setItems(list);
        setDraft(Object.fromEntries(list.map((i) => [i.key, i.value])));
      })
      .catch((e) => setErr(errText(e)))
      .finally(() => setLoading(false));
  }, [open]);

  /** Điền lại giá trị mặc định vào ô — CHƯA lưu, admin còn xem rồi mới bấm Lưu. */
  const restore = () => setDraft(Object.fromEntries(items.map((i) => [i.key, i.default])));

  const save = async () => {
    setSaving(true); setErr("");
    try {
      await saveAnomalyConfig(draft);
      message.success("Đã lưu ngưỡng — đang quét lại theo ngưỡng mới.");
      onSaved();
    } catch (e) {
      setErr(errText(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Drawer
      title="Cấu hình ngưỡng" open={open} onClose={onClose} width={520}
      extra={
        <Space>
          <Button onClick={restore} disabled={loading || saving || !items.length}>Khôi phục mặc định</Button>
          <Button type="primary" loading={saving} disabled={loading || !items.length}
            onClick={() => void save()}>Lưu</Button>
        </Space>
      }
    >
      {err && <Alert type="error" showIcon message={err} style={{ marginBottom: 12 }} />}
      {loading ? (
        <div style={{ textAlign: "center", padding: 24 }}><Spin /></div>
      ) : (
        <Space direction="vertical" size="large" style={{ width: "100%" }}>
          {items.map((it) => (
            <div key={it.key}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>{it.label}</div>
              <InputNumber style={{ width: "100%" }} value={draft[it.key] ?? null}
                onChange={(v) => setDraft((d) => ({ ...d, [it.key]: Number(v ?? 0) }))} />
              {it.hint && <div className="form-note" style={{ fontSize: 12, marginTop: 4 }}>{it.hint}</div>}
              <div style={{ color: "var(--muted)", fontSize: 11.5, marginTop: 2 }}>Mặc định: {formatViNumber(it.default)}</div>
            </div>
          ))}
          {!items.length && (
            <Typography.Text type="secondary">Chưa có ngưỡng nào để cấu hình.</Typography.Text>
          )}
        </Space>
      )}
    </Drawer>
  );
}

export default function AnomalyPage() {
  const initial = defaultAnomalyRange();
  const [range, setRange] = useState<[Dayjs, Dayjs]>([dayjs(initial.from), dayjs(initial.to)]);
  const [report, setReport] = useState<AnomalyReport | null>(null);
  const [activeKeys, setActiveKeys] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [cfgOpen, setCfgOpen] = useState(false);
  const [err, setErr] = useState("");

  const scan = useCallback(async () => {
    setLoading(true); setErr("");
    try {
      const r = await fetchAnomalies(range[0].format(ISO_DATE), range[1].format(ISO_DATE));
      setReport(r);
      // Bung sẵn TẤT CẢ nhóm có cảnh báo (máy chủ đã xếp chúng lên đầu), để lên trang là đọc
      // được ngay mọi việc cần làm mà không phải bấm từng nhóm. Nhóm rỗng vẫn gấp.
      setActiveKeys(r.groups.filter((g) => g.count > 0).map((g) => g.key));
    } catch (e) {
      setErr(errText(e));
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, [range]);

  // Quét MỘT LẦN lúc mở trang. Deps để rỗng là CỐ Ý (không phụ thuộc `scan`): đổi ngày sẽ không
  // tự quét lại — mỗi lần quét mất vài giây, nên để người dùng chủ động bấm "Quét lại".
  useEffect(() => { void scan(); }, []);

  const exportXlsx = async () => {
    setExporting(true); setErr("");
    try {
      await downloadAnomalyXlsx(range[0].format(ISO_DATE), range[1].format(ISO_DATE));
    } catch (e) {
      setErr(errText(e));
    } finally {
      setExporting(false);
    }
  };

  const groups = report?.groups ?? [];

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><WarningOutlined style={{ marginRight: 8 }} />Cảnh báo bất thường</h2>
          <p>Quét toàn bộ số liệu đơn vị thành viên trong khoảng đã chọn và gom mọi dấu hiệu sai:
            <b> nhập sai đơn vị tính · chưa nộp báo cáo · thiếu đơn giá · doanh thu vô lý</b>…</p>
          {report && (
            <p style={{ marginTop: 4 }}>
              Khoảng đang xem: <b>{dmy(report.date_from)}</b> → <b>{dmy(report.date_to)}</b>.
              Cảnh báo là <b>dấu hiệu cần kiểm tra</b>, chưa chắc đã là số sai — đối chiếu với đơn vị trước khi sửa.
            </p>
          )}
        </div>
      </div>
      {err && <Alert type="error" showIcon message={err} style={{ marginBottom: 12 }} />}

      <div className="card" style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", marginBottom: 14 }}>
        <RangePicker
          format={DATE_DISPLAY} allowClear={false} value={range} disabled={loading}
          placeholder={["Từ ngày", "Đến ngày"]}
          onChange={(v) => { if (v?.[0] && v[1]) setRange([v[0], v[1]]); }}
        />
        <Button type="primary" icon={<ReloadOutlined />} loading={loading}
          onClick={() => void scan()}>Quét lại</Button>
        <Button icon={<FileExcelOutlined />} loading={exporting}
          disabled={loading || !report || report.summary.total === 0}
          onClick={() => void exportXlsx()}>Xuất Excel</Button>
        <Button icon={<SlidersOutlined />} style={{ marginLeft: "auto" }} disabled={loading}
          onClick={() => setCfgOpen(true)}>Cấu hình ngưỡng</Button>
      </div>

      {loading && (
        <div className="card" style={{ textAlign: "center", padding: 40 }}>
          <Spin size="large" />
          <div style={{ marginTop: 12, color: "var(--muted)" }}>
            Đang quét số liệu từ {dmy(range[0].format(ISO_DATE))} đến {dmy(range[1].format(ISO_DATE))} —
            việc này mất vài giây, vui lòng đợi…
          </div>
        </div>
      )}

      {!loading && report && (
        <>
          <SummaryCards s={report.summary} />
          {report.summary.total === 0 ? (
            /* Máy chủ LUÔN trả đủ 8 nhóm (kể cả nhóm rỗng) nên phải xét tổng số dòng, không xét
               số nhóm — nếu không, ngày hệ thống sạch admin sẽ thấy 8 bảng "Không có cảnh báo"
               thay vì một câu xác nhận. */
            <Alert type="success" showIcon
                   message="Không phát hiện bất thường nào trong khoảng đã chọn."
                   description="Số liệu đơn vị thành viên trong kỳ này đạt mọi luật kiểm tra." />
          ) : (
            <Collapse
              activeKey={activeKeys}
              onChange={(k) => setActiveKeys(Array.isArray(k) ? k : [k])}
              items={groups.map((g) => ({
                key: g.key, label: <GroupHeader g={g} />, children: <GroupTable group={g} />,
              }))}
            />
          )}
        </>
      )}

      <ThresholdDrawer open={cfgOpen} onClose={() => setCfgOpen(false)}
        onSaved={() => { setCfgOpen(false); void scan(); }} />
    </div>
  );
}
