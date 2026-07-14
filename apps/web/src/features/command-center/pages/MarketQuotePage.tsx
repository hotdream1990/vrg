import { CheckCircleOutlined, SolutionOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useRef, useState } from "react";

import { dmy } from "../../../lib/date";
import {
  type MarketQuote,
  type MarketQuoteSummary,
  type Section,
  deleteQuote,
  emptyQuote,
  fetchQuoteMeta,
  getQuote,
  isEmptyQuote,
  listQuotes,
  saveQuote,
} from "../../../lib/market-quote-client";
import { useAuth } from "../../auth/AuthContext";
import DataSourceNote from "../sections/DataSourceNote";
import DateInput from "../sections/DateInput";
import DateRangeBar from "../sections/DateRangeBar";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import GradePriceTable from "./components/GradePriceTable";
import ProposalTable from "./components/ProposalTable";
import RegionLatexTable from "./components/RegionLatexTable";
import VcbRateBar from "./components/VcbRateBar";
import "../../bulletin/bulletin.css";

const todayISO = () => new Date().toISOString().slice(0, 10);
type SectKey = "domestic_private" | "domestic_export" | "export_vrg" | "domestic_vrg";

/** Chỉ giữ các ô người dùng đã sửa trong phiên — để phiếu KHÔNG ghi đè kho "Giá mủ nguyên liệu"
 *  bằng ảnh chụp cũ/số của ngày khác (chống carry-forward mủ nước). */
const pickEdited = (m: Record<string, number | null>, keys: Set<string>): Record<string, number | null> =>
  Object.fromEntries(Object.entries(m).filter(([k]) => keys.has(k)));

