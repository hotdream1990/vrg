/* Cảnh báo bất thường — hai người dùng, một màn:
   - QUẢN TRỊ: toàn bộ đơn vị thành viên + cấu hình ngưỡng + nút đăng nhập hộ để kiểm chứng.
   - LÃNH ĐẠO ĐƠN VỊ: chỉ đơn vị mình (server tự lọc), để nhắc nhân viên nhập liệu đúng việc
     cần sửa. Không có cấu hình ngưỡng, không có nút đăng nhập hộ.
   Mở một trang là nắm mọi dấu hiệu sai: nhập sai đơn vị tính, chưa nộp, thiếu đơn giá… — thay cho
   việc chạy script dò tay từng đợt. Bảng dựng ĐỘNG theo `columns` server trả về. */

import {
  CameraOutlined, CloseOutlined, FileExcelOutlined, ReloadOutlined, SlidersOutlined, WarningOutlined,
} from "@ant-design/icons";
import { Alert, Button, Collapse, DatePicker, Spin } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useCallback, useEffect, useState } from "react";

import {
  type AnomalyReport, defaultAnomalyRange, downloadAnomalyXlsx, fetchAnomalies,
} from "../../../lib/anomaly-client";
import { dmy } from "../../../lib/date";
import { useAuth } from "../../auth/AuthContext";
import { GroupHeader, GroupTable, SummaryCards } from "../sections/AnomalyGroupParts";
import ThresholdDrawer from "../sections/AnomalyThresholdDrawer";

const { RangePicker } = DatePicker;

const DATE_DISPLAY = "DD/MM/YYYY";
const ISO_DATE = "YYYY-MM-DD";

const errText = (e: unknown): string =>
  (e instanceof Error ? e.message : "Không tải được dữ liệu, vui lòng thử lại.");

export default function AnomalyPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const isLeader = user?.role === "leader";
  const scope = isLeader ? "mine" : "all";

  const initial = defaultAnomalyRange();
  const [range, setRange] = useState<[Dayjs, Dayjs]>([dayjs(initial.from), dayjs(initial.to)]);
  const [report, setReport] = useState<AnomalyReport | null>(null);
  const [activeKeys, setActiveKeys] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [cfgOpen, setCfgOpen] = useState(false);
  const [shot, setShot] = useState(false);   // chế độ chụp: ẩn khung ứng dụng, chỉ còn bảng
  const [err, setErr] = useState("");

  // Ẩn/hiện khung bằng một lớp trên <body> (CSS `.shot-mode` ở command-center.css) thay vì truyền
  // cờ xuyên qua AdminLayout — màn khác muốn dùng lại chỉ cần bật đúng lớp này.
  useEffect(() => {
    document.body.classList.toggle("shot-mode", shot);
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setShot(false); };
    window.addEventListener("keydown", esc);
    return () => {
      document.body.classList.remove("shot-mode");   // rời trang giữa chừng không được kẹt chế độ
      window.removeEventListener("keydown", esc);
    };
  }, [shot]);

  const scan = useCallback(async () => {
    setLoading(true); setErr("");
    try {
      const r = await fetchAnomalies(range[0].format(ISO_DATE), range[1].format(ISO_DATE), scope);
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
  }, [range, scope]);

  // Quét MỘT LẦN lúc mở trang. Deps để rỗng là CỐ Ý (không phụ thuộc `scan`): đổi ngày sẽ không
  // tự quét lại — mỗi lần quét mất vài giây, nên để người dùng chủ động bấm "Quét lại".
  useEffect(() => { void scan(); }, []);

  const exportXlsx = async () => {
    setExporting(true); setErr("");
    try {
      await downloadAnomalyXlsx(range[0].format(ISO_DATE), range[1].format(ISO_DATE), scope);
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
          {isLeader ? (
            <p>Những chỗ <b>nhân viên nhập liệu của đơn vị</b> đang nhập sai hoặc còn thiếu — để
              nhắc đúng việc cần sửa: <b>nhập sai đơn vị tính · chưa nộp báo cáo · thiếu đơn giá ·
              kế hoạch năm khai thiếu</b>…</p>
          ) : (
            <p>Quét toàn bộ số liệu đơn vị thành viên trong khoảng đã chọn và gom mọi dấu hiệu sai:
              <b> nhập sai đơn vị tính · chưa nộp báo cáo · thiếu đơn giá · doanh thu vô lý</b>…</p>
          )}
          {report && (
            <p style={{ marginTop: 4 }}>
              Khoảng đang xem: <b>{dmy(report.date_from)}</b> → <b>{dmy(report.date_to)}</b>.{" "}
              {isLeader ? (
                <>Cảnh báo là <b>dấu hiệu cần kiểm tra</b> — nhắc nhân viên nhập liệu xem lại. Ngày
                  đã khoá thì nhân viên gửi <b>Đề nghị sửa số liệu</b> để Ban duyệt.</>
              ) : (
                <>Cảnh báo là <b>dấu hiệu cần kiểm tra</b>, chưa chắc đã là số sai — đối chiếu với
                  đơn vị trước khi sửa.</>
              )}
            </p>
          )}
        </div>
      </div>
      {err && <Alert type="error" showIcon message={err} style={{ marginBottom: 12 }} />}

      <div className="card shot-hide" style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", marginBottom: 14 }}>
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
        <Button icon={<CameraOutlined />} disabled={loading || !report}
          onClick={() => setShot(true)}>Chế độ chụp</Button>
        {isAdmin && (
          <Button icon={<SlidersOutlined />} style={{ marginLeft: "auto" }} disabled={loading}
            onClick={() => setCfgOpen(true)}>Cấu hình ngưỡng</Button>
        )}
      </div>

      {/* Lối ra của chế độ chụp: nút nổi góc dưới phải (ngoài vùng hay chụp) + phím Esc. */}
      {shot && (
        <Button size="small" icon={<CloseOutlined />} onClick={() => setShot(false)}
          style={{ position: "fixed", right: 16, bottom: 16, zIndex: 1000 }}>
          Thoát chế độ chụp (Esc)
        </Button>
      )}

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
            /* Máy chủ trả cả nhóm rỗng (màn lãnh đạo đơn vị chỉ bớt nhóm tính trên số gộp Tập
               đoàn) nên phải xét tổng số dòng, không xét số nhóm — nếu không, ngày sạch sẽ hiện
               một loạt bảng "Không có cảnh báo" thay vì một câu xác nhận. */
            <Alert type="success" showIcon
                   message="Không phát hiện bất thường nào trong khoảng đã chọn."
                   description={isLeader
                     ? "Số liệu của đơn vị trong kỳ này đạt mọi luật kiểm tra."
                     : "Số liệu đơn vị thành viên trong kỳ này đạt mọi luật kiểm tra."} />
          ) : (
            <Collapse
              activeKey={activeKeys}
              onChange={(k) => setActiveKeys(Array.isArray(k) ? k : [k])}
              items={groups.map((g) => ({
                key: g.key, label: <GroupHeader g={g} />,
                children: <GroupTable group={g} showLogin={isAdmin} />,
              }))}
            />
          )}
        </>
      )}

      {isAdmin && (
        <ThresholdDrawer open={cfgOpen} onClose={() => setCfgOpen(false)}
          onSaved={() => { setCfgOpen(false); void scan(); }} />
      )}
    </div>
  );
}
