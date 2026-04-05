import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { SettingsModalHost } from "@/components/settings/SettingsModalHost";
import { SettingsModalProvider } from "@/contexts/SettingsModalContext";
import { SettingsPage } from "@/pages/SettingsPage";
import { SpotifyCallbackPage } from "@/pages/SpotifyCallbackPage";
import { WorkspacePage } from "@/pages/WorkspacePage";
import { QueryProvider } from "@/providers/QueryProvider";
import { ToastProvider } from "@/providers/ToastProvider";

export default function App() {
  return (
    <QueryProvider>
      <ToastProvider>
        <SettingsModalProvider>
          <BrowserRouter>
            <SettingsModalHost />
            <Routes>
              <Route path="/" element={<WorkspacePage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/spotify-callback" element={<SpotifyCallbackPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </SettingsModalProvider>
      </ToastProvider>
    </QueryProvider>
  );
}