/** Quản lý số liệu → Báo giá mủ thị trường: 1 phiếu/ngày, TỰ LƯU (auto-save) khi nhập. */
export default function MarketQuotePage() {
  const { canEdit } = useAuth();
  const [grades, setGrades] = useState<string[]>([]);
  const [units, setUnits] = useState<string[]>([]);
  const [packOpts, setPackOpts] = useState<string[]>([]);
  const [list, setList] = useState<MarketQuoteSummary[]>([]);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [draft, setDraft] = useState<MarketQuote | null>(null);
  const [prev, setPrev] = useState<MarketQuote | null>(null); // phiếu gần nhất TRƯỚC ngày draft → cảnh báo lệch ≥10%
  const [isNew, setIsNew] = useState(false);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [savedAt, setSavedAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [info, setInfo] = useState("");
  const [createDate, setCreateDate] = useState(todayISO());
  const lastSaved = useRef("");
  const timer = useRef<number | null>(null);
  const editedR = useRef<Set<string>>(new Set()); // ô mủ nước user đã sửa phiên này
  const editedRc = useRef<Set<string>>(new Set()); // ô mủ chén user đã sửa phiên này
  const resetEdits = () => { editedR.current = new Set(); editedRc.current = new Set(); };

  useEffect(() => {
    fetchQuoteMeta()
      .then((m) => { setGrades(m.grades); setUnits(m.units); setPackOpts(m.packaging); })
      .catch(() => {});
  }, []);
  const loadList = useCallback(() => {
    listQuotes(from || undefined, to || undefined).then(setList).catch((e) => setErr(e.message));
  }, [from, to]);
  useEffect(() => { loadList(); }, [loadList]);

  // Auto-save: nhập xong ~0.9s tự lưu (bỏ qua khi phiếu còn trống / chưa đổi gì).
  useEffect(() => {
    if (!draft || !canEdit) return;
    const json = JSON.stringify(draft);
    if (json === lastSaved.current || isEmptyQuote(draft)) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      setSaveState("saving"); setErr("");
      // Chỉ đồng bộ ô mủ nước/mủ chén user vừa sửa (không đẩy cả snapshot → không đè kho bằng số cũ/ngày khác).
      const payload = {
        ...draft,
        regions: pickEdited(draft.regions ?? {}, editedR.current),
        regions_cup: pickEdited(draft.regions_cup ?? {}, editedRc.current),
      };
      saveQuote(payload).then(() => {
        lastSaved.current = json;
        setSaveState("saved"); setSavedAt(new Date().toLocaleTimeString("vi-VN"));
        setIsNew(false); loadList();
      }).catch((e) => { setSaveState("error"); setErr(e instanceof Error ? e.message : "Lỗi lưu"); });
    }, 900);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [draft, canEdit, loadList]);

  // Phiếu gần nhất TRƯỚC ngày `as_of` (để đối chiếu cảnh báo). Lỗi/không có → bỏ qua.
  const loadPrev = useCallback(async (as_of: string) => {
    try {
      const prior = (await listQuotes(undefined, as_of)).find((s) => s.as_of < as_of);
      setPrev(prior ? await getQuote(prior.as_of) : null);
    } catch { setPrev(null); }
  }, []);

  const openDate = async (as_of: string) => {
    setErr(""); setInfo("");
    try {
      const q = await getQuote(as_of);
      lastSaved.current = JSON.stringify(q); setSaveState("idle"); setSavedAt("");
      resetEdits(); // mở phiếu = số từ kho, chưa có ô nào user sửa → không tự đồng bộ lại
      setIsNew(false); setDraft(q); void loadPrev(as_of);
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
  };
  // Tạo mới / đổi ngày (cho phép chọn ngày trong quá khứ): ngày ĐÃ CÓ phiếu → mở phiếu sẵn có
  // + báo cho người dùng biết (chống trùng); ngày trống → phiếu mới
  // (keepData: giữ dữ liệu đang nhập khi chỉ đổi ngày).
  const startAt = async (as_of: string, keepData = false) => {
    setErr(""); setInfo("");
    try {
      if ((await listQuotes(as_of, as_of)).length > 0) {
        await openDate(as_of);
        setInfo(`Ngày ${dmy(as_of)} đã có phiếu — đã mở phiếu sẵn có để xem/sửa.`);
        return;
      }
      lastSaved.current = ""; setSaveState("idle"); setSavedAt(""); setIsNew(true);
      resetEdits();
      if (keepData) {
        // Đổi ngày: giữ phần đang nhập (tỷ giá/SVR/đề xuất) nhưng MỦ NƯỚC phải theo NGÀY —
        // đọc lại từ kho theo ngày mới, TUYỆT ĐỐI không mang số mủ nước ngày cũ (chống carry-forward).
        const fresh = await getQuote(as_of).catch(() => null);
        setDraft((d) => (d
          ? { ...d, as_of, regions: fresh?.regions ?? {}, regions_cup: fresh?.regions_cup ?? {} }
          : emptyQuote(as_of, grades)));
      } else {
        setDraft(emptyQuote(as_of, grades));
      }
      void loadPrev(as_of);
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
  };
  const startNew = () => { void startAt(createDate); };

  const setSect = (k: SectKey, patch: Partial<Section>) =>
    setDraft((d) => d && { ...d, [k]: { ...d[k], ...patch } });
  const setPrice = (k: SectKey, g: string, v: number | null) =>
    setDraft((d) => d && { ...d, [k]: { ...d[k], prices: { ...d[k].prices, [g]: v } } });
  const setPackaging = (k: SectKey, g: string, v: string) =>
    setDraft((d) => d && { ...d, [k]: { ...d[k], packaging: { ...d[k].packaging, [g]: v } } });
  const setShipping = (k: SectKey, g: string, v: string) =>
    setDraft((d) => d && { ...d, [k]: { ...d[k], shipping: { ...d[k].shipping, [g]: v } } });
  const setStatus = (k: SectKey, g: string, v: string) =>
    setDraft((d) => d && { ...d, [k]: { ...d[k], status: { ...(d[k].status ?? {}), [g]: v } } });
  const setRegion = (u: string, v: number | null) => {
    editedR.current.add(u); // đánh dấu ô user sửa → mới đồng bộ ô này xuống kho
    setDraft((d) => d && { ...d, regions: { ...d.regions, [u]: v } });
  };
  const setRegionCup = (u: string, v: number | null) => {
    editedRc.current.add(u);
    setDraft((d) => d && { ...d, regions_cup: { ...d.regions_cup, [u]: v } });
  };
  const setProp = (patch: Partial<MarketQuote["customer_proposal"]>) =>
    setDraft((d) => d && { ...d, customer_proposal: { ...d.customer_proposal, ...patch } });
  const setPropQty = (g: string, v: number | null) =>
    setDraft((d) => d && { ...d, customer_proposal: { ...d.customer_proposal, qty: { ...d.customer_proposal.qty, [g]: v } } });
  const setPropPrice = (g: string, v: number | null) =>
    setDraft((d) => d && { ...d, customer_proposal: { ...d.customer_proposal, prices: { ...d.customer_proposal.prices, [g]: v } } });

  const remove = async () => {
    if (!draft || !confirm(`Xoá phiếu báo giá ngày ${dmy(draft.as_of)}? (Giá mủ nước đã đồng bộ vẫn giữ)`)) return;
    setBusy(true);
    try { await deleteQuote(draft.as_of); setDraft(null); loadList(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi xoá"); }
    finally { setBusy(false); }
  };

  const statusText = saveState === "saving" ? "Đang lưu…"
    : saveState === "saved" ? `Đã lưu lúc ${savedAt}`
    : saveState === "error" ? "Lỗi lưu — sửa lại để thử lại" : "Tự lưu khi nhập";

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><SolutionOutlined style={{ marginRight: 8 }} />Báo giá mủ thị trường</h2>
          <p>Phiếu báo giá theo ngày: tỷ giá VCB · giá SVR (NĐ tư nhân/NĐ hàng XK/VRG XK/VRG nội địa) · đề xuất mua từ khách hàng · giá mủ khu vực (nước + chén). Tự lưu khi nhập.</p>
        </div>
        {canEdit && (
          <div className="actions" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <label className="blt-date-label" style={{ margin: 0, whiteSpace: "nowrap" }}>Ngày phiếu:
              <DateInput value={createDate} noFuture style={{ width: 140 }}
                onChange={(v) => setCreateDate(v || todayISO())} />
            </label>
            <button className="btn btn-primary" style={{ whiteSpace: "nowrap" }} onClick={startNew}>＋ Tạo phiếu mới</button>
          </div>
        )}
      </div>

      <ReadOnlyNotice />
      <DataSourceNote page="market-quote" />

      <DateRangeBar from={from} to={to} onFrom={setFrom} onTo={setTo} info={`${list.length} phiếu`} />
      {err && <div className="blt-error">{err}</div>}
      {info && <div className="blt-info">{info}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head"><h3>Các phiếu đã có</h3></div>
        {list.length === 0 ? (
          <div className="scan-empty">{canEdit ? 'Chưa có phiếu nào — bấm "Tạo phiếu mới".' : "Chưa có phiếu nào."}</div>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {list.map((s) => (
              <button key={s.as_of} className={`btn${draft?.as_of === s.as_of ? " btn-primary" : ""}`}
                onClick={() => openDate(s.as_of)}>
                {dmy(s.as_of)} <span style={{ opacity: 0.7 }}>({s.filled} giá)</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {draft && (
        <>
          <div className="card blt-section" style={{ marginBottom: 16 }}>
            <div className="blt-section-header">
              <h3>Phiếu ngày {dmy(draft.as_of)}</h3>
              <div className="blt-section-meta" style={{ alignItems: "center" }}>
                <label className="blt-date-label">Ngày báo giá:
                  <DateInput value={draft.as_of} readOnly={!canEdit || !isNew}
                    onChange={(v) => startAt(v, true)} />
                </label>
                {canEdit && (
                  <span className="db-badge" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    {saveState === "saving" ? <span className="spinner" /> : <CheckCircleOutlined />} {statusText}
                  </span>
                )}
                {canEdit && <button className="btn" onClick={remove} disabled={busy}>Xoá phiếu</button>}
              </div>
            </div>
          </div>

          <VcbRateBar fx={draft.fx} date={draft.as_of} readOnly={!canEdit} prevFx={prev?.fx}
            onChange={(fx) => setDraft((d) => d && { ...d, fx })} />

          <GradePriceTable title="1. Giá nội địa — hàng tư nhân" subtitle="VNĐ/tấn + tình trạng" grades={grades}
            section={draft.domestic_private} unitLabel="Đồng/tấn" packagingOptions={packOpts} withStatus readOnly={!canEdit}
            prevPrices={prev?.domestic_private?.prices}
            onPrice={(g, v) => setPrice("domestic_private", g, v)}
            onPackaging={(g, v) => setPackaging("domestic_private", g, v)}
            onShipping={(g, v) => setShipping("domestic_private", g, v)}
            onStatus={(g, v) => setStatus("domestic_private", g, v)}
            onNote={(v) => setSect("domestic_private", { note: v })} />

          <GradePriceTable title="2. Giá nội địa — hàng xuất khẩu" subtitle="VNĐ/tấn + tình trạng" grades={grades}
            section={draft.domestic_export ?? { prices: {}, packaging: {}, shipping: {}, status: {}, note: "" }}
            unitLabel="Đồng/tấn" packagingOptions={packOpts} withStatus readOnly={!canEdit}
            prevPrices={prev?.domestic_export?.prices}
            onPrice={(g, v) => setPrice("domestic_export", g, v)}
            onPackaging={(g, v) => setPackaging("domestic_export", g, v)}
            onShipping={(g, v) => setShipping("domestic_export", g, v)}
            onStatus={(g, v) => setStatus("domestic_export", g, v)}
            onNote={(v) => setSect("domestic_export", { note: v })} />

          <GradePriceTable title="3. Giá xuất khẩu — hàng VRG" subtitle="USD/tấn (FOB) + tình trạng" grades={grades}
            section={draft.export_vrg} unitLabel="USD/tấn" packagingOptions={packOpts} withStatus readOnly={!canEdit}
            prevPrices={prev?.export_vrg?.prices}
            onPrice={(g, v) => setPrice("export_vrg", g, v)}
            onPackaging={(g, v) => setPackaging("export_vrg", g, v)}
            onShipping={(g, v) => setShipping("export_vrg", g, v)}
            onStatus={(g, v) => setStatus("export_vrg", g, v)}
            onNote={(v) => setSect("export_vrg", { note: v })} />

          <GradePriceTable title="4. Giá nội địa — hàng VRG" subtitle="VNĐ/tấn + tình trạng" grades={grades}
            section={draft.domestic_vrg} unitLabel="Đồng/tấn" packagingOptions={packOpts} withStatus readOnly={!canEdit}
            prevPrices={prev?.domestic_vrg?.prices}
            onPrice={(g, v) => setPrice("domestic_vrg", g, v)}
            onPackaging={(g, v) => setPackaging("domestic_vrg", g, v)}
            onShipping={(g, v) => setShipping("domestic_vrg", g, v)}
            onStatus={(g, v) => setStatus("domestic_vrg", g, v)}
            onNote={(v) => setSect("domestic_vrg", { note: v })} />

          <ProposalTable grades={grades} section={draft.customer_proposal ?? { qty: {}, prices: {}, note: "" }}
            readOnly={!canEdit} prevQty={prev?.customer_proposal?.qty} prevPrices={prev?.customer_proposal?.prices}
            onQty={setPropQty} onPrice={setPropPrice} onNote={(v) => setProp({ note: v })} />

          <RegionLatexTable units={units} regions={draft.regions ?? {}} regionsCup={draft.regions_cup ?? {}}
            readOnly={!canEdit} prevRegions={prev?.regions} prevRegionsCup={prev?.regions_cup}
            onPrice={setRegion} onPriceCup={setRegionCup} />

          <div className="card blt-section" style={{ marginBottom: 16 }}>
            <label className="blt-date-label" style={{ display: "block" }}>Ghi chú chung / Cảnh báo
              <textarea className="blt-date-input" style={{ width: "100%", minHeight: 52, resize: "vertical" }}
                value={draft.footer} readOnly={!canEdit} placeholder="Ghi chú cuối phiếu…"
                onChange={(e) => setDraft((d) => d && { ...d, footer: e.target.value })} />
            </label>
          </div>
        </>
      )}
    </div>
  );
}
