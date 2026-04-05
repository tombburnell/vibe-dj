import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { WelcomeModal } from "@/components/onboarding/WelcomeModal";
import { SettingsModalHost } from "@/components/settings/SettingsModalHost";
import { SettingsModalProvider } from "@/contexts/SettingsModalContext";
import { WelcomeModalProvider } from "@/contexts/WelcomeModalContext";
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
          <WelcomeModalProvider>
            <BrowserRouter>
              <SettingsModalHost />
              <WelcomeModal />
              <Routes>
                <Route path="/" element={<WorkspacePage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/spotify-callback" element={<SpotifyCallbackPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </BrowserRouter>
          </WelcomeModalProvider>
        </SettingsModalProvider>
      </ToastProvider>
    </QueryProvider>
  );
}
