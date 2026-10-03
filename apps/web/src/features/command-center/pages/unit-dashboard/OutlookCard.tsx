/* Card "Tiến độ bán hàng năm" — trả lời: HĐ dài hạn đã giao bao nhiêu trên cam kết HĐDH · còn phải
   giao bao nhiêu (HĐ/phụ lục đã ký chưa giao + cam kết HĐDH còn lại) · sau khi giao hết dự kiến bán
   bao nhiêu so KH bán hàng (khai thác + thu mua + hàng hóa) · doanh thu dự kiến so KH doanh thu.
   Dòng phương trình = CẢ PHẠM VI; % so KH = RỔ đơn vị có KH (luôn ghi rõ rổ). Số lấy nguyên từ
   server (plans/260926-hd-dai-han-phai-giao/api-contract.md mục 4) — web không tự cộng lại. */

import { RiseOutlined } from "@ant-design/icons";
import { Alert } from "antd";

import { dmy } from "../../../../lib/date";
import type { OutlookBlock } from "../../../../lib/unit-dashboard-client";
import DashboardCard from "./DashboardCard";
import OutlookBreakdownTable from "./OutlookBreakdownTable";
import OutlookEquation from "./OutlookEquation";
import OutlookMasterItems from "./OutlookMasterItems";
import OutlookPanels from "./OutlookPanels";
import type { BlockState } from "./use-dashboard-block";

export default function OutlookCard({ state }: { state: BlockState<OutlookBlock> }) {
  const d = state.data;
  return (
    <DashboardCard
      id="ud-outlook" state={state} warnings={(o) => o.warnings ?? []}
      title={<><RiseOutlined style={{ marginRight: 6 }} />Tiến độ bán hàng năm {d?.year ?? ""}</>}
      sub={d && <>Tính đến {dmy(d.as_of)} · Tổng còn phải giao = các HĐ/phụ lục đã ký chưa giao + phần
        cam kết HĐDH còn lại chưa ký phụ lục · DT dự kiến = DT đã thực hiện + SL còn phải giao × giá bán
        BQ lũy kế của từng đơn vị.</>}
    >
      {(o) => {
        const single = o.scope?.scope === "unit";
        return (
          <>
            {(o.critical_errors ?? []).map((error) => (
              <Alert key={error} type="error" showIcon className="ud-alert" title={error} />
            ))}
            <div className="ud-mini-title ud-ol-lead">
              Sản lượng đã giao và còn phải giao — {o.scope?.label || "cả phạm vi"}
            </div>
            <OutlookEquation data={o} />
            <OutlookPanels data={o} single={single} />
            {!!o.breakdown?.length && (
              <OutlookBreakdownTable rows={o.breakdown} childLabel={o.scope?.child_label ?? "Phạm vi con"} />
            )}
            {single && !!o.items?.length && <OutlookMasterItems items={o.items} />}
          </>
        );
      }}
    </DashboardCard>
  );
}
