/* Ngăn "Cấu hình ngưỡng" của màn Cảnh báo bất thường — CHỈ quản trị (server cũng chặn). */

import { Alert, App, Button, Drawer, InputNumber, Space, Spin, Typography } from "antd";
import { useEffect, useState } from "react";

import {
  type AnomalyConfigItem, fetchAnomalyConfig, saveAnomalyConfig,
} from "../../../lib/anomaly-client";
import { formatViNumber } from "../../../lib/number-format";

const errText = (e: unknown): string =>
  (e instanceof Error ? e.message : "Không tải được dữ liệu, vui lòng thử lại.");

/** Ngăn cấu hình ngưỡng: mỗi ngưỡng một ô số + dòng giải thích; Lưu xong trang tự quét lại. */
export default function ThresholdDrawer({ open, onClose, onSaved }:
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
