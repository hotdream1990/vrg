/* Bước Tờ trình: AI soạn phần nhận định (như Báo cáo tuần — bản nháp cho chuyên viên soát, KHÔNG tự lưu) ·
   xem trước / in · tải PDF · tải Word (dựng từ BẢN ĐÃ LƯU, tự lưu trước khi tải) · sửa nội dung. */

import { EyeOutlined, FilePdfOutlined, FileWordOutlined, RobotOutlined } from "@ant-design/icons";
import { Alert, App, Button, Space } from "antd";
import { useState } from "react";

import { type DraftFile, type Memo, fetchDraftFile, memoAi, saveBlob } from "../../../../lib/floor-draft-flow-client";
import ToTrinhMemoEditor from "./ToTrinhMemoEditor";

type Props = {
  draftId: number;
  sig: string;                   // chữ ký số phương án hiện tại
  memo: Memo;
  editable: boolean;
  ensureSaved: () => Promise<void>;
  onMemo: (m: Memo) => void;
  onPreview: () => void;
};

const errText = (e: unknown) => (e instanceof Error ? e.message : "Có lỗi xảy ra, vui lòng thử lại.");
const hasText = (m: Memo) => [...m.futures, ...m.physical, ...m.outlook].some((p) => p.text.trim());

export default function ToTrinhPanel({ draftId, sig, memo, editable, ensureSaved, onMemo, onPreview }: Props) {
  const { message, modal } = App.useApp();
  const [aiBusy, setAiBusy] = useState(false);
  const [file, setFile] = useState<DraftFile | null>(null);
  // Nội dung được soạn/soát theo bộ số khác bộ số hiện tại (vd trả về Nháp sửa số theo ý lãnh đạo).
  const stale = Boolean(memo.sig) && memo.sig !== sig;

  const runAi = async () => {
    setAiBusy(true);
    try {
      const res = await memoAi(draftId, memo);
      onMemo(res.memo);
      message.success(res.warnings.length ? "AI đã soạn xong — xem các cảnh báo trước khi lưu."
        : "AI đã soạn xong — soát lại rồi bấm Lưu.");
    } catch (e) {
      message.error(errText(e));
    } finally {
      setAiBusy(false);
    }
  };

  const askAi = () => {
    if (!hasText(memo)) { void runAi(); return; }
    modal.confirm({
      title: "AI viết lại phần nhận định?", width: 520, okText: "AI soạn lại", cancelText: "Huỷ",
      content: "AI sẽ thay dòng nguồn, diễn giải từng sàn, mục II và phần cung – cầu bằng bản mới dựa trên số liệu "
        + "của bản nháp. Số tờ trình, tồn kho, câu kính trình và người ký giữ nguyên. Chưa lưu cho tới khi bạn bấm Lưu.",
      onOk: runAi,
    });
  };

  const download = async (f: DraftFile) => {
    setFile(f);
    try {
      await ensureSaved();
      const out = await fetchDraftFile(draftId, f);
      saveBlob(out.blob, out.name);
    } catch (e) {
      message.error(errText(e));
    } finally {
      setFile(null);
    }
  };

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div className="card">
        <Space wrap size={8}>
          {editable && (
            <Button type="primary" icon={<RobotOutlined />} loading={aiBusy} onClick={askAi}>AI soạn nội dung</Button>
          )}
          <Button icon={<EyeOutlined />} onClick={onPreview}>Xem trước / In</Button>
          <Button icon={<FilePdfOutlined />} loading={file === "to-trinh.pdf"} onClick={() => download("to-trinh.pdf")}>
            Tải PDF
          </Button>
          <Button icon={<FileWordOutlined />} loading={file === "to-trinh.docx"} onClick={() => download("to-trinh.docx")}>
            Tải Word
          </Button>
        </Space>
        {aiBusy && <div style={{ marginTop: 8, color: "var(--muted)", fontSize: 12.5 }}>AI đang đọc số liệu, báo cáo tuần và tin tức để soạn — có thể mất 20–60 giây.</div>}
        <div className="form-note" style={{ fontSize: 12.5, marginTop: 8 }}>
          Theo mẫu Tờ trình 54/TTr-TTKD. Bảng giá các sàn và bảng đề xuất do hệ thống dựng từ số của bản nháp.
        </div>
        {stale && (
          <Alert type="warning" showIcon style={{ marginTop: 10 }}
            title="Số phương án đã đổi kể từ lần soạn nội dung tờ trình"
            description="Bảng giá đề xuất đã tự theo số mới; phần nhận định có thể còn nói theo mức cũ. Bấm “AI soạn nội dung” để viết lại, hoặc soát tay rồi đánh dấu đã soát."
            action={editable && (
              <Button size="small" onClick={() => onMemo({ ...memo, sig })}>Đã soát, khớp số mới</Button>
            )} />
        )}
        {memo.ai && memo.ai.warnings.length > 0 && !stale && (
          <Alert type="info" showIcon style={{ marginTop: 10 }} title="Cảnh báo từ lần AI soạn gần nhất"
            description={<ul style={{ margin: 0, paddingLeft: 18 }}>{memo.ai.warnings.map((w) => <li key={w}>{w}</li>)}</ul>} />
        )}
      </div>
      <ToTrinhMemoEditor memo={memo} readOnly={!editable} onChange={onMemo} />
    </div>
  );
}
