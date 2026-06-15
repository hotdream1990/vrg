import { Outlet } from "react-router-dom";

import Footer from "./Footer";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

/** Khung chung (giữ nguyên giữa các route): top bar + sidebar + nội dung route + footer. */
export default function AppLayout() {
  return (
    <>
      <TopBar />
      <div className="shell">
        <Sidebar />
        <main className="main">
          <Outlet />
        </main>
      </div>
      <Footer />
    </>
  );
}
