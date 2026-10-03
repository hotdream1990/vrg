/* Bản nháp giá sàn theo quy trình 4 bước: Nháp (chỉnh số) → Dự thảo (chốt số · chép hình dự thảo) →
   Tờ trình (soạn nội dung · AI · xuất Word/PDF theo mẫu mới) → Áp dụng (có trong quy trình, chưa làm).
   Mỗi phần chỉ sửa ở đúng bước của nó (server chặn). Không ghi biểu giá sàn chính thức.
   Lãnh đạo Tập đoàn chỉ xem/tải. */

import { ArrowLeftOutlined, DeleteOutlined, FormOutlined, SaveOutlined } from "@ant-design/icons";
import { Alert, App, Button, Collapse, Input, Popconfirm, Spin, Tag } from "antd";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { STAGES, STAGE_COLOR, STAGE_LABEL, type Stage } from "../../../lib/floor-draft-flow-client";
import { DRAFT_LIST_PATH, DRAFT_SOURCE_LABEL } from "../../../lib/floor-proposal-client";
import { dmy, stampVN } from "../../../lib/date";
import { ApiError } from "../../../lib/http";
import { useAuth } from "../../auth/AuthContext";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import { useUnsavedGuard } from "../unsaved-guard";
import DuThaoPanel from "./components/DuThaoPanel";
import FloorDraftSteps from "./components/FloorDraftSteps";
import FloorProposalPanel from "./components/FloorProposalPanel";
import ToTrinhPanel from "./components/ToTrinhPanel";
import ToTrinhPreview from "./components/ToTrinhPreview";
import "./floor-draft.css";
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
  const { draft, form, dirty, loading, saving, err, applier, patch, save, ensureSaved, move, remove, reload, previewHtml } =
    useFloorDraft(id);
  const [preview, setPreview] = useState(false);
  const [moving, setMoving] = useState(false);
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
  const fail = (e: unknown) => {
    if (e instanceof ApiError && e.status === 409) askReloadOnConflict(e.message);
    else message.error(errText(e));
  };

  const doSave = async () => {
    if (!form) return;
    if (!form.title.trim()) { message.warning("Nhập tiêu đề bản nháp trước khi lưu."); return; }
    try { await save(); message.success("Đã lưu bản nháp."); } catch (e) { fail(e); }
  };

  const doMove = async (to: Stage, note?: string) => {
    const back = draft != null && STAGES.indexOf(to) < STAGES.indexOf(draft.stage);
    setMoving(true);
    try {
      await move(to, note);
      message.success(back ? `Đã trả về bước ${STAGE_LABEL[to]} — sửa xong thì đi tiếp như bình thường.`
        : `Đã chuyển sang bước ${STAGE_LABEL[to]}.`);
    } catch (e) { fail(e); } finally { setMoving(false); }
  };

  const doDelete = async () => {
    try { await remove(); message.success("Đã xoá bản nháp."); navigate(DRAFT_LIST_PATH); } catch (e) { message.error(errText(e)); }
  };

  if (loading) return <div className="main" style={{ padding: 32, textAlign: "center" }}><Spin /></div>;
  if (err || !draft || !form) {
    return (
      <div className="main">
        <Alert type="error" showIcon title={err || "Không tìm thấy bản nháp."} style={{ marginBottom: 12 }} />
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(DRAFT_LIST_PATH)}>Về danh sách bản nháp</Button>
      </div>
    );
  }

  const stage = draft.stage;
  const locked = !canEdit || stage === "ap_dung";
  const proposalPanel = (
    <FloorProposalPanel proposal={form.proposal} applier={applier} readOnly={locked || stage !== "nhap"} />
  );

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><FormOutlined style={{ marginRight: 8 }} />Quy trình giá sàn — {form.title || `Bản nháp #${draft.id}`}</h2>
          <p>
            Ngày tờ trình <b>{dmy(draft.as_of)}</b> · Lần {draft.doc?.lan ?? "—"} ·{" "}
            <Tag color={STAGE_COLOR[stage]} style={{ marginInlineEnd: 4 }}>{STAGE_LABEL[stage]}</Tag>
            <Tag style={{ marginInlineEnd: 4 }}>{DRAFT_SOURCE_LABEL[draft.source] ?? draft.source}</Tag>
            · Sửa lần cuối: {draft.updated_by ?? draft.created_by ?? "—"} lúc {stampVN(draft.updated_at)}
          </p>
        </div>
      </div>
      <ReadOnlyNotice cap="floor_suggest" />

      <FloorDraftSteps stage={stage} history={draft.history ?? []} canEdit={!locked} busy={moving || saving}
        onMove={doMove} />

      <div className="card fd-toolbar">
        <Button icon={<ArrowLeftOutlined />} onClick={() => leaveGuard(() => navigate(DRAFT_LIST_PATH))}>Danh sách</Button>
        {!locked && (
          // Không khoá theo `dirty`: ô vừa gõ chỉ được áp khi blur (lúc bấm nút) — khoá nút là cú bấm đầu bị nuốt.
          <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={doSave}>Lưu</Button>
        )}
        {dirty && <Tag color="warning">Có thay đổi chưa lưu</Tag>}
        {!locked && (
          <Popconfirm title="Xoá bản nháp này?" description="Bản nháp đã xoá không khôi phục được."
            okText="Xoá" cancelText="Huỷ" okButtonProps={{ danger: true }} onConfirm={doDelete}>
            <Button danger icon={<DeleteOutlined />} style={{ marginLeft: "auto" }}>Xoá</Button>
          </Popconfirm>
        )}
        <div className="fd-grid" style={{ width: "100%" }}>
          <label>
            <span style={LABEL}>Tiêu đề</span>
            <Input value={form.title} readOnly={locked} maxLength={200} onChange={(e) => patch({ title: e.target.value })} />
          </label>
          <label>
            <span style={LABEL}>Ghi chú nội bộ (không in lên tờ trình)</span>
            <Input.TextArea value={form.note} readOnly={locked} maxLength={4000} autoSize={{ minRows: 1, maxRows: 5 }}
              onChange={(e) => patch({ note: e.target.value })} />
          </label>
        </div>
      </div>

      {stage === "nhap" ? (
        <div className="card">
          <div className="card-head" style={{ marginBottom: 6 }}><h3 style={{ margin: 0 }}>Phương án giá sàn</h3></div>
          {proposalPanel}
          <div className="form-note" style={{ fontSize: 12.5, marginTop: 8 }}>
            Chỉnh xong bấm <b>Chốt dự thảo</b> để khoá số và lấy hình dự thảo. Cần sửa lại số thì trả về bước Nháp.
          </div>
        </div>
      ) : (
        <Collapse className="fd-collapse" items={[{
          key: "p", label: "Phương án giá sàn (đã chốt — trả về bước Nháp để sửa số)", children: proposalPanel,
        }]} />
      )}

      {stage === "du_thao" && (
        <DuThaoPanel draftId={id} version={draft.updated_at} sheet={form.sheet} dirty={dirty}
          editable={!locked} ensureSaved={ensureSaved} onSheet={(sheet) => patch({ sheet })} />
      )}
      {(stage === "to_trinh" || stage === "ap_dung") && (
        <Collapse className="fd-collapse" items={[{
          key: "d", label: "Hình dự thảo giá sàn điều chỉnh",
          children: <DuThaoPanel draftId={id} version={draft.updated_at} sheet={form.sheet} dirty={dirty}
            editable={false} ensureSaved={ensureSaved} onSheet={() => undefined} />,
        }]} />
      )}

      {(stage === "to_trinh" || stage === "ap_dung") && form.memo && (
        <ToTrinhPanel draftId={id} sig={draft.sig} memo={form.memo} editable={!locked && stage === "to_trinh"}
          ensureSaved={ensureSaved} onMemo={(memo) => patch({ memo })} onPreview={() => setPreview(true)} />
      )}

      {preview && (
        <ToTrinhPreview
          title={`Xem trước Tờ trình giá sàn — ${form.title || dmy(draft.as_of)}${dirty ? " (gồm thay đổi chưa lưu)" : ""}`}
          load={previewHtml}
          extraActions={!locked && dirty && <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={doSave}>Lưu</Button>}
          onClose={() => setPreview(false)}
        />
      )}
    </div>
  );
}
