/* Thanh lọc màn Chỉ số đơn vị. Bộ lọc GIỮ NGUYÊN khi đổi tab — chỉ ô "ngày chốt" của tab Tồn kho
   là hiện thêm, vì tồn kho là số thời điểm chứ không cộng dồn theo kỳ.
   Ô chủng loại làm mờ ở tab không gắn chủng loại (mủ nước/chén/dây và kế hoạch năm khai theo
   tổng) — để trống ô đó còn hơn để người dùng lọc rồi tưởng số bị thiếu. */

import { ReloadOutlined } from "@ant-design/icons";
import { Button, Checkbox, Segmented, Select, Tooltip } from "antd";
import { useState } from "react";

import { PRESETS, type Preset, rangeOf } from "../../../../lib/date-presets";
import type { FilterCatalog } from "../../../../lib/unit-analytics-client";
import type { ScorecardFilters, TabInfo } from "../../../../lib/unit-scorecard-client";
import DateInput from "../../sections/DateInput";
import { MultiSelect, SplitMergedToggle } from "../analytics/AnalyticsFilters";

const GRADE_OFF = "Chỉ số của tab này không gắn chủng loại (mủ nước/chén/dây và kế hoạch năm "
  + "đơn vị khai theo tổng). Muốn xem theo chủng loại thì sang tab Tiêu thụ, Tồn kho "
  + "hoặc Thu mua.";
const GRADE_PARTIAL = "Ở tab Thu mua, lọc chủng loại chỉ tác động phần THÀNH PHẨM mua ngoài; "
  + "mủ nước/chén/dây không gắn chủng loại nên giữ nguyên.";
const GRADE_SPLIT = "Tab này đã tách sẵn theo chủng loại — mỗi cột là một chủng loại, "
  + "không cần lọc thêm.";

type Props = {
  catalog: FilterCatalog | null;
  tab: TabInfo | undefined;
  value: ScorecardFilters;
  onChange: (f: ScorecardFilters) => void;
  hideEmpty: boolean;
  onHideEmptyChange: (v: boolean) => void;
  onReload: () => void;
  loading?: boolean;
};

export default function ScorecardFilterBar({
  catalog, tab, value, onChange, hideEmpty, onHideEmptyChange, onReload, loading,
}: Props) {
  const [preset, setPreset] = useState<Preset>("Tháng này");
  const patch = (p: Partial<ScorecardFilters>) => onChange({ ...value, ...p });

  const pickPreset = (p: Preset) => {
    setPreset(p);
    const r = rangeOf(p);
    // Ngày chốt tồn kho bám ngày cuối kỳ cho tới khi người dùng tự chọn ngày khác.
    if (r) onChange({ ...value, from: r.from, to: r.to, asOf: r.to });
  };

  const units = (catalog?.units ?? []).filter(
    (u) => !value.regions.length || value.regions.includes(u.region ?? ""));
  const unitNames = value.splitMerged
    ? [...units.map((u) => u.name), ...(catalog?.merged_units ?? []).map((m) => m.name)]
    : units.map((u) => u.name);
  const gradeMode = tab?.grade_filter ?? "none";
  const splitByGrade = value.tab === "by_grade";

  return (
    <div className="card" style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
      <Segmented value={preset} onChange={(v) => pickPreset(v as Preset)} options={[...PRESETS]} />
      <DateInput value={value.from} style={{ width: 150 }}
                 onChange={(v) => { patch({ from: v }); setPreset("Tự chọn"); }} />
      <span style={{ color: "var(--muted)" }}>→</span>
      <DateInput value={value.to} style={{ width: 150 }}
                 onChange={(v) => { patch({ to: v, asOf: v }); setPreset("Tự chọn"); }} />

      {tab?.axis === "as_of" && (
        <Tooltip title="Tồn kho là số THỜI ĐIỂM: chọn đúng một ngày chốt, không cộng dồn cả kỳ.">
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <b style={{ fontSize: 12 }}>Chốt ngày</b>
            <DateInput value={value.asOf ?? value.to} style={{ width: 150 }}
                       onChange={(v) => patch({ asOf: v })} />
          </span>
        </Tooltip>
      )}

      <MultiSelect placeholder="Tất cả khu vực" options={catalog?.regions ?? []} width={185}
                   value={value.regions} onChange={(v) => patch({ regions: v })} />
      <MultiSelect placeholder="Tất cả đơn vị" options={unitNames} width={225}
                   value={value.companies} onChange={(v) => patch({ companies: v })} />

      <Tooltip title={splitByGrade ? GRADE_SPLIT
                      : gradeMode === "none" ? GRADE_OFF
                      : gradeMode === "partial" ? GRADE_PARTIAL : ""}>
        <span>
          <Select
            mode="multiple" allowClear maxTagCount="responsive" style={{ minWidth: 205 }}
            disabled={gradeMode === "none"} value={value.grades}
            placeholder={splitByGrade ? "Cột đã là chủng loại"
                         : gradeMode === "none" ? "Chủng loại: xem ở tab khác"
                         : "Tất cả chủng loại"}
            onChange={(v) => patch({ grades: v })}
            options={(catalog?.grades ?? []).map((g) => ({ value: g, label: g }))}
          />
        </span>
      </Tooltip>

      {value.tab === "compliance" && (
        <Segmented
          value={value.statusKind} options={[{ value: "purchase", label: "Biểu Thu mua" },
                                             { value: "consumption", label: "Biểu Tiêu thụ" }]}
          onChange={(v) => patch({ statusKind: v as "purchase" | "consumption" })}
        />
      )}

      <SplitMergedToggle catalog={catalog} value={value.splitMerged}
                         onChange={(v) => patch({ splitMerged: v })} />
      <Tooltip title="Bỏ bớt dòng của đơn vị chưa có số nào trong kỳ. Số ở dòng khu vực và dòng tổng KHÔNG đổi.">
        <Checkbox checked={hideEmpty} onChange={(e) => onHideEmptyChange(e.target.checked)}>
          Ẩn đơn vị chưa có số
        </Checkbox>
      </Tooltip>
      <Button icon={<ReloadOutlined />} onClick={onReload} loading={loading}>Tải lại</Button>
    </div>
  );
}
