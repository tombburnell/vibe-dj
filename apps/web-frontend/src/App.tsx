import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { ToastProvider } from "@/providers/ToastProvider";
import { SettingsPage } from "@/pages/SettingsPage";
import { WorkspacePage } from "@/pages/WorkspacePage";

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<WorkspacePage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}
