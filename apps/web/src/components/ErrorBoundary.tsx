import { Component, type ErrorInfo, type ReactNode } from "react";
import { WarningOutlined } from "@ant-design/icons";

/* Chặn lỗi render của cây React: 1 component throw → không "trắng màn hình" toàn app,
   mà hiện màn hình sự cố + nút tải lại. Đặt ở gốc (main.tsx) bọc <App/>. */

type Props = { children: ReactNode };
type State = { hasError: boolean };

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Log đầy đủ để debug; có thể nối tới dịch vụ theo dõi lỗi (Sentry…) sau.
    console.error("[ErrorBoundary] Lỗi render:", error, info.componentStack);
  }

  private reload = (): void => window.location.reload();

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;
    return (
      <div style={WRAP}>
        <div style={{ maxWidth: 460, textAlign: "center" }}>
          <WarningOutlined style={{ fontSize: 44, color: "#f5a623" }} />
          <h1 style={{ fontSize: 20, margin: "16px 0 8px" }}>Giao diện gặp sự cố</h1>
          <p style={{ color: "#9fb0a6", margin: "0 0 20px", fontSize: 14 }}>
            Đã xảy ra lỗi hiển thị ngoài dự kiến. Vui lòng tải lại trang; nếu vẫn lỗi, hãy liên hệ quản trị viên.
          </p>
          <button type="button" onClick={this.reload} style={BTN}>
            Tải lại trang
          </button>
        </div>
      </div>
    );
  }
}

const WRAP: React.CSSProperties = {
  minHeight: "100vh", display: "grid", placeItems: "center",
  background: "#0f1714", color: "#e8efe9", padding: 24,
};
const BTN: React.CSSProperties = {
  background: "#1f8f5f", color: "#fff", border: 0, borderRadius: 8,
  padding: "10px 20px", fontSize: 14, cursor: "pointer",
};
