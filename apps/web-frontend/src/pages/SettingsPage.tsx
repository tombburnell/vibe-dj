import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { useSettingsModal } from "@/contexts/SettingsModalContext";

/** Legacy `/settings` URL: open the modal and return to the workspace. */
export function SettingsPage() {
  const navigate = useNavigate();
  const { openSettings } = useSettingsModal();

  useEffect(() => {
    openSettings();
    navigate("/", { replace: true });
  }, [openSettings, navigate]);

  return (
    <div className="flex min-h-[30vh] items-center justify-center bg-background text-[0.875rem] text-muted">
      Opening settings…
    </div>
  );
}
