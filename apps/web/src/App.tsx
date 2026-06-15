import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import AppLayout from "./features/command-center/AppLayout";
import DashboardPage from "./features/command-center/pages/DashboardPage";
import ScanPage from "./features/command-center/pages/ScanPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/quet-da-san" element={<ScanPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
