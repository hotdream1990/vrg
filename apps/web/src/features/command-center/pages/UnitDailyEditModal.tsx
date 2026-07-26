/* Modal nhập/sửa số liệu 1 đơn vị / 1 ngày — DÙNG CHUNG cho timeline (danh sách theo ngày) và
   trang tổng hợp. Chọn ngày + đơn vị → nạp số đã có (nếu có) → sửa → lưu (upsert). Role-aware. */

import { Alert, Modal, Select, Spin, Tag, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import { deleteRecord, upsertRecord } from "../../../lib/api-client";
import { type MemberPriceType, clearMyPrice, upsertMyPrice } from "../../../lib/member-client";
import {
  type DayData, fetchMyDay, fetchDay, saveMyDaily, saveDaily,
} from "../../../lib/unit-daily-client";
import { KIND_LABEL, type Kind, type Values } from "../../../lib/unit-daily-fields";
import DateInput from "../sections/DateInput";
import type { ConsumptionTab } from "./ConsumptionForm";
import UnitDailyForm, { type PriceDraft } from "./UnitDailyForm";

const daysBetween = (later: string, earlier: string) =>
  Math.round((new Date(later + "T00:00:00").getTime() - new Date(earlier + "T00:00:00").getTime()) / 86_400_000);

type Props = {
  open: boolean;
  kind: Kind;
  defaultTab?: ConsumptionTab;    // Tiêu thụ–Tồn kho: tab mở sẵn theo mục menu
  role: "member" | "hq";
  isAdmin: boolean;
  canEdit: boolean; // false = chỉ được cấp mức Xem → mở ở chế độ chỉ đọc
  initialDay: string;
  initialCompany: string;
  today: string;
  onClose: () => void;
  onSaved: () => void;
};

export default function UnitDailyEditModal(
  { open, kind, defaultTab, role, isAdmin, canEdit, initialDay, initialCompany, today, onClose, onSaved }: Props,
) {
  const [day, setDay] = useState(initialDay);
  const [company, setCompany] = useState(initialCompany);
  const [data, setData] = useState<DayData | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (open) { setDay(initialDay); setCompany(initialCompany); } }, [open, initialDay, initialCompany]);

  const load = useCallback((asOf: string) => {
    setLoading(true);
    (role === "member" ? fetchMyDay : fetchDay)(kind, asOf)
      .then((d) => { setData(d); setCompany((c) => (c && d.units.includes(c) ? c : d.units[0] ?? "")); })
      .catch((e) => message.error(e.message)).finally(() => setLoading(false));
  }, [role, kind]);
  useEffect(() => { if (open && day) load(day); }, [open, day, load]);

  const units = data?.units ?? [];

  const entry = data?.entries[company] ?? null;
  const exists = !!entry;
  const editable = useMemo(() => {
    if (!canEdit || !day || day > today) return false;
    if (isAdmin) return true;
    return daysBetween(today, day) <= (data?.edit_window_days ?? 7);
  }, [canEdit, isAdmin, day, today, data]);

  // Đơn giá mủ nước/mủ chén → ghi thẳng kho "Giá mủ nguyên liệu" (đúng đơn vị + ngày), chỉ khi đổi.
  const savePrices = async (prices: PriceDraft) => {
    const orig = data?.prices?.[company];
    const jobs: Promise<unknown>[] = [];
    // Mủ chén có thể tính theo độ TSC hoặc độ DRC — nhãn đơn vị lưu kèm giá phải khớp lựa chọn.
    const cupBasis = prices.cupBasis ?? "tsc";
    const each = (nv: number | null, ov: number | null, pt: MemberPriceType) => {
      if ((nv ?? null) === (ov ?? null)) return;
      const unit = pt === "purchase_cup" && cupBasis === "drc" ? "đồng/độ DRC" : "đồng/độ TSC";
      if (role === "member") {
        jobs.push(nv == null
          ? clearMyPrice(company, day, pt)
          : upsertMyPrice(company, day, pt, nv, pt === "purchase_cup" ? cupBasis : undefined));
      } else {
        jobs.push(nv == null
          ? deleteRecord({ as_of: day, source: "vrg", grade: company, contract: "", price_type: pt })
          : upsertRecord({ as_of: day, source: "vrg", grade: company, contract: "",
                           price_type: pt, price: nv, currency: "VND", unit }));
      }
    };
    each(prices.latex, orig?.latex ?? null, "purchase");
    each(prices.cup, orig?.cup ?? null, "purchase_cup");
    await Promise.all(jobs);
  };

  const save = async (fields: Values, prices: PriceDraft) => {
    setSaving(true);
    try {
      await (role === "member" ? saveMyDaily : saveDaily)(kind, company, day, fields);
      if (kind === "purchase") await savePrices(prices);
      message.success("Đã lưu số liệu ngày");
      onSaved();
      onClose();
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  // Bề rộng bám theo màn hình để có nhiều chỗ nhập nhất có thể (96% bề ngang, chặn trần cho màn siêu rộng);
  // biểu Tiêu thụ–Tồn kho nhiều cột hơn (loại tiền · tỷ giá · ngày HĐ · file) nên rộng hơn biểu Thu mua.
  const width = kind === "consumption" ? "min(1680px, 96vw)" : "min(1240px, 92vw)";
  return (
    <Modal open={open} onCancel={onClose} footer={null}
           width={width} destroyOnHidden
           title={`Nhập số liệu — ${KIND_LABEL[kind]}`}>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
        <DateInput value={day} onChange={setDay} noFuture style={{ width: 190 }} />
        <Select value={company} onChange={setCompany} showSearch style={{ minWidth: 220 }}
                options={units.map((u) => ({ value: u, label: u }))}
                filterOption={(i, o) => (o?.label ?? "").toLowerCase().includes(i.toLowerCase())} />
        {exists
          ? <Tag color="blue">Đang sửa số đã có</Tag>
          : <Tag color="green">Tạo mới cho ngày này</Tag>}
      </div>
      {!editable && (
        <Alert type="info" showIcon style={{ marginBottom: 12 }}
               message="Ngày này ở chế độ chỉ xem — ngoài cửa sổ nhập cho phép." />
      )}
      <Spin spinning={loading}>
        {data && (
          <UnitDailyForm
            kind={kind}
            formKey={`${kind}|${day}|${company}|${entry?.updated_at ?? "new"}`}
            values={entry?.fields ?? {}}
            plan={data.plans[company] ?? null}
            currency={data.currencies?.[company] ?? "VND"}
            role={role}
            company={company}
            day={day}
            defaultTab={defaultTab}
            linkedPrice={data.prices?.[company] ?? null}
            readOnly={!editable}
            footer={(dirty, current, prices) => (
              <div style={{ marginTop: 14, textAlign: "right" }}>
                <button className="btn btn-primary" disabled={!dirty || saving}
                        onClick={() => save(current, prices)}>
                  {saving ? "Đang lưu…" : "Lưu số liệu"}
                </button>
              </div>
            )}
          />
        )}
      </Spin>
    </Modal>
  );
}
