import { CheckCircleOutlined, LockOutlined } from "@ant-design/icons";
import { App, Button, Card, Input, Select, Table, Typography } from "antd";
import { useState } from "react";

import { changeLabel, isBigChange } from "../../lib/change-warning";
import { dmy } from "../../lib/date";
import {
  type RecentRow,
  publicAuth,
  publicRecent,
  publicSubmit,
} from "../../lib/public-purchase-client";

const fmt = (n: number) => n.toLocaleString("vi-VN");
const wrap: React.CSSProperties = {
  minHeight: "100vh", background: "#0B6B3A", display: "flex",
  alignItems: "center", justifyContent: "center", padding: 16,
};

/** Trang CÔNG KHAI: đơn vị thành viên nhập giá mủ nước hôm nay (gác bằng mật khẩu chung). */
export default function PublicPurchaseInputPage() {
  const { message } = App.useApp();
  const [token, setToken] = useState("");
  const [units, setUnits] = useState<string[]>([]);
  const [today, setToday] = useState("");
  const [pw, setPw] = useState("");
  const [company, setCompany] = useState<string | undefined>();
  const [price, setPrice] = useState("");
  const [recent, setRecent] = useState<RecentRow[]>([]);
  const [busy, setBusy] = useState(false);

  const doAuth = async () => {
    if (!pw.trim()) return;
    setBusy(true);
    try {
      const r = await publicAuth(pw);
      setToken(r.token); setUnits(r.units); setToday(r.today);
    } catch (e) { message.error(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  const pickCompany = async (c: string) => {
    setCompany(c);
    try { setRecent((await publicRecent(token, c)).records); } catch { setRecent([]); }
  };

  // Cảnh báo: giá nhập lệch ≥10% so với lần gửi gần nhất của đơn vị (recent[0]).
  const prevPrice = recent[0]?.price ?? null;
  const priceNum = price.trim() ? Number(price.replace(/[.,\s]/g, "")) : null;
  const warnPrice = isBigChange(priceNum, prevPrice);

  const submit = async () => {
    if (!company) { message.warning("Chọn đơn vị của bạn"); return; }
    const p = Number(price.replace(/[.,\s]/g, ""));
    if (!p || p <= 0) { message.warning("Nhập giá hợp lệ (đồng/độ TSC)"); return; }
    setBusy(true);
    try {
      await publicSubmit(token, company, p);
      message.success(`Đã gửi giá ngày ${dmy(today)} cho ${company}`);
      setPrice("");
      setRecent((await publicRecent(token, company)).records);
    } catch (e) { message.error(e instanceof Error ? e.message : "Lỗi gửi"); }
    finally { setBusy(false); }
  };

  if (!token) {
    return (
      <div style={wrap}>
        <Card style={{ width: 380, maxWidth: "100%" }}>
          <Typography.Title level={4} style={{ marginTop: 0 }}>
            <LockOutlined /> Nhập giá mủ nước
          </Typography.Title>
          <Typography.Paragraph type="secondary">
            Nhập mật khẩu do VRG cung cấp để tiếp tục nhập giá.
          </Typography.Paragraph>
          <Input.Password value={pw} onChange={(e) => setPw(e.target.value)}
            placeholder="Mật khẩu" onPressEnter={doAuth} autoFocus />
          <Button type="primary" block style={{ marginTop: 12 }} loading={busy} onClick={doAuth}>
            Tiếp tục
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div style={{ ...wrap, alignItems: "flex-start", paddingTop: 40 }}>
      <Card style={{ width: 480, maxWidth: "100%" }}
        title={<span><CheckCircleOutlined style={{ color: "#16AF67" }} /> Nhập giá mủ nước — ngày {dmy(today)}</span>}>
        <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
          Chọn đơn vị của bạn và nhập giá mủ nước hôm nay (đồng/độ TSC). Chỉ nhập cho ngày hiện tại.
        </Typography.Paragraph>

        <div style={{ marginBottom: 10 }}>
          <label style={{ fontWeight: 600 }}>Đơn vị</label>
          <Select showSearch value={company} onChange={pickCompany} placeholder="Chọn đơn vị của bạn"
            style={{ width: "100%", marginTop: 4 }}
            options={units.map((u) => ({ value: u, label: u }))}
            filterOption={(i, o) => (o?.label ?? "").toLowerCase().includes(i.toLowerCase())} />
        </div>

        <div style={{ marginBottom: 12 }}>
          <label style={{ fontWeight: 600 }}>Giá mủ nước (đồng/độ TSC)</label>
          <Input value={price} onChange={(e) => setPrice(e.target.value)} inputMode="numeric"
            placeholder="vd: 550" onPressEnter={submit} style={{ marginTop: 4 }} disabled={!company}
            status={warnPrice ? "warning" : undefined} />
          {warnPrice && (
            <Typography.Text type="warning" style={{ fontSize: 12, display: "block", marginTop: 4 }}>
              Lệch {changeLabel(priceNum as number, prevPrice as number)} so với lần gần nhất ({fmt(prevPrice as number)}) — kiểm tra lại số liệu.
            </Typography.Text>
          )}
        </div>

        <Button type="primary" block loading={busy} disabled={!company} onClick={submit}>
          Gửi giá ngày {dmy(today)}
        </Button>

        {company && (
          <>
            <Typography.Text strong style={{ display: "block", margin: "16px 0 6px" }}>
              Giá gần đây của {company}
            </Typography.Text>
            <Table size="small" pagination={false} rowKey="as_of"
              locale={{ emptyText: "Chưa có giá nào" }}
              dataSource={recent}
              columns={[
                { title: "Ngày", dataIndex: "as_of", render: (d: string) => dmy(d) },
                { title: "Giá (đồng/độ TSC)", dataIndex: "price", align: "right", render: (p: number) => fmt(p) },
              ]} />
          </>
        )}
      </Card>
    </div>
  );
}
