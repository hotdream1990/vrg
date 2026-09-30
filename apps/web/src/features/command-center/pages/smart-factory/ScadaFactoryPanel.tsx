/* Tab "SCADA nhà máy" trong Quản trị → Cấu hình hệ thống (chỉ admin) — mỗi nhà máy một máy chủ SQL
   Server của SCADA (AVEVA Historian, linked server INSQL) + tên tag điện · nước · số bành. Nút "Kiểm
   tra kết nối" đọc thử số mới nhất để đối chiếu với màn SCADA tại nhà máy. Mật khẩu không hiện lại.
   Nằm TRONG <Form> của trang cấu hình: nút ở đây là htmlType "button" (mặc định AntD) nên không
   submit form ngoài; form sửa nhà máy mở trong Modal (portal) với Form riêng. */

import {
  ApiOutlined, DeleteOutlined, EditOutlined, PlusOutlined, ReloadOutlined,
} from "@ant-design/icons";
import { Alert, App, Button, Grid, Popconfirm, Space, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useState } from "react";

import {
  type ScadaFactory, type ScadaTestResult, deleteScadaFactory, fetchScadaFactories, testScadaFactory,
} from "../../../../lib/smart-factory-client";
import ScadaFactoryFormModal from "./ScadaFactoryFormModal";
import ScadaTestResultModal from "./ScadaTestResultModal";
import { errText } from "./smart-factory-format";
import "./smart-factory.css";

const TagList = ({ tags }: { tags: (string | null)[] }) => {
  const list = tags.filter((t): t is string => !!t);
  if (!list.length) return <span className="sf-muted">—</span>;
  return (
    <Space size={[4, 4]} wrap>
      {list.map((t, i) => <Tag key={`${i}-${t}`} className="sf-code">{t}</Tag>)}
    </Space>
  );
};

/** Gộp tag điện · nước · số bành vào MỘT cột (3 dòng) để bảng không tràn đẩy cột Thao tác ra ngoài. */
const FactoryTags = ({ f }: { f: ScadaFactory }) => (
  <div className="sf-tag-lines">
    <span className="sf-muted">Điện</span><TagList tags={f.energy_tags} />
    <span className="sf-muted">Nước</span><TagList tags={[f.water_tag]} />
    <span className="sf-muted">Số bành</span><TagList tags={[f.bales_tag]} />
  </div>
);

export default function ScadaFactoryPanel() {
  const { message } = App.useApp();
  // Ghim cột tên/thao tác chỉ khi màn đủ rộng — màn điện thoại ghim 2 đầu thì chiếm hết chỗ, đè nhau.
  const pin = Grid.useBreakpoint().md;
  const [rows, setRows] = useState<ScadaFactory[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState<ScadaFactory | "new" | null>(null);
  const [testingId, setTestingId] = useState<number | null>(null);
  const [tested, setTested] = useState<{ name: string; result: ScadaTestResult } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      setRows((await fetchScadaFactories()).factories);
    } catch (e) {
      setErr(errText(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const runTest = async (f: ScadaFactory) => {
    setTestingId(f.id);
    try {
      setTested({ name: f.name, result: await testScadaFactory(f.id) });
    } catch (e) {
      message.error(errText(e));
    } finally {
      setTestingId(null);
    }
  };

  const remove = async (f: ScadaFactory) => {
    try {
      await deleteScadaFactory(f.id);
      message.success(`Đã xoá ${f.name}.`);
      void load();
    } catch (e) {
      message.error(errText(e));
    }
  };

  const onSaved = (f: ScadaFactory) => {
    message.success(editing === "new" ? `Đã thêm ${f.name}.` : `Đã lưu ${f.name}.`);
    setEditing(null);
    void load();
  };

  const columns: ColumnsType<ScadaFactory> = [
    { title: "Tên nhà máy", dataIndex: "name", key: "name", fixed: pin ? "left" : undefined,
      render: (n: string) => <b>{n}</b> },
    { title: "Máy chủ", key: "host",
      render: (_, f) => (
        <div className="sf-code">
          {f.host}:{f.port}
          <div className="sf-muted">{f.database} / {f.linked_server}</div>
        </div>
      ) },
    { title: "Tag Historian", key: "tags", render: (_, f) => <FactoryTags f={f} /> },
    { title: "Trạng thái", dataIndex: "enabled", key: "enabled",
      render: (on: boolean) => (on ? <Tag color="green">Bật</Tag> : <Tag>Tắt</Tag>) },
    { title: "Thao tác", key: "act", fixed: pin ? "right" : undefined,
      render: (_, f) => (
        <Space size={6} wrap>
          <Button size="small" type="primary" ghost icon={<ApiOutlined />}
            loading={testingId === f.id} disabled={testingId != null && testingId !== f.id}
            onClick={() => void runTest(f)}>Kiểm tra kết nối</Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => setEditing(f)}>Sửa</Button>
          <Popconfirm
            title={`Xoá cấu hình ${f.name}?`}
            description="Màn chỉ số sẽ không còn đọc được số liệu của nhà máy này."
            okText="Xoá" cancelText="Huỷ" okButtonProps={{ danger: true }}
            onConfirm={() => remove(f)}>
            <Button size="small" danger icon={<DeleteOutlined />}>Xoá</Button>
          </Popconfirm>
        </Space>
      ) },
  ];

  return (
    <div>
      <div className="sf-panel-bar">
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void load()}>Tải lại</Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setEditing("new")}>Thêm nhà máy</Button>
      </div>

      {err && (
        <Alert type="error" showIcon className="sf-alert" title={`Chưa tải được danh sách: ${err}`}
          action={<Button size="small" onClick={() => void load()}>Thử lại</Button>} />
      )}

      <Table<ScadaFactory>
        rowKey="id" size="middle" loading={loading} columns={columns} dataSource={rows}
        pagination={false} scroll={{ x: "max-content" }}
        locale={{ emptyText: "Chưa có nhà máy nào — bấm “Thêm nhà máy” để khai kết nối SCADA." }}
      />

      {editing && (
        <ScadaFactoryFormModal
          factory={editing === "new" ? null : editing}
          onClose={() => setEditing(null)} onSaved={onSaved}
        />
      )}
      {tested && (
        <ScadaTestResultModal name={tested.name} result={tested.result} onClose={() => setTested(null)} />
      )}
    </div>
  );
}
