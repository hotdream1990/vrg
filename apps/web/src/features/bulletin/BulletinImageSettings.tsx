/**
 * BulletinImageSettings — Panel quản lý hình ảnh bản tin.
 *
 * Hiển thị 5 slot: cover-front, cover-back, header-banner, footer-banner, logo-vrg.
 * Cho phép: xem preview, upload mới, revert về default.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import type { ImageSlot } from "../../lib/bulletin-client";
import {
  deleteCustomImage,
  getImageUrl,
  listImages,
  uploadImage,
} from "../../lib/bulletin-client";

import "./bulletin-images.css";

/* ── SVG Icons (inline, 16×16) ── */

const IconImage = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="m21 15-5-5L5 21" />
  </svg>
);

const IconFile = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" /><polyline points="14 2 14 8 20 8" />
  </svg>
);

const IconPalette = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="13.5" cy="6.5" r="2.5" /><circle cx="17.5" cy="10.5" r="2.5" /><circle cx="8.5" cy="7.5" r="2.5" /><circle cx="6.5" cy="12.5" r="2.5" />
    <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z" />
  </svg>
);

const IconBuilding = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="4" y="2" width="16" height="20" rx="2" /><path d="M9 22v-4h6v4" /><path d="M8 6h.01" /><path d="M16 6h.01" /><path d="M12 6h.01" /><path d="M12 10h.01" /><path d="M12 14h.01" /><path d="M16 10h.01" /><path d="M16 14h.01" /><path d="M8 10h.01" /><path d="M8 14h.01" />
  </svg>
);

const IconUpload = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
  </svg>
);

const IconUndo = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 7v6h6" /><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13" />
  </svg>
);

const IconAlertCircle = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
  </svg>
);

const IconChevron = ({ open }: { open: boolean }) => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
    style={{ transition: "transform 0.25s ease", transform: open ? "rotate(90deg)" : "rotate(0deg)" }}>
    <polyline points="9 18 15 12 9 6" />
  </svg>
);

type Props = { open: boolean; onToggle: () => void };

export default function BulletinImageSettings({ open, onToggle }: Props) {
  const [slots, setSlots] = useState<ImageSlot[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState<string | null>(null);
  const fileRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listImages();
      setSlots(res.images);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open && slots.length === 0) refresh();
  }, [open, refresh, slots.length]);

  const handleUpload = async (slot: string, file: File) => {
    setUploading(slot);
    setError(null);
    try {
      const updated = await uploadImage(slot, file);
      setSlots(updated);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploading(null);
    }
  };

  const handleRevert = async (slot: string) => {
    setUploading(slot);
    setError(null);
    try {
      const updated = await deleteCustomImage(slot);
      setSlots(updated);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploading(null);
    }
  };

  const handleFileChange = (slot: string) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(slot, file);
    e.target.value = "";
  };

  const triggerUpload = (slot: string) => {
    fileRefs.current[slot]?.click();
  };

  const covers = slots.filter((s) => s.slot.startsWith("cover-"));
  const banners = slots.filter((s) => s.slot.endsWith("-banner"));
  const logos = slots.filter((s) => s.slot.startsWith("logo-"));

  return (
    <div className="blt-img-settings">
      <button className="blt-img-toggle" onClick={onToggle}>
        <span className="blt-img-toggle-label"><IconImage /> Cài đặt Hình ảnh bản tin</span>
        <IconChevron open={open} />
      </button>

      {open && (
        <div className="blt-img-panel">
          {error && (
            <div className="blt-error" style={{ margin: "0 0 12px" }}>
              <IconAlertCircle /> {error}
            </div>
          )}
          {loading && <div className="blt-loading"><span className="spinner" /> Đang tải...</div>}

          {!loading && slots.length > 0 && (
            <>
              <div className="blt-img-group">
                <h4><IconFile /> Hình bìa</h4>
                <div className="blt-img-grid">
                  {covers.map((s) => (
                    <ImageCard
                      key={s.slot} slot={s} uploading={uploading === s.slot}
                      onUpload={() => triggerUpload(s.slot)} onRevert={() => handleRevert(s.slot)}
                      fileRef={(el) => { fileRefs.current[s.slot] = el; }}
                      onFileChange={handleFileChange(s.slot)}
                    />
                  ))}
                </div>
              </div>

              <div className="blt-img-group">
                <h4><IconPalette /> Banner Header / Footer</h4>
                <div className="blt-img-grid">
                  {banners.map((s) => (
                    <ImageCard
                      key={s.slot} slot={s} uploading={uploading === s.slot}
                      onUpload={() => triggerUpload(s.slot)} onRevert={() => handleRevert(s.slot)}
                      fileRef={(el) => { fileRefs.current[s.slot] = el; }}
                      onFileChange={handleFileChange(s.slot)}
                    />
                  ))}
                </div>
              </div>

              <div className="blt-img-group">
                <h4><IconBuilding /> Logo</h4>
                <div className="blt-img-grid">
                  {logos.map((s) => (
                    <ImageCard
                      key={s.slot} slot={s} uploading={uploading === s.slot}
                      onUpload={() => triggerUpload(s.slot)} onRevert={() => handleRevert(s.slot)}
                      fileRef={(el) => { fileRefs.current[s.slot] = el; }}
                      onFileChange={handleFileChange(s.slot)}
                    />
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

/* ── ImageCard sub-component ── */

function ImageCard({
  slot, uploading, onUpload, onRevert, fileRef, onFileChange,
}: {
  slot: ImageSlot; uploading: boolean;
  onUpload: () => void; onRevert: () => void;
  fileRef: (el: HTMLInputElement | null) => void;
  onFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  const isCustom = slot.active_source === "custom";

  return (
    <div className={`blt-img-card ${isCustom ? "blt-img-custom" : ""}`}>
      <div className="blt-img-label">
        {slot.label}
        {isCustom && <span className="chip info" style={{ marginLeft: 8 }}>Tùy chỉnh</span>}
        {!isCustom && slot.active_source === "default" && (
          <span className="chip" style={{ marginLeft: 8 }}>Mặc định</span>
        )}
      </div>

      <div className="blt-img-preview">
        {slot.active_url ? (
          <img src={getImageUrl(slot.slot)} alt={slot.label} loading="lazy" />
        ) : (
          <div className="blt-img-empty">Chưa có hình</div>
        )}
      </div>

      <div className="blt-img-actions">
        <input
          type="file" accept="image/jpeg,image/png,image/webp"
          ref={fileRef} onChange={onFileChange} style={{ display: "none" }}
        />
        <button className="btn btn-sm" onClick={onUpload} disabled={uploading}>
          {uploading ? <span className="spinner" /> : <IconUpload />} Upload
        </button>
        {isCustom && (
          <button className="btn btn-sm btn-danger" onClick={onRevert} disabled={uploading}>
            <IconUndo /> Về mặc định
          </button>
        )}
      </div>
    </div>
  );
}
