/* Soạn Bản nháp tờ trình giá sàn: sửa tay tiêu đề · ghi chú · phương án (mục 3) · 2 khối diễn giải
   (mục 1 thị trường kỳ hạn, mục 2 vật chất + tồn kho) → lưu · xem trước/in PDF · xoá.
   Không ghi biểu giá sàn chính thức. Lãnh đạo Tập đoàn chỉ xem. */

import {
  ArrowLeftOutlined, DeleteOutlined, EyeOutlined, FormOutlined, SaveOutlined,
} from "@ant-design/icons";
import { Alert, App, Button, Input, Popconfirm, Spin, Tag } from "antd";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { DRAFT_LIST_PATH, DRAFT_SOURCE_LABEL } from "../../../lib/floor-proposal-client";
import { dmy, stampVN } from "../../../lib/date";
import { ApiError } from "../../../lib/http";
import { useAuth } from "../../auth/AuthContext";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import { useUnsavedGuard } from "../unsaved-guard";
import FloorDraftNarrative from "./components/FloorDraftNarrative";
import FloorProposalPanel from "./components/FloorProposalPanel";
import ToTrinhPreview from "./components/ToTrinhPreview";
import { useFloorDraft } from "./useFloorDraft";

const errText = (e: unknown) => (e instanceof Error ? e.message : "Có lỗi xảy ra, vui lòng thử lại.");
const LABEL: React.CSSProperties = { display: "block", fontSize: 12.5, color: "var(--muted)", marginBottom: 4 };

