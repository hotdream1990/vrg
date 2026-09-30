/* Màn "GIÁM SÁT CHỈ SỐ" (nhóm Nhà máy thông minh) — điện · nước · số bành — số liệu theo NGÀY đọc thẳng từ
   SCADA (AVEVA Historian) của nhà máy: số lũy kế thời gian thực · biểu đồ tiêu thụ theo ngày · bảng.
   Chỉ số đầu ngày = số lúc 00:00, chỉ số cuối = số lúc 00:00 ngày sau (hôm nay = số mới nhất) nên
   tổng các ngày = tổng cả kỳ. Server tính hết — web chỉ hiển thị. Quyền: `smart_factory`. */

import { ControlOutlined, ReloadOutlined } from "@ant-design/icons";
import { Alert, App, Button, Skeleton, Spin } from "antd";
import { useEffect, useState } from "react";

import { ApiError } from "../../../../lib/http";
import { type DailyMeters, downloadDailyMetersXlsx, fetchDailyMeters } from "../../../../lib/smart-factory-client";
import { useAuth } from "../../../auth/AuthContext";
import { LoadErrorAlert, type MeterLoadError, NoFactory, NoTags } from "./FactoryMeterAlerts";
import FactoryMeterCharts from "./FactoryMeterCharts";
import FactoryLiveKpis from "./FactoryLiveKpis";
import FactoryMeterTable from "./FactoryMeterTable";
import FactoryMeterToolbar from "./FactoryMeterToolbar";
import { defaultRange, errText, type Range, rangeError, toISO } from "./smart-factory-format";
import { useFactoryPicker } from "./use-factory-picker";
import "./smart-factory.css";

const STORE_KEY = "vrg.smart-factory.factory-id";
const LOAD_FAIL = "Không tải được dữ liệu, vui lòng thử lại.";

export default function FactoryMetersPage() {
  const { message } = App.useApp();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const {
    factories, error: listErr, factoryId, pick: pickFactory, reload: reloadList,
  } = useFactoryPicker(STORE_KEY);
  const [range, setRange] = useState<Range>(defaultRange);
  const [data, setData] = useState<DailyMeters | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<MeterLoadError | null>(null);
  const [tick, setTick] = useState(0);
  const [exporting, setExporting] = useState(false);

  const from = toISO(range[0]);
  const to = toISO(range[1]);
  const badRange = rangeError(range);
  const factory = factories?.find((f) => f.id === factoryId) ?? null;
  // Chưa khai tag nào → khỏi gọi SCADA (server cũng trả 400), chỉ hiện lời nhắc.
  const noTags = factory != null && factory.metrics.length === 0;

  useEffect(() => {
    if (factoryId == null || badRange || noTags) { setLoading(false); setErr(null); return; }
    let alive = true;
    setLoading(true);
    setErr(null);
    fetchDailyMeters(factoryId, from, to)
      .then((d) => { if (alive) setData(d); })
      .catch((e: unknown) => {
        if (!alive) return;
        const status = e instanceof ApiError ? e.status : 0;
        setData(null);
        setErr({ text: errText(e, LOAD_FAIL), status });
        // 404 = nhà máy vừa bị tắt/xoá → tải lại danh sách (tự chuyển sang nhà máy còn lại).
        if (status === 404) reloadList();
      })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [factoryId, from, to, badRange, noTags, tick]);   // reloadList chỉ là lệnh tải lại — không cần theo dõi

  const exportXlsx = async () => {
    if (!factory) return;
    setExporting(true);
    try {
      await downloadDailyMetersXlsx(factory, from, to);
    } catch (e) {
      message.error(errText(e, "Không xuất được Excel — thử lại sau."));
    } finally {
      setExporting(false);
    }
  };

  // Chỉ hiện số của ĐÚNG nhà máy đang chọn: đổi nhà máy thì ẩn số cũ (Skeleton) tới khi có số mới;
  // đổi kỳ vẫn giữ số cũ mờ dưới Spin.
  const shown = badRange || noTags || data?.factory.id !== factoryId ? null : data;
  // Tải lại cả danh sách nhà máy: admin vừa khai thêm tag / tắt nhà máy thì màn cập nhật theo.
  const retry = () => { setTick((t) => t + 1); reloadList(); };

  return (
    <div className="main sf-page">
      <div className="page-title">
        <div>
          <h2><ControlOutlined style={{ marginRight: 8 }} />Giám sát chỉ số</h2>
        </div>
      </div>

      {listErr && (
        <Alert type="error" showIcon className="sf-alert"
          title={`Chưa tải được danh sách nhà máy: ${listErr}`}
          action={<Button size="small" icon={<ReloadOutlined />} onClick={reloadList}>Thử lại</Button>} />
      )}

      {!factories ? (
        !listErr && <div className="card"><Skeleton active paragraph={{ rows: 6 }} /></div>
      ) : factories.length === 0 ? (
        <NoFactory isAdmin={isAdmin} />
      ) : (
        <>
          <FactoryMeterToolbar
            factories={factories} factoryId={factoryId} onFactory={pickFactory}
            range={range} onRange={setRange}
            onReload={retry} onExport={() => void exportXlsx()}
            loading={loading} exporting={exporting}
            canExport={!!shown && !loading}
          />
          {noTags ? <NoTags name={factory.name} isAdmin={isAdmin} />
            : factory && <FactoryLiveKpis factoryId={factory.id} count={factory.metrics.length} />}
          {badRange && <Alert type="warning" showIcon className="sf-alert" title={badRange} />}
          {err && !noTags && <LoadErrorAlert error={err} onRetry={retry} />}
          {!shown ? (
            loading && <div className="card"><Skeleton active paragraph={{ rows: 8 }} /></div>
          ) : (
            <Spin spinning={loading} description="Đang đọc số liệu SCADA…">
              <FactoryMeterCharts data={shown} />
              <FactoryMeterTable data={shown} />
            </Spin>
          )}
        </>
      )}
    </div>
  );
}
