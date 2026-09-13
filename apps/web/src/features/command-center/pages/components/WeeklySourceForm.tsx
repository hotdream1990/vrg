/* Form thêm/sửa 1 nguồn tham khảo của Báo cáo tuần (nằm trong hộp thoại Quản lý nguồn). */

import { Checkbox, Select, Switch } from "antd";
import { useState } from "react";

import {
  SECTION_KEYS,
  type WeeklySourceInput,
  type WeeklySourceMeta,
} from "../../../../lib/weekly-sources-client";

type Props = {
  initial: WeeklySourceInput;
  meta: WeeklySourceMeta;
  busy: boolean;
  onSubmit: (v: WeeklySourceInput) => void;
  onCancel: () => void;
};

export const EMPTY_SOURCE: WeeklySourceInput = {
  category: "news", name: "", role: "", url: "", sections: [], guide: "",
  mode: "manual", feed_symbol: null, enabled: true, sort_order: null,
};

export default function WeeklySourceForm({ initial, meta, busy, onSubmit, onCancel }: Props) {
  const [v, setV] = useState<WeeklySourceInput>(initial);
  const set = (patch: Partial<WeeklySourceInput>) => setV((s) => ({ ...s, ...patch }));
  const sectionOpts = (meta.sections.length ? meta.sections : SECTION_KEYS.map((k) => ({ key: k, label: k })))
    .map((o) => ({ value: o.key, label: o.label === o.key ? o.key : `${o.key} · ${o.label}` }));
  const isFeed = v.mode === "market_feed";

  const submit = () => onSubmit({
    ...v,
    name: v.name.trim(),
    role: v.role.trim(),
    url: v.url.trim(),
    guide: v.guide.trim(),
    feed_symbol: isFeed ? (v.feed_symbol?.trim() || null) : null,
    sort_order: v.sort_order !== null && Number.isFinite(v.sort_order) ? v.sort_order : null,
  });

  return (
    <div className="wk-src-form">
      <div className="wk-form-grid">
        {/* div thay vì label: label bọc Select của AntD làm click bị phát 2 lần → danh sách mở rồi đóng ngay */}
        <div className="form-field">Loại nguồn
          <Select value={v.category} onChange={(category) => set({ category })}
            options={meta.categories.map((o) => ({ value: o.key, label: o.label }))} />
        </div>
        <div className="form-field">Cách lấy số liệu
          <Select value={v.mode} onChange={(mode) => set({ mode })}
            options={meta.modes.map((o) => ({ value: o.key, label: o.label }))} />
        </div>
        <label className="form-field">Tên nguồn *
          <input className="blt-input" value={v.name} onChange={(e) => set({ name: e.target.value })} />
        </label>
        <label className="form-field">Đường dẫn (URL)
          <input className="blt-input" value={v.url} placeholder="https://…"
            onChange={(e) => set({ url: e.target.value })} />
        </label>
        {isFeed && (
          <label className="form-field">Mã lấy tự động (feed_symbol)
            <input className="blt-input" value={v.feed_symbol ?? ""} placeholder="vd DX-Y.NYB, CL=F, BZ=F"
              onChange={(e) => set({ feed_symbol: e.target.value })} />
          </label>
        )}
        <label className="form-field">Thứ tự hiển thị
          <input className="blt-input" type="number" value={v.sort_order ?? ""} placeholder="Trống = xếp cuối"
            onChange={(e) => set({ sort_order: e.target.value === "" ? null : Number(e.target.value) })} />
        </label>
      </div>
      <label className="form-field">Vai trò trong phân tích
        <input className="blt-input" value={v.role} onChange={(e) => set({ role: e.target.value })} />
      </label>
      <div className="form-field">Dùng cho mục
        <Checkbox.Group value={v.sections} options={sectionOpts}
          onChange={(vals) => set({ sections: vals as string[] })} />
      </div>
      <label className="form-field">Hướng dẫn lấy số liệu
        <textarea className="blt-textarea" rows={4} value={v.guide}
          onChange={(e) => set({ guide: e.target.value })} />
      </label>
      {isFeed && <div className="form-note">Mã lấy tự động: mã kiểu Yahoo Finance (DX-Y.NYB, CL=F, BZ=F — tự đổi sang CNBC) hoặc mã CNBC (@LCO.1) — sai mã thì dòng chỉ số báo lỗi.</div>}
      <div className="blt-date-label">
        <Switch checked={v.enabled} onChange={(enabled) => set({ enabled })} /> Đang bật
      </div>
      <div className="wk-form-actions">
        <button className="btn" onClick={onCancel} disabled={busy}>Huỷ</button>
        <button className="btn btn-primary" onClick={submit} disabled={busy || !v.name.trim()}>
          {busy ? <span className="spinner" /> : null} Lưu nguồn
        </button>
      </div>
    </div>
  );
}
