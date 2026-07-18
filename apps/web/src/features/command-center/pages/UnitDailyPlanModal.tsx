/* Modal cấu hình CHỈ TIÊU KẾ HOẠCH thu mua năm cho từng đơn vị (dùng tính % thực hiện).
   Chỉ chuyên viên có quyền `unit_daily` / admin. */

import { InputNumber, message, Modal, Table } from "antd";
import { useEffect, useState } from "react";

import { fetchPlan, savePlan } from "../../../lib/unit-daily-client";

export default function UnitDailyPlanModal(
  { open, year, onClose }: { open: boolean; year: number; onClose: () => void },
) {
  const [units, setUnits] = useState<string[]>([]);
  const [plans, setPlans] = useState<Record<string, number | null>>({});
  const [saved, setSaved] = useState<Record<string, number | null>>({});
  const [saving, setSaving] = useState("");

  useEffect(() => {
    if (!open) return;
    fetchPlan(year)
      .then((d) => { setUnits(d.units); setPlans(d.plans); setSaved(d.plans); })
      .catch((e) => message.error(e.message));
  }, [open, year]);

  // Lưu khi rời ô nếu giá trị đổi so với đã lưu.
  const commit = async (unit: string) => {
    const v = plans[unit] ?? null;
    if (v === (saved[unit] ?? null)) return;
    setSaving(unit);
    try {
      await savePlan(year, unit, v);
      setSaved((s) => ({ ...s, [unit]: v }));
      message.success(`Đã lưu chỉ tiêu ${unit}`);
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setSaving("");
    }
  };

  return (
    <Modal open={open} onCancel={onClose} onOk={onClose} okText="Xong" cancelButtonProps={{ style: { display: "none" } }}
           title={`Chỉ tiêu kế hoạch thu mua năm ${year}`} width={520}>
      <Table
        rowKey="unit"
        size="small"
        pagination={false}
        scroll={{ y: 420 }}
        dataSource={units.map((u) => ({ unit: u }))}
        columns={[
          { title: "Đơn vị", dataIndex: "unit", key: "unit" },
          {
            title: "Kế hoạch năm (tấn)", key: "plan", width: 200, align: "right",
            render: (_: unknown, r: { unit: string }) => (
              <InputNumber
                value={plans[r.unit] ?? null}
                onChange={(v) => setPlans((p) => ({ ...p, [r.unit]: (v as number) ?? null }))}
                onBlur={() => commit(r.unit)}
                disabled={saving === r.unit}
                controls={false}
                min={0}
                decimalSeparator=","
                style={{ width: "100%" }}
                placeholder="—"
              />
            ),
          },
        ]}
      />
    </Modal>
  );
}
