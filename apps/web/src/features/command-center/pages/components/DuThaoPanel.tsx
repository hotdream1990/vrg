/* Bước Dự thảo: hình "DỰ THẢO GIÁ SÀN ĐIỀU CHỈNH" (server dựng từ BẢN ĐÃ LƯU) · chép hình vào bộ nhớ tạm
   để dán Zalo/email · tải PNG · tỷ giá VCB in dưới bảng (chỉ sửa ở bước Dự thảo). */

import { CopyOutlined, DownloadOutlined, ReloadOutlined, SyncOutlined } from "@ant-design/icons";
import { Alert, App, Button, Input, Space, Spin } from "antd";
import { useEffect, useState } from "react";

import {
  type Sheet, copyImage, fetchDraftFile, fetchVcbRate, saveBlob,
} from "../../../../lib/floor-draft-flow-client";
import DateInput from "../../sections/DateInput";
import NumInput from "../../sections/NumInput";

type Props = {
  draftId: number;
  version: string;               // updated_at của bản đã lưu — đổi thì dựng lại hình
  sheet: Sheet | null;
  editable: boolean;             // đang ở bước Dự thảo + có quyền sửa
  dirty: boolean;
  ensureSaved: () => Promise<void>;
  onSheet: (s: Sheet) => void;
};

const LABEL: React.CSSProperties = { display: "block", fontSize: 12.5, color: "var(--muted)", marginBottom: 4 };
const errText = (e: unknown) => (e instanceof Error ? e.message : "Có lỗi xảy ra, vui lòng thử lại.");

export default function DuThaoPanel({ draftId, version, sheet, editable, dirty, ensureSaved, onSheet }: Props) {
  const { message } = App.useApp();
  const [src, setSrc] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [fetchingRate, setFetchingRate] = useState(false);
  const [tick, setTick] = useState(0);
  const s: Sheet = sheet ?? { vcb_rate: null, vcb_time: "8g30", vcb_date: null };

  useEffect(() => {
    let url = "";
    let cancelled = false;
    setLoading(true); setErr("");
    fetchDraftFile(draftId, "du-thao.png")
      .then(({ blob }) => { if (!cancelled) { url = URL.createObjectURL(blob); setSrc(url); } })
      .catch((e) => { if (!cancelled) setErr(errText(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; if (url) URL.revokeObjectURL(url); };
  }, [draftId, version, tick]);

  const blobAfterSave = () => ensureSaved().then(() => fetchDraftFile(draftId, "du-thao.png")).then((f) => f.blob);

  const copy = async () => {
    try {
      // ClipboardItem nhận Promise → tạo NGAY trong cú bấm (Safari đòi thao tác người dùng còn hiệu lực).
      if (await copyImage(blobAfterSave())) message.success("Đã chép hình dự thảo — dán (Ctrl+V) vào Zalo/email.");
      else message.warning("Trình duyệt này không cho chép ảnh — dùng nút Tải PNG.");
    } catch (e) {
      message.error(`Không chép được hình: ${errText(e)} — dùng nút Tải PNG.`);
    }
  };

  const download = async () => {
    try {
      await ensureSaved();
      const f = await fetchDraftFile(draftId, "du-thao.png");
      saveBlob(f.blob, f.name);
    } catch (e) {
      message.error(errText(e));
    }
  };

  const getRate = async () => {
    setFetchingRate(true);
    try {
      const r = await fetchVcbRate(s.vcb_date ?? undefined);
      if (r.rate == null) throw new Error("VCB chưa có giá mua chuyển khoản.");
      onSheet({ ...s, vcb_rate: r.rate });
      message.success(`Tỷ giá VCB mua CK ngày ${r.date}: ${r.rate.toLocaleString("vi-VN")} đ`);
    } catch (e) {
      message.error(errText(e));
    } finally {
      setFetchingRate(false);
    }
  };

  return (
    <div className="card">
      <div className="card-head" style={{ marginBottom: 8 }}><h3 style={{ margin: 0 }}>Hình dự thảo giá sàn điều chỉnh</h3></div>
      <Space wrap size={8} style={{ marginBottom: 10 }}>
        <Button type="primary" icon={<CopyOutlined />} onClick={copy} disabled={!!err}>Chép hình</Button>
        <Button icon={<DownloadOutlined />} onClick={download} disabled={!!err}>Tải PNG</Button>
        <Button icon={<ReloadOutlined />} onClick={() => setTick((t) => t + 1)}>Dựng lại</Button>
        {dirty && <span className="form-note" style={{ fontSize: 12.5 }}>Có thay đổi chưa lưu — chép/tải sẽ tự lưu trước.</span>}
      </Space>

      <div className="fd-sheet-fields">
        <label>
          <span style={LABEL}>Tỷ giá VCB mua CK (đ/USD)</span>
          <span className="fd-input-row">
            <NumInput value={s.vcb_rate} readOnly={!editable} className="fd-box-input"
              onChange={(v) => onSheet({ ...s, vcb_rate: v })} />
            {editable && (
              <Button icon={<SyncOutlined />} loading={fetchingRate} onClick={getRate}>Lấy từ VCB</Button>
            )}
          </span>
        </label>
        <label>
          <span style={LABEL}>Giờ lấy</span>
          <Input value={s.vcb_time} readOnly={!editable} maxLength={20} placeholder="vd 8g30"
            onChange={(e) => onSheet({ ...s, vcb_time: e.target.value })} />
        </label>
        <label>
          <span style={LABEL}>Ngày lấy</span>
          <DateInput value={s.vcb_date ?? ""} readOnly={!editable} noFuture
            onChange={(iso) => onSheet({ ...s, vcb_date: iso || null })} />
        </label>
      </div>

      {err && <Alert type="error" showIcon message={err} style={{ marginTop: 10 }} />}
      <div className="fd-sheet-frame">
        {loading ? <Spin /> : src && <img src={src} alt="Dự thảo giá sàn điều chỉnh" />}
      </div>
    </div>
  );
}
