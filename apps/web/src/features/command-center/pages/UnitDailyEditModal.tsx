/* Modal nhập/sửa số liệu 1 đơn vị / 1 ngày — DÙNG CHUNG cho timeline (danh sách theo ngày) và
   trang tổng hợp. Chọn ngày + đơn vị → nạp số đã có (nếu có) → sửa → lưu (upsert). Role-aware. */

import { Alert, Modal, Select, Spin, Tag, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import { deleteRecord, upsertRecord } from "../../../lib/api-client";
import { dmy } from "../../../lib/date";
import { type MemberPriceType, clearMyPrice, upsertMyPrice } from "../../../lib/member-client";
import { CUP_PRICE_UNIT, LACE_PRICE_UNIT, LATEX_PRICE_UNIT } from "../../../lib/purchase-price-unit";
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
  // Đơn vị đã SÁP NHẬP vào đơn vị của tài khoản: mở phiếu ra xem lại số cũ được, sửa thì không
  // (server chặn) — khoá ngay ở đây để form mở thẳng ở chế độ chỉ xem.
  const mergedUnit = (data?.view_only_units ?? []).includes(company);

  const entry = data?.entries[company] ?? null;
  const exists = !!entry;
  // Ngày đã CHỐT SỐ LIỆU của đơn vị đó → chỉ xem, giống ngày ngoài cửa sổ sửa. Hai hàng rào độc
  // lập, cái nào chặn tới ngày mới hơn thì cái đó quyết định (xem `app/core/data_lock.py`).
  const lockedUntil = data?.locked_until?.[company] ?? null;
  const closed = !isAdmin && !!lockedUntil && !!day && day <= lockedUntil;   // đã chốt số liệu
  const editable = useMemo(() => {
    if (!canEdit || !day || day > today || mergedUnit) return false;
    if (isAdmin) return true;
    if (lockedUntil && day <= lockedUntil) return false;
    return daysBetween(today, day) <= (data?.edit_window_days ?? 7);
  }, [canEdit, isAdmin, day, today, data, lockedUntil, mergedUnit]);

  // Đơn giá mủ nước/mủ chén → ghi thẳng kho "Giá mủ nguyên liệu" (đúng đơn vị + ngày), chỉ khi đổi.
  //
  // ĐƠN GIÁ 0 = "ngày đó không có giá": xoá ô giá, KHÔNG lưu số 0 (quy ước dùng chung — xem
  // `app/core/market_meta.py`). Lưu số 0 thì bản tin in ra khoảng "0-550 đồng/độ" cho cả khu vực
  // và giá bình quân gia quyền bị kéo tụt. Server chặn lần hai nên hai tầng luôn khớp.
  const savePrices = async (prices: PriceDraft) => {
    const orig = data?.prices?.[company];
    const jobs: Promise<unknown>[] = [];
    // Nhãn đơn vị lưu kèm giá: mủ nước = độ TSC, mủ chén và mủ dây = độ DRC (cố định, xem
    // `lib/purchase-price-unit.ts`) — server cũng ép lại nhãn này nên hai tầng luôn khớp.
    const PRICE_UNIT: Record<MemberPriceType, string> = {
      purchase: LATEX_PRICE_UNIT, purchase_cup: CUP_PRICE_UNIT, purchase_lace: LACE_PRICE_UNIT,
    };
    const each = (raw: number | null, ov: number | null, pt: MemberPriceType) => {
      const nv = raw === 0 ? null : raw;   // 0 = không có giá → coi như bỏ trống
      if ((nv ?? null) === (ov ?? null)) return;
      const unit = PRICE_UNIT[pt];
      if (role === "member") {
        jobs.push(nv == null
          ? clearMyPrice(company, day, pt)
          : upsertMyPrice(company, day, pt, nv));
      } else {
        jobs.push(nv == null
          ? deleteRecord({ as_of: day, source: "vrg", grade: company, contract: "", price_type: pt })
          : upsertRecord({ as_of: day, source: "vrg", grade: company, contract: "",
                           price_type: pt, price: nv, currency: "VND", unit }));
      }
    };
    each(prices.latex, orig?.latex ?? null, "purchase");
    each(prices.cup, orig?.cup ?? null, "purchase_cup");
    each(prices.lace, orig?.lace ?? null, "purchase_lace");
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
           title={`${editable ? "Nhập số liệu" : "Xem số liệu"} — ${KIND_LABEL[kind]}`}>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
        <DateInput value={day} onChange={setDay} noFuture style={{ width: 190 }} />
        <Select value={company} onChange={setCompany} showSearch style={{ minWidth: 220 }}
                options={units.map((u) => ({ value: u, label: u }))}
                filterOption={(i, o) => (o?.label ?? "").toLowerCase().includes(i.toLowerCase())} />
        {mergedUnit
          ? <Tag color="default">Đơn vị đã sáp nhập — chỉ tra cứu</Tag>
          : !canEdit
            ? <Tag color="default">{exists ? "Số liệu đã nhập" : "Ngày này chưa có số liệu"}</Tag>
            : exists
              ? <Tag color="blue">Đang sửa số đã có</Tag>
              : <Tag color="green">Tạo mới cho ngày này</Tag>}
      </div>
      {/* Nói ĐÚNG lý do khoá — ba lý do khác hẳn nhau và cách xử lý cũng khác:
          tài khoản chỉ xem (không bao giờ sửa được, đừng chờ) · ngày đã chốt (phải nhờ Ban TTKD
          sửa hộ) · ngoài cửa sổ nhập (hết hạn tự sửa). Ghi nhầm lý do là người dùng ngồi chờ hết
          cửa sổ trong khi thực ra phải gọi cho Ban, hoặc đi xin quyền mà vai trò vốn không có. */}
      {!editable && (
        <Alert type="info" showIcon style={{ marginBottom: 12 }}
               message={mergedUnit
                 ? `${company} đã sáp nhập vào đơn vị của bạn — số liệu trước ngày sáp nhập giữ `
                   + "nguyên để tra cứu và vẫn được cộng vào báo cáo, nhưng không sửa được nữa."
                 : !canEdit
                 ? "Tài khoản của bạn chỉ xem số liệu — việc nhập/sửa do tài khoản nhập liệu "
                   + "của đơn vị thực hiện."
                 : closed
                   ? `Số liệu đến hết ngày ${dmy(lockedUntil ?? "")} đã được chốt — đơn vị không tự `
                     + "sửa được nữa. Cần điều chỉnh, đề nghị báo Ban TTKD để chuyên viên sửa hộ."
                   : "Ngày này ở chế độ chỉ xem — ngoài cửa sổ nhập cho phép."} />
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