export default function FloorDraftEditorPage() {
  const { id: idParam } = useParams<{ id: string }>();
  const id = Number(idParam);
  const { canEditCap } = useAuth();
  const { message, modal } = App.useApp();
  const navigate = useNavigate();
  const canEdit = canEditCap("floor_suggest");
  const {
    draft, form, dirty, loading, saving, err, applier, patch, save, remove, reload, previewHtml,
  } = useFloorDraft(id);
  const [preview, setPreview] = useState(false);
  // Đang có thay đổi chưa lưu → menu / đăng xuất / đóng tab đều hỏi lại (nút Back trình duyệt thì không).
  const leaveGuard = useUnsavedGuard(dirty);

  // Người khác đã lưu bản nháp sau lúc mình mở → không lưu đè; cho chọn tải bản mới hoặc ở lại chép tay.
  const askReloadOnConflict = (msg: string) => {
    modal.confirm({
      title: "Bản nháp đã được người khác lưu", width: 520,
      content: `${msg} Bạn có thể tải bản mới nhất (bỏ phần đang sửa) hoặc ở lại để tự chép phần sửa ra trước.`,
      okText: "Tải bản mới nhất (bỏ phần sửa của tôi)", cancelText: "Ở lại", okButtonProps: { danger: true },
      onOk: async () => {
        try { await reload(); message.success("Đã tải bản mới nhất."); } catch (e) { message.error(errText(e)); }
      },
    });
  };

  const doSave = async () => {
    if (!form) return;
    if (!form.title.trim()) { message.warning("Nhập tiêu đề bản nháp trước khi lưu."); return; }
    try {
      await save();
      message.success("Đã lưu bản nháp.");
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) askReloadOnConflict(e.message);
      else message.error(errText(e));
    }
  };

  const doDelete = async () => {
    try {
      await remove();
      message.success("Đã xoá bản nháp.");
      navigate(DRAFT_LIST_PATH);
    } catch (e) {
      message.error(errText(e));
    }
  };

  const back = () => leaveGuard(() => navigate(DRAFT_LIST_PATH));

  if (loading) return <div className="main" style={{ padding: 32, textAlign: "center" }}><Spin /></div>;
  if (err || !draft || !form) {
    return (
      <div className="main">
        <Alert type="error" showIcon message={err || "Không tìm thấy bản nháp."} style={{ marginBottom: 12 }} />
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(DRAFT_LIST_PATH)}>Về danh sách bản nháp</Button>
      </div>
    );
  }

  const readOnly = !canEdit;

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><FormOutlined style={{ marginRight: 8 }} />Bản nháp tờ trình giá sàn</h2>
          <p>
            Ngày tờ trình <b>{dmy(draft.as_of)}</b> · Lần {draft.doc?.lan ?? "—"} ·{" "}
            <Tag style={{ marginInlineEnd: 4 }}>{DRAFT_SOURCE_LABEL[draft.source] ?? draft.source}</Tag>
            · Sửa lần cuối: {draft.updated_by ?? draft.created_by ?? "—"} lúc {stampVN(draft.updated_at)}
          </p>
        </div>
      </div>
      <ReadOnlyNotice cap="floor_suggest" />

      <div className="card" style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
        <Button icon={<ArrowLeftOutlined />} onClick={back}>Danh sách</Button>
        {!readOnly && (
          // Không khoá theo `dirty`: ô vừa gõ chỉ được áp khi blur (lúc bấm nút) — khoá nút là cú bấm
          // đầu tiên bị nuốt vì nút còn khoá ở thời điểm blur. Lưu luôn chờ hàng đợi áp số rảnh.
          <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={doSave}>
            Lưu
          </Button>
        )}
        <Button icon={<EyeOutlined />} onClick={() => setPreview(true)}>Xem trước / In PDF</Button>
        {dirty && <Tag color="warning">Có thay đổi chưa lưu</Tag>}
        {!readOnly && (
          <Popconfirm title="Xoá bản nháp này?" description="Bản nháp đã xoá không khôi phục được."
            okText="Xoá" cancelText="Huỷ" okButtonProps={{ danger: true }} onConfirm={doDelete}>
            <Button danger icon={<DeleteOutlined />} style={{ marginLeft: "auto" }}>Xoá</Button>
          </Popconfirm>
        )}
        <div className="form-note" style={{ fontSize: 12.5, width: "100%" }}>
          Bản nháp không ghi vào biểu giá sàn chính thức. Số thị trường ở mục 1–2 là ảnh chụp lúc tạo bản nháp.
        </div>
      </div>

      <div className="card" style={{ marginTop: 12, display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(min(300px, 100%), 1fr))" }}>
        <label>
          <span style={LABEL}>Tiêu đề</span>
          <Input value={form.title} readOnly={readOnly} maxLength={200}
            onChange={(e) => patch({ title: e.target.value })} />
        </label>
        <label>
          <span style={LABEL}>Ghi chú nội bộ (không in lên tờ trình)</span>
          <Input.TextArea value={form.note} readOnly={readOnly} maxLength={4000} autoSize={{ minRows: 1, maxRows: 5 }}
            onChange={(e) => patch({ note: e.target.value })} />
        </label>
      </div>

      <div className="card" style={{ marginTop: 12 }}>
        <div className="card-head" style={{ marginBottom: 6 }}><h3 style={{ margin: 0 }}>Mục 3 — Phương án giá sàn</h3></div>
        <FloorProposalPanel proposal={form.proposal} applier={applier} readOnly={readOnly} />
      </div>

      <div style={{ marginTop: 12, display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(min(360px, 100%), 1fr))" }}>
        <FloorDraftNarrative title="Mục 1 — Diễn giải thị trường kỳ hạn" readOnly={readOnly}
          hint="Mỗi ô là một đoạn in dưới bảng giá các sàn. Ô để trống sẽ bị bỏ khi lưu."
          paragraphs={form.n1} onChange={(n1) => patch({ n1 })} />
        <FloorDraftNarrative title="Mục 2 — Diễn giải thị trường vật chất và tồn kho" readOnly={readOnly}
          hint="Mỗi ô là một đoạn in dưới bảng giá physical. Ô để trống sẽ bị bỏ khi lưu."
          paragraphs={form.n2} onChange={(n2) => patch({ n2 })} />
      </div>

      {preview && (
        <ToTrinhPreview
          title={`Xem trước Tờ trình giá sàn — ${form.title || dmy(draft.as_of)}${dirty ? " (gồm thay đổi chưa lưu)" : ""}`}
          load={previewHtml}
          extraActions={!readOnly && dirty && (
            <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={doSave}>Lưu</Button>
          )}
          onClose={() => setPreview(false)}
        />
      )}
    </div>
  );
}
