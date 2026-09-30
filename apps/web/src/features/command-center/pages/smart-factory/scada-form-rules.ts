/* Luật kiểm tra + giá trị mặc định của form cấu hình kết nối SCADA — KHỚP server
   (api-contract.md §3 + "Sửa đổi sau review"): server vẫn kiểm lại, web chặn trước cho người khai
   đỡ phải gửi đi gửi lại. */

import type { Rule as FormRule, RuleObject } from "antd/es/form";
import type { NamePath } from "antd/es/form/interface";

import type { ScadaFactory, ScadaFactoryInput } from "../../../../lib/smart-factory-client";

/** Tag Historian (dựng thẳng vào câu truy vấn → phải kiểm nghiêm để chống injection). */
export const TAG_RE = /^[A-Za-z0-9_.$#-]{1,128}$/;
/** CSDL · linked server. */
export const IDENT_RE = /^[A-Za-z0-9_]{1,128}$/;

export const DEFAULT_ENERGY_TAGS = ["PM_EnergyReal0", "PM_EnergyReal1", "PM_EnergyReal2", "PM_EnergyReal3"];

/** 4 ô tag điện CỐ ĐỊNH theo thanh ghi cao → thấp — không thể đảo thứ tự như ô chọn nhiều tag. */
export const ENERGY_SLOTS = [
  "R0 (cao nhất, ×2⁴⁸)", "R1 (×2³²)", "R2 (×65.536)", "R3 (thấp nhất, ×1)",
].map((label, i) => ({ key: `R${i}`, label, name: ["energy_tags", i] as NamePath, short: `R${i}` }));

/** Mọi ô tag (để bắt trùng) — `short` dùng trong câu báo lỗi. */
const TAG_FIELDS: { key: string; name: NamePath; short: string }[] = [
  ...ENERGY_SLOTS,
  { key: "water", name: "water_tag", short: "Tag nước" },
  { key: "bales", name: "bales_tag", short: "Tag số bành" },
];

export type ScadaFormValues = {
  name: string; host: string; port: number; username: string; password?: string;
  database: string; linked_server: string;
  energy_tags: (string | undefined)[]; water_tag?: string; bales_tag?: string;
  layout_key?: string; enabled: boolean;
};

export function initialValues(f: ScadaFactory | null): ScadaFormValues {
  if (!f) {
    return {
      name: "", host: "", port: 1433, username: "", password: "",
      database: "Runtime", linked_server: "INSQL",
      energy_tags: DEFAULT_ENERGY_TAGS, water_tag: "Water_TotalVolume", bales_tag: "", layout_key: "",
      enabled: true,
    };
  }
  return {
    name: f.name, host: f.host, port: f.port, username: f.username, password: "",
    database: f.database, linked_server: f.linked_server,
    energy_tags: ENERGY_SLOTS.map((_, i) => f.energy_tags[i] ?? ""),
    water_tag: f.water_tag ?? "", bales_tag: f.bales_tag ?? "", layout_key: f.layout_key ?? "",
    enabled: f.enabled,
  };
}

const norm = (v: unknown) => (typeof v === "string" ? v.trim() : "");
const blankToNull = (s?: string) => norm(s) || null;

/** Giá trị form → body API. Sửa mà để trống mật khẩu = giữ mật khẩu cũ (gửi null).
 *  Tag điện: các ô đã điền, GIỮ thứ tự R0..R3 (luật form bảo đảm chỉ còn 0, 1 = R0, hoặc 4 ô). */
export const toInput = (v: ScadaFormValues): ScadaFactoryInput => ({
  name: v.name.trim(), host: v.host.trim(), port: v.port, username: v.username.trim(),
  password: v.password ? v.password : null,
  database: v.database.trim(), linked_server: v.linked_server.trim(),
  energy_tags: (v.energy_tags ?? []).map(norm).filter(Boolean),
  water_tag: blankToNull(v.water_tag), bales_tag: blankToNull(v.bales_tag),
  layout_key: blankToNull(v.layout_key),
  enabled: v.enabled,
});

const reject = (msg: string) => Promise.reject(new Error(msg));
const ok = () => Promise.resolve();

export const identRule: RuleObject = {
  validator: (_, v?: string) => (!norm(v) || IDENT_RE.test(norm(v)) ? ok()
    : reject("Chỉ gồm chữ không dấu, số, dấu gạch dưới (_) — tối đa 128 ký tự")),
};

const tagFormatRule: RuleObject = {
  validator: (_, v?: string) => (!norm(v) || TAG_RE.test(norm(v)) ? ok()
    : reject("Chỉ gồm chữ không dấu, số và các ký tự _ . $ # - (tối đa 128 ký tự)")),
};

/** Ô tag điện đang TRỐNG mà các ô khác lại khai dở: hợp lệ chỉ khi đủ 4 ô, chỉ ô R0, hoặc trống cả 4. */
const energySlotRule: FormRule = ({ getFieldValue }) => ({
  validator: (_, v?: string) => {
    if (norm(v)) return ok();
    const filled = ENERGY_SLOTS.map((s) => !!norm(getFieldValue(s.name)));
    const n = filled.filter(Boolean).length;
    return n === 0 || n === 4 || (n === 1 && filled[0]) ? ok()
      : reject("Điền đủ 4 ô R0–R3, hoặc chỉ ô R0 nếu tag đã là kWh");
  },
});

/** Tag trùng với ô khác (không phân biệt hoa thường — server cũng chặn). */
const uniqueTagRule = (key: string): FormRule => ({ getFieldValue }) => ({
  validator: (_, v?: string) => {
    const t = norm(v).toLowerCase();
    const other = t
      ? TAG_FIELDS.find((f) => f.key !== key && norm(getFieldValue(f.name)).toLowerCase() === t)
      : undefined;
    return other ? reject(`Trùng tag với ô ${other.short}`) : ok();
  },
});

/** Props chung của một ô tag: đúng định dạng · không trùng · (tag điện) không khai dở —
 *  kiểm lại mỗi khi ô tag khác đổi. */
export function tagItemProps(key: string) {
  const self = TAG_FIELDS.find((f) => f.key === key)!;
  return {
    name: self.name,
    dependencies: TAG_FIELDS.filter((f) => f.key !== key).map((f) => f.name),
    rules: [tagFormatRule, ...(key.startsWith("R") ? [energySlotRule] : []), uniqueTagRule(key)],
  };
}

/** Sửa: đổi máy chủ/cổng/tài khoản thì mật khẩu cũ không còn đúng chỗ → bắt nhập lại (server cũng chặn). */
export const passwordRule = (factory: ScadaFactory | null): FormRule => ({ getFieldValue }) => ({
  validator: (_, v?: string) => {
    if (v) return ok();
    if (!factory) return reject("Nhập mật khẩu");
    const moved = norm(getFieldValue("host")) !== factory.host
      || getFieldValue("port") !== factory.port
      || norm(getFieldValue("username")) !== factory.username;
    return moved ? reject("Đổi máy chủ, cổng hoặc tài khoản thì phải nhập lại mật khẩu.") : ok();
  },
});
